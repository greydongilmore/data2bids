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

from helpers import EDFReader, bidsHelper, sorted_nicely, partition, determine_groups, fix_sessions, sec2time, deidentify_edf

class WorkerKilledException(Exception):
	pass

class WorkerSignals(QtCore.QObject):
	'''
	Defines the signals available from a running worker thread.

	Supported signals are:

	finished
		No data
	
	error
		`tuple` (exctype, value, traceback.format_exc() )
	
	result
		`object` data returned from processing, anything

	progress
		`int` indicating % progress 

	'''
	finished = QtCore.Signal()
	progressEvent = QtCore.Signal(str)
	
class edf2bids(QtCore.QRunnable):
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
	
	def __init__(self):	
		super(edf2bids, self).__init__()
		
		self.new_sessions = []
		self.file_info = []
		self.chan_label_file = []
		self.input_path = []
		self.output_path = []
		self.script_path = []
		self.coordinates = []
		self.make_dir = []
		self.overwrite = []
		self.verbose = []
		self.deidentify_source = []
		self.offset_date = []
		self.bids_settings = []
		self.test_conversion = []
		self.annotations_only = []
		
		self.signals = WorkerSignals()
		
		self.running = False
		self.userAbort = False
		self.is_killed = False
		
	def stop(self):
		self.running = False
		self.userAbort = True
	
	def kill(self):
		self.is_killed = True
	
	def write_annotations(self, data, data_fname, deidentify=False):
		self._annotations_data(data, data_fname, deidentify)
	
	def _read_annotations_apply_offset(self, triggers):
		events = []
		offset = 0.
		for k, ev in enumerate(triggers):
			onset = float(ev[0]) + offset
			duration = float(ev[2]) if ev[2] else 0
			for description in ev[3].split('\x14')[1:]:
				if description:
					events.append([onset, duration, description, ev[4]])
				elif k==0:
					# "The startdate/time of a file is specified in the EDF+ header
					# fields 'startdate of recording' and 'starttime of recording'.
					# These fields must indicate the absolute second in which the
					# start of the first data record falls. So, the first TAL in
					# the first data record always starts with +0.X2020, indicating
					# that the first data record starts a fraction, X, of a second
					# after the startdate/time that is specified in the EDF+
					# header. If X=0, then the .X may be omitted."
					offset = -onset
					
		return events if events else list()
	
	def read_annotation_block(self, block, tal_indx):
		pat = '([+-]\\d+\\.?\\d*)(\x15(\\d+\\.?\\d*))?(\x14.*?)\x14\x00'
		assert(block>=0)
		data = []
		with open(self.fname, 'rb') as fid:
			assert(fid.tell() == 0)
			blocksize = np.sum(self.header['chan_info']['n_samps']) * self.header['meas_info']['data_size']
			fid.seek(np.int64(self.header['meas_info']['data_offset']) + np.int64(block) * np.int64(blocksize))
			read_idx = 0
			for i in range(self.header['meas_info']['nchan']):
				read_idx += np.int64(self.header['chan_info']['n_samps'][i]*self.header['meas_info']['data_size'])
				buf = fid.read(np.int64(self.header['chan_info']['n_samps'][i]*self.header['meas_info']['data_size']))
				if i==tal_indx:
					raw = re.findall(pat, buf.decode('latin-1'))
					if raw:
						data.append(list(map(list, [x+(block,) for x in raw])))
			
		return data
	
	def overwrite_annotations(self, events, identity_idx, tal_indx, strings, action):
		pat = '([+-]\\d+\\.?\\d*)(\x15(\\d+\\.?\\d*))?(\x14.*?)\x14\x00'
		indexes = []
		for ident in identity_idx:
			block_chk = events[ident][-1]
			if isinstance(strings, dict):
				replace_idx = [i for i,x in enumerate(strings.keys()) if x.lower() in events[ident][2].lower()]
			else:
				replace_idx = [i for i,x in enumerate(strings) if x.lower() in events[ident][2].lower()]
			for irep in replace_idx:
				assert(block_chk>=0)
				new_block=[]
				with open(self.fname, 'rb') as fid:
					assert(fid.tell() == 0)
					blocksize = np.sum(self.header['chan_info']['n_samps']) * self.header['meas_info']['data_size']
					fid.seek(np.int64(self.header['meas_info']['data_offset']) + np.int64(block_chk) * np.int64(blocksize))
					for i in range(self.header['meas_info']['nchan']):
						buf = fid.read(np.int64(self.header['chan_info']['n_samps'][i]*self.header['meas_info']['data_size']))
						if i==tal_indx:
							if action == 'replace':
								new_block = buf.lower().replace(bytes(strings[irep],'latin-1').lower(), bytes(''.join(np.repeat('X', len(strings[irep]))),'latin-1'))
								events[ident][2] = events[ident][2].lower().replace(strings[irep].lower(), ''.join(np.repeat('X', len(strings[irep]))))
								assert(len(new_block)==len(buf))
							
							elif action == 'replaceWhole':
								_idx = [i for i,x in enumerate(strings.keys()) if x.lower() in events[ident][2].lower()]
								replace_string = list(strings.values())[_idx[0]]
								new_block = buf.lower().replace(bytes(events[ident][2],'latin-1').lower(), bytes(replace_string,'latin-1'))
								events[ident][2] = replace_string
								new_block = new_block+bytes('\x00'*(len(buf)-len(new_block)),'latin-1')
								assert(len(new_block)==len(buf))
							
							elif action == 'remove':
								raw = re.findall(pat, buf.decode('latin-1'))[0][0] +'\x14\x14'
								new_block = bytes(raw + ('\x00'*(len(buf)-len(raw))),'latin-1')
								indexes.append(ident)
								assert(len(new_block)==len(buf))
								
				if new_block:
					with open(self.fname, 'r+b') as fid:
						assert(fid.tell() == 0)
						blocksize = np.sum(self.header['chan_info']['n_samps']) * self.header['meas_info']['data_size']
						fid.seek(np.int64(self.header['meas_info']['data_offset']) + np.int64(block_chk) * np.int64(blocksize))
						read_idx = 0
						for i in range(self.header['meas_info']['nchan']):
							read_idx += np.int64(self.header['chan_info']['n_samps'][i]*self.header['meas_info']['data_size'])
							buf = fid.read(np.int64(self.header['chan_info']['n_samps'][i]*self.header['meas_info']['data_size']))
							if i==tal_indx:
								back = fid.seek(-np.int64(self.header['chan_info']['n_samps'][i]*self.header['meas_info']['data_size']), 1)
								assert(fid.tell()==back)
								fid.write(new_block)
		
		if indexes:
			for index in sorted(indexes, reverse=True):
				del events[index]
		
		return events
	
	def _annotations_data(self, file_info_run, data_fname, deidentify):
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
		self.fname=data_fname
		
		file_in = EDFReader()
		file_in.open(data_fname)
		self.header = file_in.readHeader()
		
		overwrite_strings = [self.header['meas_info']['firstname'], self.header['meas_info']['lastname']]
		overwrite_strings = [x for x in overwrite_strings if x is not None]
		overwrite_whole={
						'montage': 'Montage Event'
						}
		remove_strings = ['XLSPIKE','XLEVENT']
	
		tal_indx = [i for i,x in enumerate(self.header['chan_info']['ch_names']) if x.endswith('Annotations')][0]
		
		start_time = 0
		end_time = self.header['meas_info']['n_records']*self.header['meas_info']['record_length']
		
		begsample = int(self.header['meas_info']['sampling_frequency']*float(start_time))
		endsample = int(self.header['meas_info']['sampling_frequency']*float(end_time))
		
		n_samps = max(set(list(self.header['chan_info']['n_samps'])), key = list(self.header['chan_info']['n_samps']).count)
		
		begblock = int(np.floor((begsample) / n_samps))
		endblock = int(np.floor((endsample) / n_samps))
		
		update_cnt = int((endblock+1)/10)
		annotations = []
		for block in range(begblock, endblock):
			if self.is_killed:
				self.running = False
				raise WorkerKilledException
			else:
				data_temp = self.read_annotation_block(block, tal_indx)
				if data_temp:
						annotations.append(data_temp[0])
				if block == update_cnt and block < (endblock-(int((endblock+1)/20))):
					self.signals.progressEvent.emit('{}%'.format(int(np.ceil((update_cnt/endblock)*100))))
					update_cnt += int((endblock+1)/10)
		
		self.signals.progressEvent.emit('annot100%')
		events = self._read_annotations_apply_offset([item for sublist in annotations for item in sublist])
		
		if deidentify:
			if overwrite_strings:
				### Replace any identifier strings
				identity_idx = [i for i,x in enumerate(events) if any(substring.lower() in x[2].lower() for substring in overwrite_strings) and 'montage' not in x[2].lower()]
				if identity_idx:
					events = self.overwrite_annotations(events, identity_idx, tal_indx, overwrite_strings, 'replace')
			
			if overwrite_whole:
				identity_idx = [i for i,x in enumerate(events) if any(substring.lower() in x[2].lower() for substring in overwrite_whole.keys()) and not any(substring.lower() == x[2].lower() for substring in list(overwrite_whole.values()))]
				if identity_idx:
					events = self.overwrite_annotations(events, identity_idx, tal_indx, overwrite_whole, 'replaceWhole')
		
			if remove_strings:
				### Remove unwanted annoations
				identity_idx = [i for i,x in enumerate(events) if any(substring.lower() == x[2].lower() for substring in remove_strings)]
				if identity_idx:
					events = self.overwrite_annotations(events, identity_idx, tal_indx, remove_strings, 'remove')
		
		annotation_data = pd.DataFrame({})
		if events:
			fulldate = datetime.datetime.strptime(self.header['meas_info']['meas_date'], '%Y-%m-%d %H:%M:%S')
			for i, annot in enumerate(events):
				data_temp = {'onset': annot[0],
							 'duration': annot[1],
							 'time_abs': (fulldate + datetime.timedelta(seconds=annot[0]+float(self.header['meas_info']['millisecond']))).strftime('%H:%M:%S.%f'),
							 'time_rel': sec2time(annot[0], 6),
							 'event': annot[2]}
				annotation_data = pd.concat([annotation_data, pd.DataFrame([data_temp])], axis = 0)
			
		annotation_data.to_csv(self.annotation_fname, sep='\t', index=False, na_rep='n/a', line_terminator="", float_format='%.3f')
	
	def copyLargeFile(self, src, dest, callback, buffer_size=16*1024):
		total_size = os.path.getsize(src)
		update_cnt = int(total_size/10)
		with open(src, 'rb') as fsrc:
			with open(dest, 'wb') as fdest:
				copied = 0
				while 1:
					if self.is_killed:
						self.running = False
						raise WorkerKilledException
					else:
						buf = fsrc.read(buffer_size)
						if not buf:
							break
						fdest.write(buf)
						copied += len(buf)
						if update_cnt < copied:
							if update_cnt == int(total_size/10):
								callback.emit('copy{}%'.format(int(np.ceil((update_cnt/total_size)*100))))
							elif copied < (total_size-(int((total_size)/20))):
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
		
		participants_fname = bidsHelper(output_path=self.output_path).write_participants(return_fname=True)
		if os.path.exists(participants_fname):
			self.participant_tsv = pd.read_csv(participants_fname, sep='\t')
			
		try:
			for isub, values in self.new_sessions.items():
				subject_dir = self.file_info[isub][0][0]['SubDir']
				raw_file_path = os.path.join(self.input_path, subject_dir)
				
				if self.is_killed:
					self.running = False
					raise WorkerKilledException
					
				if values['newSessions']:
					sessions_fix = [x for x in values['session_changes'] if x[0] != x[1]]
					if sessions_fix:
						fix_sessions(sessions_fix, values['num_sessions'], self.output_path, isub)
					
					for ises in range(len(values['session_labels'])):
						file_data = [self.file_info[isub][ises]]
						session_id = values['session_labels'][ises].split('-')[-1]
						
						if 'Scalp' in file_data[0][0]['RecordingType']:
							kind = 'eeg'
						elif 'iEEG' in file_data[0][0]['RecordingType']:
							kind = 'ieeg'
						
						self.conversionStatusText = '\nStarting conversion: session {} of {} for {} at {}'.format(str(ises+1), str(len(values['session_labels'])), isub, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
						self.signals.progressEvent.emit(self.conversionStatusText)
						
						bids_helper = bidsHelper(subject_id=isub, session_id=session_id, kind=kind, output_path=self.output_path, bids_settings=self.bids_settings, make_sub_dir=True)
# 						bids_helper = bidsHelper(subject_id=isub, session_id=session_id, kind=kind, output_path=output_path, bids_settings=bids_settings, make_sub_dir=True)
						
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
							
							bids_helper.task_id=task_id
							bids_helper.run_num=run_num
							
							data_fname = bids_helper.make_bids_filename(suffix = kind + '.edf')
							
							if not self.test_conversion:
								source_name = os.path.join(raw_file_path, file_data[0][irun]['FileName'])
								self.annotation_fname = bids_helper.make_bids_filename(suffix='annotations.tsv')
								if not self.annotations_only:
									if self.deidentify_source:
										source_name, epochLength = deidentify_edf(source_name, isub, self.offset_date, True)
										self.bids_settings['json_metadata']['EpochLength'] = epochLength
										
									self.copyLargeFile(source_name, data_fname, self.signals.progressEvent)
									
									if not self.deidentify_source:
										temp_name, epochLength = deidentify_edf(data_fname, isub, self.offset_date, False)
										self.bids_settings['json_metadata']['EpochLength'] = epochLength
									
									self.write_annotations(file_data[0][irun], data_fname, deidentify=True)
									
									if file_data[0][irun]['chan_label']:
										file_in = EDFReader()
										file_in.open(data_fname)
										chan_label_file=file_in.chnames_update(os.path.join(raw_file_path, file_data[0][irun]['chan_label'][0]), self.bids_settings, write=True)
									elif file_data[0][irun]['ses_chan_label']:
										file_in = EDFReader()
										file_in.open(data_fname)
										chan_label_file=file_in.chnames_update(os.path.join(raw_file_path, file_data[0][irun]['ses_chan_label'][0]), self.bids_settings, write=True)
								else:
									self.write_annotations(file_data[0][irun], source_name, deidentify=False)
							
							else:
								if self.deidentify_source:
									source_name = os.path.join(raw_file_path, file_data[0][irun]['FileName'])
									source_name, epochLength = deidentify_edf(source_name, isub, self.offset_date, True)
									self.bids_settings['json_metadata']['EpochLength'] = epochLength
								else:
									self.bids_settings['json_metadata']['EpochLength'] = 0
							
							bids_helper.write_scans(data_fname.split(isub+os.path.sep)[-1], file_data[0][irun], self.offset_date)
							
							bids_helper.write_channels(file_data[0][irun])
							bids_helper.write_sidecar(file_data[0][irun])
						
						bids_helper.write_electrodes(file_data[0][0], coordinates=None)
						
						code_output_path = os.path.join(self.output_path, 'code', 'edf2bids')
						code_path = bids_helper.make_bids_folders(path_override=code_output_path, make_dir=True)
						
						shutil.copy(os.path.join(self.script_path, 'edf2bids.py'), code_path)
						shutil.copy(os.path.join(self.script_path, 'helpers.py'), code_path)
					
						self.conversionStatusText = 'Finished conversion: session {} of {} for {} at {}'.format(str(ises+1), str(len(values['session_labels'])), isub, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
						self.signals.progressEvent.emit(self.conversionStatusText)
					
					time.sleep(0.1)
					
					if isub not in list(self.participant_tsv['participant_id']):
						bids_helper.write_participants(self.file_info[isub][0])
						self.participant_tsv = pd.read_csv(participants_fname, sep='\t')
				else:
					self.conversionStatusText = 'Participant {} already exists in the dataset! \n'.format(isub)
					self.signals.progressEvent.emit(self.conversionStatusText)
			
		except WorkerKilledException:
			self.running = False
			pass
		
		finally:
			self.running = False
			self.signals.finished.emit()





