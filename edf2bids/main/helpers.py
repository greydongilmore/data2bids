# -*- coding: utf-8 -*-
"""
Created on Thu Jan 10 13:14:21 2019

@author: Greydon
"""
import os
import numpy as np
import pandas as pd
pd.set_option('precision', 6)
import json
import datetime
import warnings
import re
from copy import deepcopy
from struct import pack, unpack
from math import floor
import shutil
import glob
from collections import OrderedDict

def padtrim(buf, num):
	"""
	Adds padding to string data.
	
	:param buf: input string to pad
	:type buf: string
	:param num: Length of desired output buffer.
	:type num: integer

	:return buffer: The input string padded to desired size.
	:type butter: string

	"""
	num -= len(buf)
	if num>=0:
		# pad the input to the specified length
		buffer = (str(buf) + ' ' * num)
	else:
		# trim the input to the specified length
		buffer = (buf[0:num])
	
	return buffer

def sorted_nicely(lst):
	"""
	Sorts the given iterable in the way that is expected.
	
	:param lst: The iterable to be sorted.
	:type lst: list

	:return sorted_lst: The input string padded to desired size.
	:type sorted_lst: list

	"""
	convert = lambda text: int(text) if text.isdigit() else text
	alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
	sorted_lst = sorted(lst, key = alphanum_key)
	
	return sorted_lst

def partition(iterable):
	"""
	Seperates list of strings into alpha and digit.
	
	:param iterable: The iterable to seperated.
	:type iterable: list

	:return values: List of lists containing seperated input strings.
	:type values: list

	"""
	values = []
	for item in iterable:
		if len(re.findall(r"([a-zA-Z]+)([0-9]+)",item))>1:
			first = "".join(list(re.findall(r"([a-zA-Z]+)([0-9]+)([a-zA-Z]+)",item)[0]))
			second = list(re.findall(r"([a-zA-Z]+)([0-9]+)",item)[-1])[-1]
			values.append([first, second])
		elif list(re.findall(r"([a-zA-Z]+)([0-9]+)",item)):
			values.append(list(re.findall(r"([a-zA-Z]+)([0-9]+)",item)[0]))
		else:
			values.append(["".join(x for x in item if not x.isdigit()), "".join(sorted(x for x in item if x.isdigit()))])
	
	return values

def determine_groups(iterable):
	"""
	Identifies unique strings in a list of strings which include alphas.
	
	:param iterable: The iterable to seperated into unique groups.
	:type iterable: list

	:return values: List of lists ccontaining seperated string groups.
	:type values: list

	"""
	values = []
	for item in iterable:
		if len(re.findall(r"([a-zA-Z]+)([0-9]+)",item))>1:
			first = "".join(list(re.findall(r"([a-zA-Z]+)([0-9]+)([a-zA-Z]+)",item)[0]))
			values.append(first)
		else:
			values.append("".join(x for x in item if not x.isdigit()))
	
	values = list(set(values))
	
	return values

class EDFWriter():
	"""
	This class will write to the edf file format.
	
	:param fname: filename to write.
	:type iterable: string
		
	"""
	def __init__(self, fname=None):
		self.fname = None
		self.meas_info = None
		self.chan_info = None
		self.calibrate = None
		self.offset    = None
		self.n_records = 0
		if fname:
			self.open(fname)

	def open(self, fname):
		with open(fname, 'r+') as fid:
			assert(fid.tell() == 0)
		self.fname = fname

	def close(self):
		# it is still needed to update the number of records in the header
		# this requires copying the whole file content
		meas_info = self.meas_info
		chan_info = self.chan_info
		# update the n_records value in the file
		tempname = self.fname + '.bak'
		os.rename(self.fname, tempname)
		with open(tempname, 'r+') as fid1:
			assert(fid1.tell() == 0)
			with open(self.fname, 'wb') as fid2:
				assert(fid2.tell() == 0)
				fid2.write(fid1.read(236).encode('utf-8'))
				fid1.read(8)                                    # skip this part
				fid2.write(padtrim(str(self.n_records), 8).encode('utf-8'))     # but write this instead
				fid2.write(fid1.read(meas_info['data_offset'] - 236 - 8).encode('utf-8'))
				blocksize = np.sum(chan_info['n_samps']) * meas_info['data_size']
				for block in range(self.n_records):
					fid2.write(fid1.read(blocksize).encode('utf-8'))
		os.remove(tempname)
		self.fname = None
		self.meas_info = None
		self.chan_info = None
		self.calibrate = None
		self.offset    = None
		self.n_records = 0
		return
	
	def padtrim(buf, num):
		num -= len(buf)
		if num>=0:
			# pad the input to the specified length
			return (str(buf) + ' ' * num)
		else:
			# trim the input to the specified length
			return (buf[0:num])
	
	def writeHeader(self, header):
		meas_info = header['meas_info']
		chan_info = header['chan_info']
		meas_size = 256
		chan_size = 256 * meas_info['nchan']
		with open(self.fname, 'r+') as fid:
			assert(fid.tell() == 0)

			# fill in the missing or incomplete information
			if not 'subject_id' in meas_info:
				meas_info['subject_id'] = ''
			if not 'recording_id' in meas_info:
				meas_info['recording_id'] = ''
			if not 'subtype' in meas_info:
				meas_info['subtype'] = 'edf'
			nchan = meas_info['nchan']
			if not 'ch_names' in chan_info or len(chan_info['ch_names'])<nchan:
				chan_info['ch_names'] = [str(i) for i in range(nchan)]
			if not 'transducers' in chan_info or len(chan_info['transducers'])<nchan:
				chan_info['transducers'] = ['' for i in range(nchan)]
			if not 'units' in chan_info or len(chan_info['units'])<nchan:
				chan_info['units'] = ['' for i in range(nchan)]

			if meas_info['subtype'] in ('24BIT', 'bdf'):
				meas_info['data_size'] = 3  # 24-bit (3 byte) integers
			else:
				meas_info['data_size'] = 2  # 16-bit (2 byte) integers

			fid.write(padtrim('0', 8))
			fid.write(padtrim(meas_info['subject_id'], 80))
			fid.write(padtrim(meas_info['recording_id'], 80))
			fid.write(padtrim('{:0>2d}.{:0>2d}.{:0>2d}'.format(meas_info['day'], meas_info['month'], meas_info['year']), 8))
			fid.write(padtrim('{:0>2d}.{:0>2d}.{:0>2d}'.format(meas_info['hour'], meas_info['minute'], meas_info['second']), 8))
			fid.write(padtrim(str(meas_size + chan_size), 8))
