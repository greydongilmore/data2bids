# -*- coding: utf-8 -*-
"""
Created on Sat Dec 29 13:49:51 2018

@author: Greydon
"""
import os
import numpy as np
import pandas as pd
pd.set_option('precision', 6)
import json
from collections import OrderedDict
import datetime
import shutil
from PySide2 import QtCore
import time
import sys
import re

from helpers import EDFReader, sorted_nicely, partition, determine_groups, fix_sessions, read_annotation_block, deidentify_edf

class edf2bids(QtCore.QThread):
	"""
	This class is a thread, which manages one thread of control within the GUI.
	
	:param new_sessions: Dictionary containing information about each subject. Wether there are new sessions to process in the input directory. 
	:type new_sessions: dictionary
	:param file_info: Information about each subject file in the input directory
	:type file_info: dictionary
	:param input_path: Path to the input directory.
	:type input_path: string
	:param output_path: path to the output directory
	:type output_path: string
	:param coordinates: Optional list of electrode coordinates (x,y,z)
	:type coordinates: list or None
	:param electrode_imp: Optional list of electrode impedances
	:type electrode_imp: list or None
	:param make_dir: Make the directory
	:type make_dir: boolean
	:param overwrite: If duplicate data is present in the output directory overwrite it.
	:type overwrite: boolean
	:param verbose: Print out process steps.
	:type verbose: boolean
	:param annotation_extract: Extract annotations from the edf file.
	:type annotation_extract: boolean
	:param compress: Compress the edf file
	:type compress: boolean
	
	"""

	progressEvent = QtCore.Signal(str)
	
	def __init__(self):	
		QtCore.QThread.__init__(self)
		
		self.new_sessions = []
		self.file_info = []
		self.chan_label_file = []
		self.input_path = []
		self.output_path = []
		self.script_path = []
		self.coordinates = []
		self.electrode_imp = []
		self.make_dir = []
		self.overwrite = []
		self.verbose = []
		self.deidentify_source = False
		self.offset_date = []
		self.bids_settings = []
		self.test_conversion = []
		self.annotations_only = []
				
		self.running = False
		self.userAbort = False
		
	def stop(self):
		self.running = False
		self.userAbort = True
		
	def _write_tsv(self, fname, df, overwrite=False, verbose=False, append = False):
		"""
		Writes input dataframe to a .tsv file
		
		:param fname: Filename given to the output tsv file.
		:type fname: string
		:param df: Dataframe containing the information to write.
		:type df: dataframe
		:param overwrite: If duplicate data is present in the output directory overwrite it.
		:type overwrite: boolean
		:param verbose: Print out process steps.
		:type verbose: boolean
		:param append: Append data to file if it exists.
		:type append: boolean
	
		"""
		if sys.platform == 'win32':
			if os.path.exists(fname) and not overwrite:
				pass
			if os.path.exists(fname) and append:
				with open(fname,'a') as f:
					df.to_csv(f, sep='\t', index=False, header = False, na_rep='n/a', mode='a', line_terminator="")
				with open(fname) as f:
					lines = f.readlines()
					last = len(lines) - 1
					lines[last] = lines[last].replace('\r','').replace('\n','')
				with open(fname, 'w') as wr:
					wr.writelines(lines) 
			else:
				data1 = df.iloc[0:len(df)-1]
				data2 = df.iloc[[len(df)-1]]
				data1.to_csv(fname, sep='\t', encoding='utf-8', index = False)
				data2.to_csv(fname, sep='\t', encoding='utf-8', header= False, index = False, mode='a', line_terminator="")
		else:
			if os.path.exists(fname) and not overwrite:
				pass
			if os.path.exists(fname) and append:
				with open(fname,'a') as f:
					df.to_csv(f, sep='\t', index=False, header = False, na_rep='n/a', mode='a', line_terminator="")
			else:
				data1 = df.iloc[0:len(df)-1]
				data2 = df.iloc[[len(df)-1]]
				data1.to_csv(fname, sep='\t', encoding='utf-8', index = False)
				data2.to_csv(fname, sep='\t', encoding='utf-8', header= False, index = False, mode='a',line_terminator="")

	def _write_json(self, dictionary, fname, overwrite=False, verbose=False):
		"""
		Writes input data to a .json file
		
		:param fname: Filename given to the output json file.
		:type fname: string
		:param dictionary: Dictionary containing the information to write.
		:type dictionary: dictionary
		:param overwrite: If duplicate data is present in the output directory overwrite it.
		:type overwrite: boolean
		:param verbose: Print out process steps.
		:type verbose: boolean
	
		"""
		json_output = json.dumps(dictionary, indent=4)
		with open(fname, 'w') as fid:
			fid.write(json_output)
			fid.write('\n')
	
		if verbose is True:
			print(os.linesep + "Writing '%s'..." % fname + os.linesep)
			print(json_output)
			
	def make_bids_filename(self, subject_id, session_id, task_id, run_num, suffix, prefix):
		"""
		Constructs a BIDsified filename.
		
		:param subject_id: Subject identifier.
		:type subject_id: string or None
		:param session_id: Session identifier.
		:type session_id: string or None
		:param run_num: Run identifier.
		:type run_num: string or None
		:param suffix: Extension for the file.
		:type suffix: string
		:param prefix: Path to where the file is to be saved.
		:type prefix: string
		
		:return filename: BIDsified filename.
		:type filename: string
		
		"""
		if isinstance(session_id, str):
			if 'ses' in session_id:
				session_id = session_id.split('-')[1]
				
		order = OrderedDict([('ses', session_id if session_id is not None else None),
							 ('task', task_id if task_id is not None else None),
							 ('run', run_num if run_num is not None else None)])
	
		filename = []
		if subject_id is not None:
			filename.append(subject_id)
		for key, val in order.items():
			if val is not None:
				filename.append('%s-%s' % (key, val))
	
		if isinstance(suffix, str):
			filename.append(suffix)
	
		filename = '_'.join(filename)
		if isinstance(prefix, str):
			filename = os.path.join(prefix, filename)
			
		return filename
	
	def make_bids_folders(self, subject_id, session_id, kind, output_path, make_dir, overwrite):
		"""
		Constructs a BIDsified folder structure.
		
		:param subject_id: Subject identifier.
		:type subject_id: string or None
		:param session_id: Session identifier.
		:type session_id: string or None
		:param kind: Type of input data (e.g. anat, ieeg etc.).
		:type kind: string
		:param output_path: Path to where the file is to be saved.
		:type output_path: string
		:param make_dir: Make the directory
		:type make_dir: boolean
		:param overwrite: If duplicate data is present in the output directory overwrite it.
		:type overwrite: boolean
		
		:return path: BIDsified folder path.
		:type path: string
		
		"""
		path = []
		path.append(subject_id)
			
		if isinstance(session_id, str):
			if 'ses' not in session_id:
				path.append('ses-%s' % session_id)
			else:
				path.append(session_id)
				
		if isinstance(kind, str):
			path.append(kind)
		
		path = os.path.join(*path)  
		path = os.path.join(output_path, path)
			
		if make_dir == True:
			if not os.path.exists(path):
				os.makedirs(path)
			elif not overwrite:
				os.makedirs(path)
				
		return path
	
	def _dataset_json(self, dataset_fname):
		"""
		Constructs a dataset description JSON file.
		
		:param dataset_fname: Filename for the BIDS dataset description.
		:type dataset_fname: string
		
		"""
		info_dataset_json = OrderedDict([
			('Name', self.bids_settings['json_metadata']['DatasetName']),
			('BIDSVersion', ''),
			('License', ''),
			('Authors', self.bids_settings['json_metadata']['Experimenter'][0]),
			('Acknowledgements', 'say here what are your acknowledgments'),
			('HowToAcknowledge', 'say here how you would like to be acknowledged'),
			('Funding', ["list your funding sources"]),
			('ReferencesAndLinks', ["a data paper", "a resource to be cited when using the data"]),
			('DatasetDOI', '')])
		
		self._write_json(info_dataset_json, dataset_fname)
	
	def _participants_json(self, participants_fname):
		"""
		Constructs a participant description JSON file.
		
		:param participants_fname: Filename for the BIDS participant description.
		:type participants_fname: string
		
		"""
		info_participant_json = OrderedDict([
			('age', 
					 {'Description': 'age of the participants.', 
					  'Units': 'years.'}),
			('sex', 
					 {'Description': 'sex of the participants.', 
					  'Levels': {'m': 'male',
								  'f': 'female'}}),
			('group', 
					 {'Description': 'group the patient belongs to', 
					  })
			])
	
		self._write_json(info_participant_json, participants_fname)
		
	def _participants_data(self, subject_id, file_info_sub, participants_fname):
		"""
		Constructs a participant tsv file.
		
		:param subject_id: Subject identifier.
		:type subject_id: string or None
		:param file_info_sub: File header information from subjects recordings.
		:type file_info_sub: dictionary
		:param participants_fname: Filename for the BIDS participant description.
		:type participants_fname: string
		
		"""
		if subject_id is None:
			with open(participants_fname, 'w') as writeFile:
				writeFile.write("\t".join(['participant_id','age','sex','group']))
				writeFile.write( "\n" )
				
		else:
			# Parse edf files for age and gender (not all files will contain this info)
			age = []
			gender = []
			for ifile in file_info_sub:
				if isinstance(ifile['Age'], int):
					age = ifile['Age']
				if isinstance(ifile['Gender'], str):
					gender = ifile['Gender']
	
			df = pd.DataFrame(OrderedDict([
							  ('participant_id', subject_id if subject_id is not None else ''),
							  ('age', age if age else 'n/a'),
							  ('sex', gender if gender else 'n/a'),
							  ('group', 'patient')]), index= [0])
			
			self._write_tsv(participants_fname, df, overwrite=False, verbose=False, append = True) 
	
	def _scans_json(self, scans_fname):
		"""
		Constructs a scans JSON file containing list of all data files stored in patient directory.
		
		:param scans_fname: Filename for the scans JSON file.
		:type scans_fname: string
		
		"""
		info_scans_json = OrderedDict([
			('duration', 
					 {'Description': 'total duration of the recording.', 
					  'Units': 'hours.'}),
			('edf_type', 
					 {'Description': 'type of EDF file.', 
					  'Units': 'EDF+D or EDF+C.'})
			])
	
		self._write_json(info_scans_json, scans_fname)
		
	def _scans_data(self, file_name, file_info_run, scans_fname, date_offset):
		"""
		Constructs a scans tsv file containing list of all data files stored in patient directory.
		
		:param file_name: Filename for the specific recording.
		:type file_name: string
		:param file_info_run: File header information for specific recording.
		:type file_info_run: dictionary
		:param scans_fname: Filename for the scans tsv file.
		:type scans_fname: string
		
		"""
		date = datetime.datetime.strptime(file_info_run['Date'], '%Y-%m-%d')
		if date_offset:
			date = date - datetime.timedelta(5856)
		acq_time = 'T'.join([date.strftime('%Y-%m-%d'), file_info_run['Time']])
		
		df = pd.DataFrame(OrderedDict([
					  ('filename', file_name),
					  ('acq_time', acq_time),
					  ('duration', file_info_run['TotalRecordTime']),
					  ('edf_type', file_info_run['EDF_type'])
					  ]), index=[0])
		
		self._write_tsv(scans_fname, df, overwrite=False, verbose=False, append = True)        
		
	def _electrodes_data(self, file_info_run, electrodes_fname, coordinates=None, electrode_imp=None, overwrite=False, verbose=False):
		"""
		Constructs a tsv file containing electrode information for recording.
		
		:param file_info_run: File header information for specific recording.
		:type file_info_run: dictionary
		:param electrodes_fname: Filename for the electrode tsv file.
		:type electrodes_fname: string
		:param coordinates: List of electrode coordinates (x,y,z).
		:type coordinates: list or None
		:param electrode_imp: Lst of electrode impedances.
		:type electrode_imp: list or None
		:param overwrite: If duplicate data is present in the output directory overwrite it.
		:type overwrite: boolean
		:param verbose: Print out process steps.
		:type verbose: boolean
		
		"""
		include_chans = ['SEEG','EEG']
		chan_idx = [i for i, x in enumerate(list(file_info_run['ChanInfo'].keys())) if x in include_chans]
		mainDF = pd.DataFrame([])
		for ichan in range(len(chan_idx)):
			info_temp = file_info_run['ChanInfo'][list(file_info_run['ChanInfo'].keys())[chan_idx[ichan]]]
			
			if 'SEEG' in info_temp['Type']:
				values = []
				material = []
				manu = []
				size = []
				typ = []
				for item in info_temp['ChanName']:
					value_temp = 'n/a'
					if [x for x in file_info_run['Groups'] if item.startswith(x)]:
						value_temp = [x for x in file_info_run['Groups'] if item.startswith(x)][0]
					values.append(value_temp)
					material.append(self.bids_settings['natus_info']['iEEGElectrodeInfo']['Material'])
					manu.append(self.bids_settings['natus_info']['iEEGElectrodeInfo']['Manufacturer'])
					size.append(self.bids_settings['natus_info']['iEEGElectrodeInfo']['Diameter'])
					typ.append('depth')
			elif 'EEG' in info_temp['Type']:
				values = []
				material = []
				manu = []
				size = []
				typ = []
				for item in info_temp['ChanName']:
					value_temp = 'n/a'
					if [x for x in file_info_run['Groups'] if item.startswith(x)]:
						value_temp = [x for x in file_info_run['Groups'] if item.startswith(x)][0]
					
					values.append(value_temp)
					material.append(self.bids_settings['natus_info']['EEGElectrodeInfo']['Material'])
					manu.append(self.bids_settings['natus_info']['EEGElectrodeInfo']['Manufacturer'])
					size.append(self.bids_settings['natus_info']['EEGElectrodeInfo']['Diameter'])
					typ.append('scalp')
					
			else:
				values = np.repeat('n/a', len(info_temp['ChanName']))
				material = np.repeat('n/a', len(info_temp['ChanName']))
				manu = np.repeat('n/a', len(info_temp['ChanName']))
				size = np.repeat('n/a', len(info_temp['ChanName']))
				typ = np.repeat('n/a', len(info_temp['ChanName']))
	
			df = pd.DataFrame(OrderedDict([
						  ('name', info_temp['ChanName']),
						  ('x', coordinates[0] if coordinates is not None else 'n/a'),
						  ('y', coordinates[1] if coordinates is not None else 'n/a'),
						  ('z', coordinates[2] if coordinates is not None else 'n/a'),
						  ('size', size),
						  ('type', typ),
						  ('material', material),
						  ('manufacturer', manu)]))
			
			mainDF = pd.concat([mainDF, df], ignore_index = True, axis = 0) 
			
		df_electrodes = []
		for key, val in mainDF.items():
			if val is not None:
				df_electrodes.append((key, val))
				
		df_electrodes = pd.DataFrame(OrderedDict(df_electrodes))
		
		self._write_tsv(electrodes_fname, df_electrodes, overwrite, verbose, append = True)
	
	def _channels_data(self, file_info_run, channels_fname, overwrite=False, verbose=False):
		"""
		Constructs a tsv file containing channel information for recording.
		
		:param file_info_run: File header information for specific recording.
		:type file_info_run: dictionary
		:param channels_fname: Filename for the channels tsv file.
		:type channels_fname: string
		:param overwrite: If duplicate data is present in the output directory overwrite it.
		:type overwrite: boolean
		:param verbose: Print out process steps.
		:type verbose: boolean
		
		"""
		include_chans = ['SEEG','EEG']
		chan_idx = [i for i, x in enumerate(list(file_info_run['ChanInfo'].keys())) if x in include_chans]
		mainDF = pd.DataFrame([])
		for ichan in chan_idx:
			info_temp = file_info_run['ChanInfo'][list(file_info_run['ChanInfo'].keys())[ichan]]
			
			if 'SEEG' in info_temp['Type']:
				values = []
				for item in info_temp['ChanName']:
					value_temp = 'n/a'
					if [x for x in file_info_run['Groups'] if item.startswith(x)]:
						value_temp = [x for x in file_info_run['Groups'] if item.startswith(x)][0]
					values.append(value_temp)
					
			elif 'EEG' in info_temp['Type']:
				values = []
				for item in info_temp['ChanName']:
					value_temp = 'n/a'
					if [x for x in file_info_run['Groups'] if item.startswith(x)]:
						value_temp = [x for x in file_info_run['Groups'] if item.startswith(x)][0]
					
					values.append(value_temp)
			else:
				values = np.repeat('n/a', len(info_temp['ChanName']))
	
			df = pd.DataFrame(OrderedDict([
						  ('name', info_temp['ChanName']),
						  ('type', np.repeat(info_temp['Type'], len(info_temp['ChanName']))),
						  ('units', info_temp['Unit']),
						  ('low_cutoff', np.repeat(file_info_run['Lowpass'] if file_info_run['Lowpass'] is not None else 'n/a', len(info_temp['ChanName']))),
						  ('high_cutoff', np.repeat(file_info_run['Highpass'] if file_info_run['Highpass'] is not None else 'n/a', len(info_temp['ChanName']))),
						  ('sampling_frequency', np.repeat(file_info_run['SamplingFrequency'], len(info_temp['ChanName']))),
						  ('notch', np.repeat('n/a',len(info_temp['ChanName']))),
						  ('reference', np.repeat('n/a',len(info_temp['ChanName']))),
						  ('group', values)]))
			
			mainDF = pd.concat([mainDF, df], ignore_index = True, axis = 0) 
		
		mainDF['units'] = mainDF['units'].str.replace('uV', 'μV')
		self._write_tsv(channels_fname, mainDF, overwrite, verbose, append = False)
	
	def _annotations_data(self, file_info_run, annotation_fname, data_fname, source_name, overwrite, verbose):
		"""
		Constructs an annotations data tsv file about patient specific events from edf file.
		
		:param file_info_run: File header information for specific recording.
		:type file_info_run: dictionary
		:param annotation_fname: Filename for the annotations tsv file.
		:type annotation_fname: string
		:param data_fname: Path to the raw data file for specific recording.
		:type data_fname: string
		:param overwrite: If duplicate data is present in the output directory overwrite it.
		:type overwrite: boolean
		:param verbose: Print out process steps.
		:type verbose: boolean
		
		"""
		file_in = EDFReader(data_fname)
		annotation_data = file_in.extract_annotations(deidentify=True)
		
		annotation_data.to_csv(annotation_fname, sep='\t', index=False, na_rep='n/a', line_terminator="")
	
	def _sidecar_json(self, file_info_run, sidecar_fname, session_id, overwrite=False, verbose=False):
		"""
		Constructs a sidecar JSON file containing information about specific recording.
		
		:param file_info_run: File header information for specific recording.
		:type file_info_run: dictionary
		:param sidecar_fname: Filename for thesidecar JSON file.
		:type sidecar_fname: string
		:param overwrite: If duplicate data is present in the output directory overwrite it.
		:type overwrite: boolean
		:param verbose: Print out process steps.
		:type verbose: boolean
		
		"""
		if 'iEEG' in file_info_run['RecordingType']:
			electrode_manu = self.bids_settings['natus_info']['iEEGElectrodeInfo']['Manufacturer']
		elif 'Scalp' in file_info_run['RecordingType']:
			electrode_manu = self.bids_settings['natus_info']['EEGElectrodeInfo']['Manufacturer']
		else:
			electrode_manu = 'n/a'
		
		if 'Full' in file_info_run['RecordingLength']:
			task_name = 'full'
		elif 'Clip' in file_info_run['RecordingLength']:
			task_name = 'clip'
		elif 'CS' in file_info_run['RecordingLength']:
			task_name = 'stim'
								
		if 'Ret' in file_info_run['Retro_Pro']:
			task_name = task_name + 'ret'
		
		info_sidecar_json = OrderedDict([
			('TaskName', task_name),
			('InstitutionName', self.bids_settings['json_metadata']['InstitutionName']),
			('InstitutionAddress', self.bids_settings['json_metadata']['InstitutionAddress']),
			('Manufacturer', self.bids_settings['natus_info']['Manufacturer']),
			('ManufacturersModelName', self.bids_settings['natus_info']['ManufacturersModelName']),
			('SamplingFrequency', file_info_run['SamplingFrequency']),
			('HardwareFilters', 
					 {'HighpassFilter': {"Cutoff (Hz)": file_info_run['Highpass'] if file_info_run['Highpass'] is not None else 'n/a'}, 
					  'LowpassFilter': {"Cutoff (Hz)": file_info_run['Lowpass'] if file_info_run['Lowpass'] is not None else 'n/a'}}),
			('SoftwareFilters', 'n/a'),
			('EEGChannelCount', file_info_run['ChanInfo']['EEG']['ChannelCount'] if 'EEG' in list(file_info_run['ChanInfo'].keys()) else 0),
			('EOGChannelCount', file_info_run['ChanInfo']['EOG']['ChannelCount'] if 'EOG' in list(file_info_run['ChanInfo'].keys()) else 0),
			('ECGChannelCount', file_info_run['ChanInfo']['ECG']['ChannelCount'] if 'ECG' in list(file_info_run['ChanInfo'].keys()) else 0),
			('EMGChannelCount', file_info_run['ChanInfo']['EMG']['ChannelCount'] if 'EMG' in list(file_info_run['ChanInfo'].keys()) else 0),
			('ECOGChannelCount', file_info_run['ChanInfo']['ECOG']['ChannelCount'] if 'ECOG' in list(file_info_run['ChanInfo'].keys()) else 0),
			('SEEGChannelCount', file_info_run['ChanInfo']['SEEG']['ChannelCount'] if 'SEEG' in list(file_info_run['ChanInfo'].keys()) else 0),
			('MiscChannelCount', file_info_run['ChanInfo']['MISC']['ChannelCount'] if 'MISC' in list(file_info_run['ChanInfo'].keys()) else 0),
			('TriggerChannelCount', file_info_run['ChanInfo']['TRIG']['ChannelCount'] if 'TRIG' in list(file_info_run['ChanInfo'].keys()) else 0),
			('PowerLineFrequency', self.bids_settings['natus_info']['PowerLineFrequency']),
			('RecordingDuration', file_info_run['TotalRecordTime']),
			('RecordingType', 'continuous'),
			('SubjectArtefactDescription', ''),
			('iEEGPlacementScheme', ''),
			('iEEGElectrodeGroups', ''),
			('iEEGReference', ''),
			('ElectrodeManufacturer', electrode_manu),
			('ElectricalStimulationParameters', '')])
		
		if file_info_run['RecordingType'] == 'Scalp':
			info_sidecar_json['EEGPlacementScheme'] = info_sidecar_json.pop('iEEGPlacementScheme')
			info_sidecar_json['EEGReference'] = info_sidecar_json.pop('iEEGReference')
			del info_sidecar_json['SEEGChannelCount']
			del info_sidecar_json['iEEGElectrodeGroups']
			del info_sidecar_json['ECOGChannelCount']
			del info_sidecar_json['ElectrodeManufacturer']
			del info_sidecar_json['ElectricalStimulationParameters']
			
		self._write_json(info_sidecar_json, sidecar_fname, overwrite, verbose)
			
	def get_file_info(self, raw_file_path):
		"""
		Extract header data from EDF file.
		
		:param raw_file_path: Path to the raw data file for specific recording.
		:type raw_file_path: string
		
		:return filesInfo: Dictionary containing header information for all files in specified path.
		:type filesInfo: dictionary
		
		"""
		file_list = [x for x in os.listdir(raw_file_path) if x.endswith('.edf')]
		sub_dir = False
		if not file_list:
			folders = [x for x in os.listdir(raw_file_path) if os.path.isdir(os.path.join(raw_file_path, x))]
			sub_dir=True
			for ifold in folders:
				files = [x for x in os.listdir(os.path.join(raw_file_path, ifold)) if x.lower().endswith('.edf')]
				if len(files)==1:
					file_list.append(os.path.sep.join([ifold, files[0]]))
					
		chan_label_filename = [x for x in os.listdir(raw_file_path) if 'channel_label' in x]
		if chan_label_filename:
			chan_label_file_temp = np.genfromtxt(os.path.join(raw_file_path, chan_label_filename[0]), dtype='str')
		
		filesInfo = []
		for ises in file_list:
			filesInfo_ses = []
			for ifile in ises:
				try:
					filen = os.path.join(raw_file_path, ifile)
					file_in = EDFReader()
					header = file_in.open(filen)
					
					chan_label_file_ses = []
					if sub_dir:
						chan_label_file_ses = [x for x in os.listdir(os.path.dirname(filen)) if 'channel_label' in x]
					
					if not chan_label_file_ses:
						if chan_label_filename:
							values = partition(chan_label_file_temp[:,1])
							chan_label_file = chan_label_file_temp[:,1]
						else:
							chan_label_file = header['chan_info']['ch_names']
							values = partition(header['chan_info']['ch_names'])
					else:
						chan_label_file_ses_temp = np.genfromtxt(os.path.join(os.path.dirname(filen), chan_label_file_ses[0]), dtype='str')
						values = partition(chan_label_file_ses_temp[:,1])
						chan_label_file = chan_label_file_ses_temp[:,1]
						
					eeg_chan_idx = [i for i, x in enumerate(values) if x[0] not in list(self.bids_settings['natus_info']['ChannelInfo'].keys())]
					group_info = determine_groups(np.array(chan_label_file)[eeg_chan_idx])
					
					file_info = [
							('FileName', ifile),
							('SubDir', raw_file_path.split(os.path.sep)[-1]),
							('DisplayName', ifile if not sub_dir else ifile.split(os.path.sep)[0]),
							('Subject', header['meas_info']['subject_id']),
							('Gender', header['meas_info']['gender']),
							('Age', int(np.floor(((datetime.datetime.strptime(header['meas_info']['meas_date'].split(' ')[0],"%Y-%m-%d") 
									- datetime.datetime.strptime(datetime.datetime.strptime(header['meas_info']['birthdate'],
									'%d-%b-%Y').strftime('%Y-%m-%d'),"%Y-%m-%d")).days)/365)) if header['meas_info']['birthdate'] != 'X' else 'X'),
							('Birthdate', header['meas_info']['birthdate']),
							('RecordingID', header['meas_info']['recording_id']),
							('Date', header['meas_info']['meas_date'].split(' ')[0]),
							('Time', header['meas_info']['meas_date'].split(' ')[1]),
							('DataOffset', header['meas_info']['data_offset']),
							('NRecords', header['meas_info']['n_records']),
							('RecordLength', header['meas_info']['record_length']),
							('TotalRecordTime', round((((header['meas_info']['n_records']*(header['meas_info']['sampling_frequency']*header['meas_info']['record_length']))/header['meas_info']['sampling_frequency'])/60)/60,3)),
							('NChan', header['meas_info']['nchan']),
							('SamplingFrequency', header['meas_info']['sampling_frequency']),
							('Highpass', header['meas_info']['highpass']),
							('Lowpass', header['meas_info']['lowpass']),
							('Groups', group_info),
							('EDF_type', header['meas_info']['subtype']),
							('ses_chan_label', chan_label_file_ses)]
					
					file_info = OrderedDict(file_info)
						
					if file_info['DisplayName'].lower().endswith('.edf'):
						if file_info['NChan'] < 60:
							file_info['RecordingType'] = 'Scalp'
						else:
							file_info['RecordingType'] = 'iEEG'
						
						if file_info['TotalRecordTime'] < 5:
							file_info['RecordingLength'] = 'Clip'
						else:
							file_info['RecordingLength'] = 'Full'
						
						file_info['Retro_Pro'] = 'Pro'
					else:
						if 'ieeg' in file_info['DisplayName'].lower():
							file_info['RecordingType'] = 'iEEG'
						else:
							file_info['RecordingType'] = 'Scalp'
							
						if 'cs' in file_info['DisplayName'].lower():
							file_info['RecordingLength'] = 'CS'
						elif 'full' in file_info['DisplayName'].lower():
							file_info['RecordingLength'] = 'Full'
						elif 'clip' in file_info['DisplayName'].lower():
							file_info['RecordingLength'] = 'Clip'
					
						if 'ret' in file_info['DisplayName'].lower():
							file_info['Retro_Pro'] = 'Ret'
						else:
							file_info['Retro_Pro'] = 'Pro'
							
					if file_info['RecordingType'] == 'Scalp':
						chan_type = 'EEG'
					elif file_info['RecordingType'] == 'iEEG':
						chan_type = 'SEEG'
						
					ch_info = {}
					ch_info[chan_type] = OrderedDict([
						('ChannelCount', len(eeg_chan_idx)),
						('Unit', np.array(header['meas_info']['units'])[eeg_chan_idx]),
						('ChanName', np.array(chan_label_file)[eeg_chan_idx]),
						('Type', chan_type)])
					
					for key in self.bids_settings['natus_info']['ChannelInfo'].keys():
						chan_idx = [i for i, x in enumerate(values) if x[0] == key]
						ch_info[key] = OrderedDict([
								('ChannelCount', len(chan_idx)),
								('Unit', np.array(header['meas_info']['units'])[chan_idx]),
								('ChanName', np.array(chan_label_file)[chan_idx]),
								('Type', self.bids_settings['natus_info']['ChannelInfo'][key]['name'])])
					
					file_info['ChanInfo'] = OrderedDict(ch_info)
					file_info = OrderedDict(file_info)
				
					filesInfo_ses.append(file_info)
				except:
					print('Something wrong with file', ifile)
			
			filesInfo.append([filesInfo_ses, {'Date': filesInfo_ses[0]['Date'], 'Time': filesInfo_ses[0]['Time']}])
		
		filesInfo = sorted(filesInfo, key = lambda i: (i[1]['Date'], i[1]['Time']))
		filesInfo = [x[0] for x in filesInfo]
		
		return filesInfo

	def read_input_dir(self, input_dir):
		"""
		Reads data within the specified path.
		
		:param input_dir: Directory to read data files from.
		:type input_dir: string
		
		:return sub_file_info: Dictionary containing header information for all files in specified path.
		:type sub_file_info: dictionary
		
		"""
		folders = [x for x in os.listdir(input_dir) if os.path.isdir(os.path.join(input_dir,x))]
		folders = sorted_nicely([x for x in folders])
		
		sub_file_info = {}
		for ifold in folders:
			subject_id = ifold.replace('_','')
			if not subject_id.startswith('sub-'):
				subject_id = 'sub-' + subject_id
				
			raw_file_path = os.path.join(input_dir, ifold)
			file_info = self.get_file_info(raw_file_path)
			
			sub_file_info[subject_id] = file_info
			
		return sub_file_info
	
	def read_output_dir(self, output_path, file_info, offset_date, participants_fname):
		"""
		Reads data within the specified output path.
		
		:param output_path: Output directory to read data files from.
		:type output_path: string
		:param file_info: File header information from input directory path.
		:type file_info: dictionary
		:param participants_fname: Filename for the participants tsv file.
		:type participants_fname: string
		
		:return new_sessions: Dictionary identifying if there are new sessions to process (comparing input to output).
		:type sub_file_info: dictionary
		
		"""
		folders = [x for x in os.listdir(output_path) if os.path.isdir(os.path.join(output_path,x)) and 'code' not in x]
		new_sessions = {}
		
		for isub, values in file_info.items():
			num_sessions = len(values)
			newSessions = True
			session_start = 0
			session_labels = np.nan
			sub_sessions = {}
			session_list = []
			all_labels = []
			
			# True if subject directory already in output directory
			if isub in folders:
				sessionsDone = sorted_nicely([x for x in os.listdir(os.path.join(output_path, isub)) if x.startswith('ses')])
				print(isub)
				# Determine if new sessions to run, and where to begin
				if os.path.exists(os.path.join(output_path, isub, isub + '_scans.tsv')):
					# Load output scan file
					scans_tsv = pd.read_csv(os.path.join(output_path, isub, isub + '_scans.tsv'), sep='\t')
					sessionsDone = {}
					sessionsDone['date'] = [x for x in scans_tsv['acq_time']]
					sessionsDone['session'] = ['ses' + x.split('ses')[-1].split('_')[0] for x in scans_tsv['filename']]
					
					session_time = []
					session_dates = []
					session_labels = []
					if '_SE' not in values[0][0]['DisplayName']:
						sess_cnt = [int(s) for s in re.findall(r'\d+', sessionsDone['session'][-1])][0]
					
					for ises in range(len(values)):
						if offset_date:
							date_study = datetime.datetime.strptime(values[ises][0]['Date'],"%Y-%m-%d")
							date_study = (date_study - datetime.timedelta(5856)).strftime('%Y-%m-%d')
						else:
							date_study = values[ises][0]['Date']
						
						if '_SE' in values[ises][0]['DisplayName']:
							if ''.join([date_study,'T', values[ises][0]['Time']]) not in scans_tsv['acq_time'].values:
								visit_num = 'V'+ values[ises][0]['DisplayName'].split('_')[3]
								session_num = values[ises][0]['DisplayName'].split('_')[4]
								session_labels.append('ses-' + visit_num + session_num)
								session_dates.append(date_study)
								session_time.append(values[ises][0]['Time'])
						else:
							if ''.join([date_study,'T', values[ises][0]['Time']]) not in scans_tsv['acq_time'].values:
								sess_cnt +=1
								session_labels.append('ses-' + str(sess_cnt).zfill(3))
								session_dates.append(date_study)
								session_time.append(values[ises][0]['Time'])
					
					if session_dates:
						sort_idx = pd.DataFrame({'date': [x.split('T')[0] for x in sessionsDone['date']] + session_dates,
											    'time': [x.split('T')[1] for x in sessionsDone['date']] + session_time,
												'old_sess': sessionsDone['session'] + session_labels}).sort_values(by=['date','time']).index.values
			
						session_combined = pd.DataFrame({'date': [[*[x.split('T')[0] for x in sessionsDone['date']], *session_dates][i] for i in sort_idx],
											'time': [[*[x.split('T')[1] for x in sessionsDone['date']], *session_time][i] for i in sort_idx],
											'old_sess':[*sessionsDone['session'], *session_labels],
											'new_sess': [[*sessionsDone['session'], *session_labels][i] for i in sort_idx]})
						
						session_combined['date'] = session_combined['date'] + 'T' + session_combined['time']
						del session_combined['time']
						
						unique_sessions = session_combined[(~session_combined.date.isin(scans_tsv['acq_time'].values))]
						all_labels = list(session_combined['old_sess'].values)
						session_labels = list(unique_sessions['new_sess'].values)
						num_sessions = len(all_labels)
						if len(values) == len(all_labels):
							session_index = [x for x,i in enumerate(list(np.unique(all_labels))) if i in session_labels]
						else:
							session_index = [x for x,i in enumerate(session_labels) if i in list(np.unique(all_labels))]
						
						session_start = len(set(sessionsDone['session']))
						session_list = list(zip(list(session_combined['old_sess'].values), list(session_combined['new_sess'].values)))
					
					else:
						all_labels = sessionsDone['session']
						session_labels = sessionsDone['session']
						newSessions = False
					
			else:
				session_labels = []
				session_index = list(range(len(values)))
				for ises in range(len(values)):
					if '_SE' in values[ises][0]['DisplayName']:
						visit_num = 'V'+ values[ises][0]['DisplayName'].split('_')[3]
						session_num = values[ises][0]['DisplayName'].split('_')[4]
						session_labels.append('ses-' + visit_num + session_num)
					else:
						session_labels.append('ses-' + str(ises+1).zfill(3))
				
				all_labels = session_labels
				
				if participants_fname is not None:
					self._participants_data(isub, values, participants_fname)
				
			sub_sessions['newSessions'] = newSessions
			sub_sessions['session_done'] = session_start
			sub_sessions['num_sessions'] = num_sessions
			sub_sessions['session_labels'] = session_labels
			sub_sessions['session_index'] = session_index
			sub_sessions['all_sessions'] = all_labels
			sub_sessions['session_changes'] = session_list
			
			new_sessions[isub] = sub_sessions
			
		return new_sessions
	
	def copyLargeFile(self, src, dest, callback, buffer_size=16*1024):
		total_size = os.path.getsize(src)
		update_cnt = int(total_size/10)
		with open(src, 'rb') as fsrc:
			with open(dest, 'wb') as fdest:
				copied = 0
				while 1:
					if not self.userAbort:
						if not self.running:
							break
						else:
							buf = fsrc.read(buffer_size)
							if not buf:
								break
							fdest.write(buf)
							copied += len(buf)
							if update_cnt < copied:
								if update_cnt == int(total_size/10):
									callback.emit('copy{}%'.format(int(np.ceil((update_cnt/total_size)*100))))
								else:
									callback.emit('{}%'.format(int(np.ceil((update_cnt/total_size)*100))))
								update_cnt += int(total_size/10)

				callback.emit('100%')
	
	@QtCore.Slot()
	def run(self):
		"""
		Main loop for building BIDS database.
				
		"""
		if not self.userAbort:
			self.running = True
	
		participants_fname = self.make_bids_filename(None, session_id=None, task_id=None, run_num=None, suffix='participants.tsv', prefix=self.output_path)
		if os.path.exists(participants_fname):
			self.participant_tsv = pd.read_csv(participants_fname, sep='\t')
		while self.running:
			for isub, values in self.new_sessions.items():
				subject_dir = self.file_info[isub][0][0]['SubDir']
				raw_file_path = os.path.join(self.input_path, subject_dir)
				
				if values['newSessions']:
					sessions_fix = [x for x in values['session_changes'] if x[0] != x[1]]
					if sessions_fix:
						fix_sessions(sessions_fix, values['num_sessions'], self.output_path, isub)
					
					for ises in range(len(values['session_labels'])):
						file_data = [self.file_info[isub][ises]]
						session_id = values['session_labels'][ises].split('-')[-1]
						
						if 'Scalp' in file_data[0][0]['RecordingType']:
							data_prefix = 'eeg'
						elif 'iEEG' in file_data[0][0]['RecordingType']:
							data_prefix = 'ieeg'
						
						self.conversionStatusText = '\nStarting conversion: session {} of {} for {} at {}'.format(str(ises+1), str(len(values['session_labels'])), isub, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
						self.progressEvent.emit(self.conversionStatusText)
						
						data_path = self.make_bids_folders(isub, session_id, data_prefix, self.output_path, self.make_dir, self.overwrite)
						
						# Add scans json file for each subject
						sub_path = self.make_bids_folders(isub, None, None, self.output_path, False, False)
						scans_json_fname = self.make_bids_filename(isub, session_id=None, task_id=None, run_num=None, suffix='scans.json', prefix=sub_path)
						if not os.path.exists(scans_json_fname):
							self._scans_json(scans_json_fname)
							
						electrodes_fname = self.make_bids_filename(isub, session_id, task_id=None, run_num=None, suffix='electrodes.tsv', prefix=data_path)
						num_runs = len(file_data[0])
					
						for irun in range(num_runs):
							if 'Full' in file_data[0][irun]['RecordingLength']:
								task_id = 'full'
							elif 'Clip' in file_data[0][irun]['RecordingLength']:
								task_id = 'clip'
							elif 'CS' in file_data[0][irun]['RecordingLength']:
								task_id = 'stim'
							
							if 'Ret' in file_data[0][irun]['Retro_Pro']:
								task_id = task_id + 'ret'
								
							run_num = str(irun+1).zfill(2)
								
							channels_fname = self.make_bids_filename(isub, session_id, task_id, run_num, suffix='channels.tsv', prefix=data_path)
							sidecar_fname = self.make_bids_filename(isub, session_id, task_id, run_num, suffix=data_prefix + '.json', prefix=data_path)
							data_fname = self.make_bids_filename(isub, session_id, task_id, run_num, suffix = data_prefix + '.edf', prefix=data_path)
							scans_fname = self.make_bids_filename(isub, session_id=None, task_id=None, run_num=None, suffix='scans.tsv', prefix=os.path.join(self.output_path, isub))
							
							if not self.test_conversion:
								source_name = os.path.join(raw_file_path, file_data[0][irun]['FileName'])
								if not self.annotations_only:
									if self.deidentify_source:
										source_name, epochLength = deidentify_edf(source_name, isub, self.offset_date, True)
										self.bids_settings['json_metadata']['EpochLength'] = epochLength
										
									self.copyLargeFile(source_name, data_fname, self.progressEvent)
									
									if not self.deidentify_source:
										temp_name, epochLength = deidentify_edf(data_fname, isub, self.offset_date, False)
										self.bids_settings['json_metadata']['EpochLength'] = epochLength
									
									annotation_fname = self.make_bids_filename(isub, session_id, task_id, run_num, suffix='annotations.tsv', prefix=data_path)
									self._annotations_data(file_data[0][irun], annotation_fname, data_fname, source_name, self.overwrite, self.verbose)
								else:
									annotation_fname = self.make_bids_filename(isub, session_id, task_id, run_num, suffix='annotations.tsv', prefix=data_path)
									self._annotations_data(file_data[0][irun], annotation_fname, source_name, source_name, self.overwrite, self.verbose)
							else:
								self.bids_settings['json_metadata']['EpochLength'] = 0
								
							self._scans_data('/'.join(data_fname.split(os.path.sep)[-2:]), file_data[0][irun], scans_fname, self.offset_date)
							
							self._channels_data(file_data[0][irun], channels_fname, overwrite=self.overwrite, verbose=self.verbose)
							self._sidecar_json(file_data[0][irun], sidecar_fname, session_id, overwrite=self.overwrite, verbose=self.verbose)
						
						self._electrodes_data(file_data[0][0], electrodes_fname, coordinates=self.coordinates, electrode_imp=self.electrode_imp, overwrite=self.overwrite, verbose=self.verbose)
						 
						code_output_path = os.path.join(self.output_path, 'code', 'edf2bids')
						code_path = self.make_bids_folders(isub, session_id, None, code_output_path, self.make_dir, self.overwrite)
						
						shutil.copy(os.path.join(self.script_path, 'edf2bids.py'), code_path)
						shutil.copy(os.path.join(self.script_path, 'helpers.py'), code_path)
					
					time.sleep(0.1)
					
					if isub not in list(self.participant_tsv['participant_id']):
						self._participants_data(isub, self.file_info[isub][0], participants_fname)
						self.participant_tsv = pd.read_csv(participants_fname, sep='\t')
				else:
					self.conversionStatusText = 'Participant {} already exists in the dataset! \n'.format(isub)
					self.progressEvent.emit(self.conversionStatusText)
			
			self.running = False





