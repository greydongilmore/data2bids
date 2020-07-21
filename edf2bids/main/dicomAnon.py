#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jun 24 18:06:23 2020

@author: greydon
"""
import os
import pandas as pd
pd.set_option('precision', 6)
from PySide2 import QtCore
import pydicom
from dicognito.anonymizer import Anonymizer
import datetime
import shutil

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
	
class dicomAnon(QtCore.QRunnable):
		
	def __init__(self):	
# 		QtCore.QThread.__init__(self)
		super(dicomAnon, self).__init__()
		
		self.input_path = []
		self.output_path = []
		self.imaging_data = []
		
		self.signals = WorkerSignals()
		
		self.running = False
		self.userAbort = False
		self.is_killed = False
		
	def stop(self):
		self.running = False
		self.userAbort = True
		
	def kill(self):
		self.is_killed = True
		
	@QtCore.Slot()
	def run(self):
		"""
		Main loop.
				
		"""
		if not self.userAbort:
			self.running = True
		
		try:
			self.conversionStatusText = 'De-identifying imaging data...\n'
			self.signals.progressEvent.emit(self.conversionStatusText)
			
			for isub in list(self.imaging_data.keys()):
				
				if self.imaging_data[isub]['imaging_dir']:
					self.conversionStatusText = 'De-identifying imaging data for subject {} at {}'.format(isub, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
					self.signals.progressEvent.emit(self.conversionStatusText)
					
					if self.is_killed:
						self.running = False
						raise WorkerKilledException
					
					outdir = os.path.join(self.output_path, 'imaging', self.imaging_data[isub]['orig_sub_dir'])
					base = os.path.join(self.input_path, self.imaging_data[isub]['orig_sub_dir'], self.imaging_data[isub]['imaging_dir'][0])
					
					outname = [x for x in os.listdir(os.path.join(self.input_path, self.imaging_data[isub]['orig_sub_dir'], self.imaging_data[isub]['imaging_dir'][0]))]
					if len(outname) ==1:
						base = os.path.join(base, outname[0])
						outdir = os.path.join(outdir, outname[0])
					
					study_folders = [x for x in os.listdir(base) if os.path.isdir(os.path.join(base, x))]
					anonymizer = Anonymizer()
					for istudy in study_folders:
						dicom_files = []
						for root, folders, files in os.walk(os.path.join(base, istudy)):
							for file in files:
								fullpath = os.path.abspath(os.path.join(root,file))
								dicom_files.append(fullpath)
							
						for original_filename in dicom_files:
							outname = os.path.sep.join([outdir]+ original_filename.split(os.sep)[-2:])
							if not os.path.exists(os.path.dirname(outname)):
								os.makedirs(os.path.dirname(outname))
							with pydicom.dcmread(original_filename) as dataset:
								anonymizer.anonymize(dataset)
								dataset.save_as(outname)
					
					shutil.make_archive(outdir, 'zip', outdir)
					shutil.rmtree(outdir)
					
		except WorkerKilledException:
			self.running = False
			pass
		
		finally:
			self.running = False
			self.signals.finished.emit()
			
				