#            fid.write((' ' * 44).encode('utf-8'))
			fid.write(' ' * 44)
			fid.write(padtrim(str(-1), 8))  # the final n_records should be inserted on byte 236
			fid.write(padtrim(str(meas_info['record_length']), 8))
			fid.write(padtrim(str(meas_info['nchan']), 4))

			# ensure that these are all np arrays rather than lists
			for key in ['physical_min', 'transducers', 'physical_max', 'digital_max', 'ch_names', 'n_samps', 'units', 'digital_min']:
				chan_info[key] = np.asarray(chan_info[key])

			for i in range(meas_info['nchan']):
				fid.write(padtrim(    chan_info['ch_names'][i], 16))
			for i in range(meas_info['nchan']):
				fid.write(padtrim(    chan_info['transducers'][i], 80))
			for i in range(meas_info['nchan']):
				fid.write(padtrim(    chan_info['units'][i], 8))
			for i in range(meas_info['nchan']):
				fid.write(padtrim(str(chan_info['physical_min'][i]), 8))
			for i in range(meas_info['nchan']):
				fid.write(padtrim(str(chan_info['physical_max'][i]), 8))
			for i in range(meas_info['nchan']):
				fid.write(padtrim(str(chan_info['digital_min'][i]), 8))
			for i in range(meas_info['nchan']):
				fid.write(padtrim(str(chan_info['digital_max'][i]), 8))
			for i in range(meas_info['nchan']):
#                fid.write((' ' * 80).encode('utf-8')) # prefiltering
				fid.write(' ' * 80) # prefiltering
			for i in range(meas_info['nchan']):
				fid.write(padtrim(str(chan_info['n_samps'][i]), 8))
			for i in range(meas_info['nchan']):
#                fid.write((' ' * 32).encode('utf-8')) # reserved
				fid.write(' ' * 32) # reserved
			meas_info['data_offset'] = fid.tell()

		self.meas_info = meas_info
		self.chan_info = chan_info
		self.calibrate = (chan_info['physical_max'] - chan_info['physical_min'])/(chan_info['digital_max'] - chan_info['digital_min']);
		self.offset    =  chan_info['physical_min'] - self.calibrate * chan_info['digital_min'];
		channels = list(range(meas_info['nchan']))
		for ch in channels:
			if self.calibrate[ch]<0:
			  self.calibrate[ch] = 1;
			  self.offset[ch]    = 0;
	
	def writeBlock(self, data):
		meas_info = self.meas_info
		chan_info = self.chan_info
		with open(self.fname, 'ab') as fid:
			assert(fid.tell() > 0)
			for i in range(meas_info['nchan']):
				raw = deepcopy(data[i])

				assert(len(raw)==chan_info['n_samps'][i])
				if min(raw)<chan_info['physical_min'][i]:
					warnings.warn('Value exceeds physical_min: ' + str(min(raw)) );
				if max(raw)>chan_info['physical_max'][i]:
					warnings.warn('Value exceeds physical_max: '+ str(max(raw)));

				raw -= self.offset[i]  # FIXME I am not sure about the order of calibrate and offset
				raw /= self.calibrate[i]

				raw = np.asarray(raw, dtype=np.int16)
				buf = [pack('h', x) for x in raw]
				for val in buf:
					fid.write(val)
			self.n_records += 1
			
			
