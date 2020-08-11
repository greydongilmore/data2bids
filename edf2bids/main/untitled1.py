#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Aug 10 00:06:08 2020

@author: greydon
"""
import os
import numpy as np
import pandas as pd
pd.set_option('precision', 6)
import json
from collections import OrderedDict
import sys

class bidsHelper():
	def __init__(self, subject_id=None, session_id=None, task_id=None, run_num=None, kind=None, suffix=None, output_path=None, bids_settings=bids_settings):
		self.subject_id = subject_id
		self.session_id = session_id
		self.task_id = task_id
		self.run_num = run_num
		self.kind = kind
		self.suffix = suffix
		self.output_path = output_path
		self.bids_settings = bids_settings
	
	def write_scans(self, file_name, file_info_run, date_offset):
		# Add scans json file for each subject
		self.scans_fname = self.make_bids_filename(suffix='scans.tsv', path_override=os.path.join(self.output_path,self.subject_id))
		self.scans_json_fname = self.make_bids_filename(suffix='scans.json', path_override=os.path.join(self.output_path,self.subject_id))
		if not os.path.exists(self.scans_json_fname):
			self._scans_json()
		
		self._scans_data(file_name, file_info_run, date_offset)
		
	def write_channels(self, file_info_run, overwrite=False, verbose=False):
		
		self.channels_fname = self.make_bids_filename(suffix='channels.tsv')
		self._channels_data(file_info_run, overwrite, verbose)
	
	def write_sidecar(self, file_info_run, overwrite=False, verbose=False):
		
		self.sidecar_fname = self.make_bids_filename(suffix=self.kind + '.json')
		self._sidecar_json(file_info_run, overwrite, verbose)
	
	def write_electrodes(self, file_info_run, coordinates, overwrite=False, verbose=False):
		
		self.electrodes_fname = self.make_bids_filename(exclude_task=True, exclude_run=True, suffix='electrodes.tsv')
		self._electrodes_data(file_info_run, coordinates, overwrite, verbose)
	
	def write_participants(self, data):
		
		self.participants_fname = self.make_bids_filename(suffix='participants.tsv', exclude_sub=True, exclude_ses=True, 
													exclude_task=True, exclude_run=True, path_override=self.output_path)
		self._participants_data(data)
		
	def _write_tsv(self, fname, data, overwrite=False, verbose=False, append = False):
		"""
		Writes input dataframe to a .tsv file
		
		:param fname: Filename given to the output tsv file.
		:type fname: string
		:param data: Dataframe containing the information to write.
		:type data: dataframe
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
					data.to_csv(f, sep='\t', index=False, header = False, na_rep='n/a', mode='a', line_terminator="")
				with open(fname) as f:
					lines = f.readlines()
					last = len(lines) - 1
					lines[last] = lines[last].replace('\r','').replace('\n','')
				with open(fname, 'w') as wr:
					wr.writelines(lines) 
			else:
				data1 = data.iloc[0:len(data)-1]
				data2 = data.iloc[[len(data)-1]]
				data1.to_csv(fname, sep='\t', encoding='utf-8', index = False)
				data2.to_csv(fname, sep='\t', encoding='utf-8', header= False, index = False, mode='a', line_terminator="")
		else:
			if os.path.exists(fname) and not overwrite:
				pass
			if os.path.exists(fname) and append:
				with open(fname,'a') as f:
					data.to_csv(f, sep='\t', index=False, header = False, na_rep='n/a', mode='a', line_terminator="")
			else:
				data1 = data.iloc[0:len(data)-1]
				data2 = data.iloc[[len(data)-1]]
				data1.to_csv(fname, sep='\t', encoding='utf-8', index = False)
				data2.to_csv(fname, sep='\t', encoding='utf-8', header= False, index = False, mode='a',line_terminator="")

	def _write_json(self, data, fname, overwrite=False, verbose=False):
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
		json_output = json.dumps(data, indent=4)
		with open(fname, 'w') as fid:
			fid.write(json_output)
			fid.write('\n')
	
		if verbose is True:
			print(os.linesep + "Writing '%s'..." % fname + os.linesep)
			print(json_output)
		
	def make_bids_filename(self, suffix, exclude_sub=False, exclude_ses=False, exclude_task=False, exclude_run=False, path_override=None):
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
		if exclude_task:
			ses=None
		elif isinstance(self.session_id, str):
			if 'ses' in self.session_id:
				ses=self.session_id.split('-')[1]
		else:
			ses=self.session_id
			
		if exclude_task:
			task=None
		else:
			task=self.task_id
		
		if exclude_run:
			run=None
		else:
			run=self.run_num
			
		order = OrderedDict([('ses', ses if ses is not None else None),
							 ('task', task if task is not None else None),
							 ('run', run if run is not None else None)])
	
		filename = []
		if not exclude_sub:
			if self.subject_id is not None:
				filename.append(self.subject_id)
				
		for key, val in order.items():
			if val is not None:
				filename.append('%s-%s' % (key, val))
	
		if isinstance(suffix, str):
			filename.append(suffix)
	
		filename = '_'.join(filename)
		if path_override is not None:
			filename = os.path.join(path_override, filename)
		else:
			prefix=self.make_bids_folders()
			filename = os.path.join(prefix, filename)
			
		return filename

	def make_bids_folders(self, path_override=None, make_dir=False, overwrite=False):
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
		path.append(self.subject_id)
			
		if isinstance(self.session_id, str):
			if 'ses' not in self.session_id:
				path.append('ses-%s' % self.session_id)
			else:
				path.append(self.session_id)
		
		if path_override is None:
			if isinstance(self.kind, str):
				path.append(self.kind)
		
		path = os.path.join(*path)
		if path_override is not None:
			path = os.path.join(path_override, path)
		else:
			path = os.path.join(self.output_path, path)
			
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
	
	def _participants_data(self, file_info_sub):
		"""
		Constructs a participant tsv file.
		
		:param subject_id: Subject identifier.
		:type subject_id: string or None
		:param file_info_sub: File header information from subjects recordings.
		:type file_info_sub: dictionary
		:param participants_fname: Filename for the BIDS participant description.
		:type participants_fname: string
		
		"""
		if self.subject_id is None:
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
							  ('participant_id', self.subject_id if self.subject_id is not None else ''),
							  ('age', age if age else 'n/a'),
							  ('sex', gender if gender else 'n/a'),
							  ('group', 'patient')]), index= [0])
			
			self._write_tsv(self.participants_fname, df, overwrite=False, verbose=False, append = True) 

	def _scans_json(self):
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
	
		self._write_json(info_scans_json, self.scans_json_fname)
	
	def _scans_data(self, file_name, file_info_run, date_offset):
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
		
		self._write_tsv(self.scans_fname, df, overwrite=False, verbose=False, append = True)
	
	def _electrodes_data(self, file_info_run, coordinates, overwrite, verbose):
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
		
		self._write_tsv(self.electrodes_fname, df_electrodes, overwrite, verbose, append = True)

	def _channels_data(self, file_info_run, overwrite, verbose):
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
		self._write_tsv(self.channels_fname, mainDF, overwrite, verbose, append = False)
	
	def _sidecar_json(self, file_info_run, overwrite, verbose):
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