class EDFReader():
	"""
	This class will read the edf file format.
	
	:param fname: filename to read.
	:type fname: string
		
	"""
	def __init__(self, fname=None):
		self.fname = None
		self.meas_info = None
		self.chan_info = None
		self.calibrate = None
		self.offset    = None
		if fname:
			self.open(fname)

	def open(self, fname):
		
		with open(fname, 'rb') as fid:
			assert(fid.tell() == 0)
		self.fname = fname
		self.readHeader()
		return (self.meas_info, self.chan_info)

	def close(self):
		self.fname = None
		self.meas_info = None
		self.chan_info = None
		self.calibrate = None
		self.offset    = None

	def readHeader(self):
		# the following is copied over from MNE-Python and subsequently modified
		# to more closely reflect the native EDF standard
		meas_info = {}
		chan_info = {}
		with open(self.fname, 'r+b') as fid:
			assert(fid.tell() == 0)
			meas_info['magic'] = fid.read(8).strip().decode()
			subject_id = fid.read(80).strip().decode()  # subject id
			meas_info['gender'] = subject_id.split(' ')[1]
			meas_info['birthdate'] = subject_id.split(' ')[2]
			
			meas_info['subject_id'] = subject_id.split(' ')[-1]
			meas_info['recording_id'] = fid.read(80).strip().decode()  # recording id

			day, month, year = [int(x) for x in re.findall('(\d+)', fid.read(8).decode())]
			hour, minute, second = [int(x) for x in re.findall('(\d+)', fid.read(8).decode())]
			meas_info['day'] = day
			meas_info['month'] = month
			meas_info['year'] = year
			meas_info['hour'] = hour
			meas_info['minute'] = minute
			meas_info['second'] = second
			meas_info['meas_date'] = datetime.datetime(year + 2000, month, day, hour, minute, second).strftime('%Y-%m-%d %H:%M:%S')
			meas_info['data_offset'] = header_nbytes = int(fid.read(8).decode())
		
			subtype = fid.read(44).strip().decode()[:5]
			if len(subtype) > 0:
				meas_info['subtype'] = subtype
			else:
				meas_info['subtype'] = os.path.splitext(self.fname)[1][1:].lower()
		
			if meas_info['subtype'] in ('24BIT', 'bdf'):
				meas_info['data_size'] = 3  # 24-bit (3 byte) integers
			else:
				meas_info['data_size'] = 2  # 16-bit (2 byte) integers
		
			meas_info['n_records'] = int(fid.read(8).decode())
		
			# record length in seconds
			record_length = float(fid.read(8).decode())
			if record_length == 0:
				meas_info['record_length'] = record_length = 1.
				warnings.warn('Headermeas_information is incorrect for record length. '
							  'Default record length set to 1.')
			else:
				meas_info['record_length'] = record_length
			meas_info['nchan'] = nchan = int(fid.read(4).decode())
		
			channels = list(range(nchan))
			chan_info['ch_names'] = [fid.read(16).strip().decode() for ch in channels]
			chan_info['transducers'] = [fid.read(80).strip().decode() for ch in channels]
			chan_info['units'] = [fid.read(8).strip().decode() for ch in channels]
			chan_info['physical_min'] = np.array([float(fid.read(8).decode()) for ch in channels])
			chan_info['physical_max'] = np.array([float(fid.read(8).decode()) for ch in channels])
			chan_info['digital_min'] = np.array([float(fid.read(8).decode()) for ch in channels])
			chan_info['digital_max'] = np.array([float(fid.read(8).decode()) for ch in channels])
			prefiltering = [fid.read(80).strip().decode() for ch in channels][:-1]
			highpass = np.ravel([re.findall('HP:\s+(\w+)', filt) for filt in prefiltering])
			lowpass = np.ravel([re.findall('LP:\s+(\w+)', filt) for filt in prefiltering])
			high_pass_default = 0.
			if highpass.size == 0:
				meas_info['highpass'] = high_pass_default
			elif all(highpass):
				if highpass[0] == 'NaN':
					meas_info['highpass'] = high_pass_default
				elif highpass[0] == 'DC':
					meas_info['highpass'] = 0.
				else:
					meas_info['highpass'] = float(highpass[0])
			else:
				meas_info['highpass'] = float(np.max(highpass))
				warnings.warn('Channels contain different highpass filters. '
							  'Highest filter setting will be stored.')
		
			if lowpass.size == 0:
				meas_info['lowpass'] = None
			elif all(lowpass):
				if lowpass[0] == 'NaN':
					meas_info['lowpass'] = None
				else:
					meas_info['lowpass'] = float(lowpass[0])
			else:
				meas_info['lowpass'] = float(np.min(lowpass))
				warnings.warn('%s' % ('Channels contain different lowpass filters.'
									  ' Lowest filter setting will be stored.'))
			# number of samples per record
			chan_info['n_samps'] = n_samps = np.array([int(fid.read(8).decode()) for ch in channels])
			meas_info['sampling_frequency'] = int(chan_info['n_samps'][0]/meas_info['record_length'])
			
			fid.read(32 *meas_info['nchan']).decode()  # reserved
			assert fid.tell() == header_nbytes
			if meas_info['n_records']==-1:
				# this happens if the n_records is not updated at the end of recording
				tot_samps = (os.path.getsize(self.fname)-meas_info['data_offset'])/meas_info['data_size']
				meas_info['n_records'] = tot_samps/sum(n_samps)
		
		self.calibrate = (chan_info['physical_max'] - chan_info['physical_min'])/(chan_info['digital_max'] - chan_info['digital_min'])
		self.offset    =  chan_info['physical_min'] - self.calibrate * chan_info['digital_min']
		for ch in channels:
			if self.calibrate[ch]<0:
			  self.calibrate[ch] = 1
			  self.offset[ch]    = 0
		
		header = {}
		header['meas_info'] = meas_info
		header['chan_info'] = chan_info
		
		tal_indx = [i for i,x in enumerate(chan_info['ch_names']) if x.endswith('Annotations')][0]
		header['meas_info']['millisecond'] = meas_info['millisecond'] = read_annotation_block(0, self.fname, header, tal_indx)[0][0][0]
		
		self.meas_info = meas_info
		self.chan_info = chan_info
		
		return header
	
	def padtrim(buf, num):
		num -= len(buf)
		if num>=0:
			# pad the input to the specified length
			return (str(buf) + ' ' * num)
		else:
			# trim the input to the specified length
			return (buf[0:num])
	
	def readBlock(self, block):
		assert(block>=0)
		meas_info = self.meas_info
		chan_info = self.chan_info
		data = []
		with open(self.fname, 'rb') as fid:
			assert(fid.tell() == 0)
			blocksize = np.sum(chan_info['n_samps']) * meas_info['data_size']
			fid.seek(meas_info['data_offset'] + block * blocksize)
			for i in range(meas_info['nchan']):
				buf = fid.read(chan_info['n_samps'][i]*meas_info['data_size'])
				raw = np.asarray(unpack('<{}h'.format(chan_info['n_samps'][i]), buf), dtype=np.float32)
				raw *= self.calibrate[i]
				raw += self.offset[i]  # FIXME I am not sure about the order of calibrate and offset
				data.append(raw)
		return (data)
	
	def readSamples(self, channel, begsample, endsample):
		chan_info = self.chan_info
		n_samps = chan_info['n_samps'][channel]
		begblock = int(floor((begsample) / n_samps))
		endblock = int(floor((endsample) / n_samps))
		data = self.readBlock(begblock)[channel]
		for block in range(begblock+1, endblock+1):
			data = np.append(data, self.readBlock(block)[channel])
		begsample -= begblock*n_samps
		endsample -= begblock*n_samps
		return (data[begsample:(endsample+1)])
	
	def getSignalTextLabels(self):
		# convert from unicode to string
		return [str(x) for x in self.chan_info['ch_names']]

	def getNSignals(self):
		return self.meas_info['nchan']

	def getSignalFreqs(self):
		return self.chan_info['n_samps'] / self.meas_info['record_length']

	def getNSamples(self):
		return self.chan_info['n_samps'] * self.meas_info['n_records']

	def readSignal(self, chanindx):
		begsample = 0;
		endsample = self.chan_info['n_samps'][chanindx] * self.meas_info['n_records'] - 1;
		return self.readSamples(chanindx, begsample, endsample)

def _write_tsv(fname, df, overwrite=False, verbose=False, append = False):
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

def _write_json(dictionary, fname, overwrite=False, verbose=False):
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
		
def make_bids_filename(subject_id, session_id, run_num, suffix, prefix):
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

def make_bids_folders(subject_id, session_id, kind, output_path, make_dir, overwrite):
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

def _dataset_json(dataset_fname, bids_settings):
	"""
	Constructs a dataset description JSON file.
	
	:param dataset_fname: Filename for the BIDS dataset description.
	:type dataset_fname: string
	
	"""
	info_dataset_json = OrderedDict([
		('Name', bids_settings['json_metadata']['DatasetName']),
		('BIDSVersion', ''),
		('License', ''),
		('Authors', bids_settings['json_metadata']['Experimenter']),
		('Acknowledgements', 'say here what are your acknowledgments'),
		('HowToAcknowledge', 'say here how you would like to be acknowledged'),
		('Funding', ["list your funding sources"]),
		('ReferencesAndLinks', ["a data paper", "a resource to be cited when using the data"]),
		('DatasetDOI', '')])
	
	_write_json(info_dataset_json, dataset_fname)

def _participants_json(participants_fname):
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

	_write_json(info_participant_json, participants_fname)
	
def _participants_data(subject_id, file_info_sub, participants_fname):
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
		
		_write_tsv(participants_fname, df, overwrite=False, verbose=False, append = True) 

def get_file_info(raw_file_path_sub, bids_settings):
	"""
	Extract header data from EDF file.
	
	:param raw_file_path_sub: Path to the raw data file for specific recording.
	:type raw_file_path_sub: string
	
	:return filesInfo: Dictionary containing header information for all files in specified path.
	:type filesInfo: dictionary
	
	"""
	sub_dir = False

	file_list = [[x] for x in os.listdir(raw_file_path_sub) if x.lower().endswith('.edf')]
	if not file_list:
		sub_dir = True
		folders = [x for x in os.listdir(raw_file_path_sub) if os.path.isdir(os.path.join(raw_file_path_sub, x))]
		for ifold in folders:
			files = [os.path.sep.join([ifold, x]) for x in os.listdir(os.path.join(raw_file_path_sub, ifold)) if x.lower().endswith('.edf')]
			file_list.append(files)
			
	chan_label_filename = [x for x in os.listdir(raw_file_path_sub) if 'channel_label' in x]
	if chan_label_filename:
		chan_label_file_temp = np.genfromtxt(os.path.join(raw_file_path_sub, chan_label_filename[0]), dtype='str')
		
	filesInfo = []
	for ises in file_list:
		filesInfo_ses = []
		for ifile in ises:
			filen = os.path.join(raw_file_path_sub, ifile)
			file_in = EDFReader()
			try:
				meas_info, chan_info = file_in.open(filen)
				header = file_in.readHeader()
				file_in.close()
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
						
				eeg_chan_idx = [i for i, x in enumerate(values) if x[0] not in list(bids_settings['natus_info']['ChannelInfo'].keys())]
				group_info = determine_groups(np.array(chan_label_file)[eeg_chan_idx])
				
				file_info = [
						('FileName', ifile),
						('SubDir', raw_file_path_sub.split(os.path.sep)[-1]),
						('DisplayName', ifile if not sub_dir else ifile.split(os.path.sep)[0]),
						('Subject', meas_info['subject_id']),
						('Gender', meas_info['gender']),
						('Age', int(np.floor(((datetime.datetime.strptime(meas_info['meas_date'].split(' ')[0],"%Y-%m-%d") 
								- datetime.datetime.strptime(datetime.datetime.strptime(meas_info['birthdate'],
								'%d-%b-%Y').strftime('%Y-%m-%d'),"%Y-%m-%d")).days)/365)) if meas_info['birthdate'] != 'X' else 'X'),
						('Birthdate', meas_info['birthdate']),
						('RecordingID', meas_info['recording_id']),
						('Date', meas_info['meas_date'].split(' ')[0]),
						('Time', meas_info['meas_date'].split(' ')[1]),
						('DataOffset', meas_info['data_offset']),
						('NRecords', meas_info['n_records']),
						('RecordLength', meas_info['record_length']),
						('TotalRecordTime', round((((meas_info['n_records']*(meas_info['sampling_frequency']*meas_info['record_length']))/meas_info['sampling_frequency'])/60)/60,3)),
						('NChan', meas_info['nchan']),
						('SamplingFrequency', meas_info['sampling_frequency']),
						('Highpass', meas_info['highpass']),
						('Lowpass', meas_info['lowpass']),
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
					('Unit', np.array(header['chan_info']['units'])[eeg_chan_idx]),
					('ChanName', np.array(chan_label_file)[eeg_chan_idx]),
					('Type', chan_type)])
				
				for key in bids_settings['natus_info']['ChannelInfo'].keys():
					chan_idx = [i for i, x in enumerate(values) if x[0] == key]
					ch_info[key] = OrderedDict([
							('ChannelCount', len(chan_idx)),
							('Unit', np.array(header['chan_info']['units'])[chan_idx]),
							('ChanName', np.array(chan_label_file)[chan_idx]),
							('Type', bids_settings['natus_info']['ChannelInfo'][key]['name'])])
				
				file_info['ChanInfo'] = OrderedDict(ch_info)
				file_info = OrderedDict(file_info)
			
				filesInfo_ses.append(file_info)
			except:
				print('Something wrong with file', ifile)
		
		if filesInfo_ses:
			filesInfo.append([filesInfo_ses, {'Date': filesInfo_ses[0]['Date'], 'Time': filesInfo_ses[0]['Time']}])
		
	filesInfo = sorted(filesInfo, key = lambda i: (i[1]['Date'], i[1]['Time']))
	filesInfo = [x[0] for x in filesInfo]
	
	if not sub_dir:
		filesInfo_final = []
		study_dates = [x[0]['Date'] for x in filesInfo]
		dates_unique, counts = np.unique(study_dates, return_counts=True)
		for idate in dates_unique:
			filesInfo_temp = []
			index_session = [i for i,x in enumerate(study_dates) if x == idate]
			for ises in index_session:
				filesInfo_temp.append(filesInfo[ises][0])
			filesInfo_temp = sorted(filesInfo_temp, key = lambda i: (i['Date'], i['Time']))
			filesInfo_final.append(filesInfo_temp)
			
		filesInfo = filesInfo_final
		
	return filesInfo

def folders_in(path_to_parent):
	contains_dir = False
	for fname in os.listdir(path_to_parent):
		if os.path.isdir(os.path.join(path_to_parent,fname)):
			contains_dir = True
	
	return contains_dir

#%%

# from bids_settings import ieeg_file_metadata, natus_info
# raw_file_path = r'/media/veracrypt6/projects/eplink/other_data/twh eplink data'
# output_path = r'/media/veracrypt6/projects/eplink/test'

# bids_settings = {}
# bids_settings['json_metadata'] = ieeg_file_metadata
# bids_settings['natus_info'] = natus_info
# bids_settings['settings_panel'] = {'Deidentify_source': False,
# 									 'offset_dates': False}
# input_dir = r'/media/veracrypt6/projects/eplink/other_data/twh eplink data'
# file_info, chan_label_file = read_input_dir(raw_file_path, bids_settings)

# isub = list(file_info)[0]
# values = file_info[isub]
# offset_date = False
	
def read_input_dir(input_dir, bids_settings):
	"""
	Reads data within the specified path.
	
	:param input_dir: Directory to read data files from.
	:type input_dir: string
	
	:return sub_file_info: Dictionary containing header information for all files in specified path.
	:type sub_file_info: dictionary
	
	"""
	folders = [x for x in os.listdir(input_dir) if os.path.isdir(os.path.join(input_dir, x))]
	folders = sorted_nicely([x for x in folders if len(os.listdir(os.path.join(input_dir,x))) !=0])
		
	sub_file_info = {}
	sub_chan_file = {}
	for ifold in folders:			
		subject_id = ifold.replace('_','')
		if not subject_id.startswith('sub-'):
			subject_id = 'sub-' + subject_id
			
		raw_file_path_sub = os.path.join(input_dir, ifold)
		file_info = get_file_info(raw_file_path_sub, bids_settings)
		sub_file_info[subject_id] = file_info
		chan_label_file = [x for x in os.listdir(raw_file_path_sub) if 'channel_label' in x]
		sub_chan_file[subject_id] = chan_label_file
		
	return sub_file_info, sub_chan_file

def read_output_dir(output_path, file_info, offset_date, participants_fname):
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
	folders = sorted_nicely([x for x in os.listdir(output_path) if os.path.isdir(os.path.join(output_path,x)) and 'code' not in x])
	new_sessions = {}
		
	for isub, values in file_info.items():
		num_sessions = len(values)
		newSessions = True
		session_start = 0
		session_labels = np.nan
		sub_sessions = {}
		session_list = []
		all_labels = []
		unique_sessions = []
		
		# True if subject directory already in output directory
		if isub in folders:
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
					num_sessions = len(all_labels)
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
				_participants_data(isub, values[0][0], participants_fname)
			
		sub_sessions['newSessions'] = newSessions
		sub_sessions['session_done'] = session_start
		sub_sessions['num_sessions'] = num_sessions
		sub_sessions['session_labels'] = session_labels
		sub_sessions['session_index'] = session_index
		sub_sessions['all_sessions'] = all_labels
		sub_sessions['session_changes'] = session_list
		
		new_sessions[isub] = sub_sessions
		
	return new_sessions

def fix_sessions(session_list, num_sessions, output_path, isub):
	for ises in session_list:		
		old_fold = os.path.join(output_path, isub, ises[0], 'ieeg')
		new_fold = os.path.join(output_path, isub, 'temp', ises[1], 'ieeg')
		
		if not os.path.exists(os.path.join(output_path, isub, 'temp')):
			os.mkdir(os.path.join(output_path, isub, 'temp'))
		if not os.path.exists(os.path.join(output_path, isub, 'temp', ises[1])):
			os.mkdir(os.path.join(output_path, isub, 'temp', ises[1]))
		if not os.path.exists(new_fold):
			os.mkdir(new_fold)
			
		moveAllFilesinDir(old_fold, new_fold)
		
		for f in os.listdir(new_fold):
			if 'ieeg.edf' in f:
				new_filename = os.path.join(new_fold,'_'.join([f.split('_')[0],ises[1],f.split('_')[2], f.split('_')[3]]))
				os.rename(os.path.join(new_fold,f), new_filename)
				
				with open(new_filename, 'r+b') as fid:
					assert(fid.tell() == 0)
					fid.seek(8)
					fid.write(padtrim(isub, 80).encode('utf-8')) # subject id
					fid.write(padtrim(make_bids_filename(isub, ises[1], f.split('_')[2].split('-')[-1], f.split('_')[-1], prefix=''), 80).encode('utf-8')) # recording id
			elif 'ieeg.json' in f:
				new_filename = os.path.join(new_fold,'_'.join([f.split('_')[0],ises[1],f.split('_')[2], f.split('_')[3]]))
				os.rename(os.path.join(new_fold,f), new_filename)
			elif 'channels.tsv' in f:
				new_filename = os.path.join(new_fold,'_'.join([f.split('_')[0],ises[1],f.split('_')[2], f.split('_')[3]]))
				os.rename(os.path.join(new_fold,f), new_filename)
			elif 'annotations.tsv' in f:
				new_filename = os.path.join(new_fold,'_'.join([f.split('_')[0],ises[1],f.split('_')[2], f.split('_')[3]]))
				os.rename(os.path.join(new_fold,f), new_filename)
			elif 'electrodes.tsv' in f:
				new_filename = os.path.join(new_fold,'_'.join([f.split('_')[0],ises[1],f.split('_')[2]]))
				os.rename(os.path.join(new_fold,f), new_filename)
		
		shutil.rmtree(os.path.dirname(old_fold))
		
		old_code_fold = os.path.join(output_path, 'code', 'edf2bids', isub, ises[0])
		new_code_fold = os.path.join(output_path, 'code', 'edf2bids', isub, 'temp', ises[1])
		
		if not os.path.exists(os.path.join(output_path, 'code', 'edf2bids', isub, 'temp')):
			os.mkdir(os.path.join(output_path, 'code', 'edf2bids', isub, 'temp'))
		if not os.path.exists(new_code_fold):
			os.mkdir(new_code_fold)
		
		moveAllFilesinDir(old_code_fold, new_code_fold)
		shutil.rmtree(old_code_fold)
	
		# Load output scan file
		scans_tsv = pd.read_csv(os.path.join(output_path, isub, isub + '_scans.tsv'), sep='\t')
		name_idx = [i for i,x in enumerate(list(scans_tsv['filename'])) if ises[0] in x][-1]
		old_name = scans_tsv.loc[name_idx, 'filename'].split('/')[-1]
		new_name = 'ieeg/' + '_'.join([old_name.split('_')[0], ises[1]] + old_name.split('_')[2:])
		scans_tsv.loc[name_idx, 'filename'] = new_name
		
		_write_tsv(os.path.join(output_path, isub, isub + '_scans.tsv'), scans_tsv, overwrite=True)

	temp_dir = os.path.join(output_path, isub, 'temp')
	final_dir = os.path.join(output_path, isub)
	
	moveAllFilesinDir(temp_dir, final_dir)
	
	shutil.rmtree(temp_dir)
	
	temp_dir = os.path.join(output_path, 'code', 'edf2bids', isub, 'temp')
	final_dir = os.path.join(output_path, 'code', 'edf2bids', isub)
	
	moveAllFilesinDir(temp_dir, final_dir)
	
	shutil.rmtree(temp_dir)
		
def moveAllFilesinDir(old_fold, new_fold):
	# Check if both the are directories
	if os.path.isdir(old_fold) and os.path.isdir(new_fold) :
		# Iterate over all the files in source directory
		for filePath in glob.glob(old_fold + os.path.sep + '*'):
			# Move each file to destination Directory
			shutil.move(filePath, new_fold)

def read_annotation_block(block, data_fname, header, tal_indx):
		pat = '([+-]\\d+\\.?\\d*)(\x15(\\d+\\.?\\d*))?(\x14.*?)\x14\x00'
		assert(block>=0)
		data = []
		with open(data_fname, 'rb') as fid:
			assert(fid.tell() == 0)
			blocksize = np.sum(header['chan_info']['n_samps']) * header['meas_info']['data_size']
			fid.seek(np.int64(header['meas_info']['data_offset']) + np.int64(block) * np.int64(blocksize))
			read_idx = 0
			for i in range(header['meas_info']['nchan']):
				read_idx += np.int64(header['chan_info']['n_samps'][i]*header['meas_info']['data_size'])
				buf = fid.read(np.int64(header['chan_info']['n_samps'][i]*header['meas_info']['data_size']))
				if i==tal_indx:
					raw = re.findall(pat, buf.decode('latin-1'))
					if raw:
						data.append(list(map(list, [x+(block,) for x in raw])))
		return data
	
def read_annotation_block(block, data_fname, header, chanindx):
	assert(block>=0)
	data = []
	data_overwrite = []
	with open(data_fname, 'rb') as fid:
		assert(fid.tell() == 0)
		blocksize = np.sum(header['chan_info']['n_samps']) * header['meas_info']['data_size']
		fid.seek(np.int64(header['meas_info']['data_offset']) + np.int64(block) * np.int64(blocksize))
		read_idx = 0
		for i in range(header['meas_info']['nchan']):
			read_idx += np.int64(header['chan_info']['n_samps'][i]*header['meas_info']['data_size'])
			buf = fid.read(np.int64(header['chan_info']['n_samps'][i]*header['meas_info']['data_size']))
			if i == chanindx:
				raw = buf.decode('latin-1', 'ignore')
				raw = [x for x in re.split(r'[^\x20-\x7e]', raw) if len(x) >0]
				if len(raw) > 3:
					raw = [raw[0], raw[1], ' '.join(raw[2:])]
				if len(raw)>2:
					if header['meas_info']['firstname'] is not None:
						if 'Montage' in raw[2] and 'Montage Event' not in raw[2]:
							 fid_loc = [(np.int64(header['meas_info']['data_offset']) + np.int64(block) * np.int64(blocksize)) + read_idx, np.int64(header['chan_info']['n_samps'][i]*header['meas_info']['data_size'])]
							 data_overwrite.append(['Montage'] + fid_loc + raw+ [block])
						elif any(x.lower() in raw[2].lower() for x in {header['meas_info']['firstname'], header['meas_info']['lastname']}):
							 fid_loc = [(np.int64(header['meas_info']['data_offset']) + np.int64(block) * np.int64(blocksize)) + read_idx, np.int64(header['chan_info']['n_samps'][i]*header['meas_info']['data_size'])]
							 data_overwrite.append(['Name'] + fid_loc + raw+ [block])
# 						elif any(x in raw[2] for x in {'values.append', 'self.offset[i]', 'n/a 0.0 512'}):
# 							 fid_loc = [(np.int64(header['meas_info']['data_offset']) + np.int64(block) * np.int64(blocksize)) + read_idx, np.int64(header['chan_info']['n_samps'][i]*header['meas_info']['data_size'])]
# 							 data_overwrite.append(['Other'] + fid_loc + raw+ [block])
						else:
							 data.append(raw)
					else:
						if 'Montage' in raw[2] and 'Montage Event' not in raw[2]:
							 fid_loc = [(np.int64(header['meas_info']['data_offset']) + np.int64(block) * np.int64(blocksize)) + read_idx, np.int64(header['chan_info']['n_samps'][i]*header['meas_info']['data_size'])]
							 data_overwrite.append(['Montage'] + fid_loc + raw + [block])
						elif any(x in raw[2] for x in {'values.append', 'self.offset[i]', 'n/a 0.0 512','callback.emit','Constructs a participant','w r x o k d'}):
							 fid_loc = [(np.int64(header['meas_info']['data_offset']) + np.int64(block) * np.int64(blocksize)) + read_idx, np.int64(header['chan_info']['n_samps'][i]*header['meas_info']['data_size'])]
							 data_overwrite.append(['Other'] + fid_loc + raw+ [block])
						elif 'Montage' in raw[2] and any(x in raw[0] for x in {'np.asarray(', 'item.startswith', 'SEEG','callback.emit','Constructs a participant','w r x o k d'}):
							 fid_loc = [(np.int64(header['meas_info']['data_offset']) + np.int64(block) * np.int64(blocksize)) + read_idx, np.int64(header['chan_info']['n_samps'][i]*header['meas_info']['data_size'])]
							 data_overwrite.append(['Other'] + fid_loc + raw+ [block])
						else:
							data.append(raw)
						 
	return data, data_overwrite

def deidentify_edf(fname, isub, offset_date, rename):
	file_in = EDFReader()
	file_in.open(os.path.join(fname))
	header = file_in.readHeader()
	file_in.close()
	
	edf_subject_id = []
	recording_id = []
	if not header['meas_info']['birthdate'] == 'X':
		edf_subject_id = 'X X X ' + isub
		
	if not header['meas_info']['gender'] == 'X':
		edf_subject_id = 'X X X ' + isub
		
	if not header['meas_info']['subject_id'] == isub:
		edf_subject_id = 'X X X ' + isub
	
	if not header['meas_info']['recording_id'] == 'Startdate X X X X':
		recording_id = 'Startdate X X X X'
	
	new_date = []
	days_off = 0
	if offset_date:
		date_offset = datetime.datetime(2001,1,1)
		date_study = datetime.datetime.strptime(datetime.datetime.strptime(header['meas_info']['meas_date'], '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d'), '%Y-%m-%d')
		days_offset = datetime.timedelta((date_study - date_offset).days - 1000)
		new_date = (date_offset + days_offset).strftime('%d.%m.%y')
		days_off = days_offset.days
	
	with open(fname, 'r+b') as fid:
		assert(fid.tell() == 0)
		fid.seek(8)
		
		if edf_subject_id:
			fid.write(padtrim(edf_subject_id, 80).encode('utf-8'))
		else:
			fid.seek(80+8)
			assert(fid.tell() == 80+8)
		
		if recording_id:
			fid.write(padtrim(recording_id, 80).encode('utf-8'))
		else:
			fid.seek(80+80+8)
			assert(fid.tell() == 80+80+8)
			
		if new_date:
			fid.write(padtrim(new_date, 8).encode('utf-8'))
		else:
			fid.seek(80+80+8+8)
			assert(fid.tell() == 80+80+8+8)
			
	if rename:		
		if '~' in fname.split(os.path.sep)[-1]:
			new_name = '_'.join([isub] + fname.split(os.path.sep)[-1].split('_')[1:]).split('.')[0] + '.edf'
			os.rename(fname, os.path.join(os.path.dirname(fname), new_name))
		else:
			new_name = fname
	else:
		new_name = fname
	
	return new_name, days_off