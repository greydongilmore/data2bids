#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jun 24 18:06:23 2020

@author: greydon
"""
import os
import pandas as pd
pd.set_option('precision', 6)
import shutil
from PySide2 import QtCore
import time
import re
import datetime

from helpers import moveAllFilesinDir

class bids2spred(QtCore.QThread):
	
	progressEvent = QtCore.Signal(str)
	
	def __init__(self):	
		QtCore.QThread.__init__(self)
		
		self.output_path = []
		self.script_path = []
				
		self.running = False
		self.userAbort = False
		
	def stop(self):
		self.running = False
		self.userAbort = True
	
	@QtCore.Slot()
	def run(self):
		"""
		Main loop.
				
		"""
		if not self.userAbort:
			self.running = True
		
		while self.running:
			self.conversionStatusText = 'Converting directory to SPReD format...\n'
			self.progressEvent.emit(self.conversionStatusText)
			
			folders = [x for x in os.listdir(self.output_path) if os.path.isdir(os.path.join(self.output_path, x)) and 'code' not in x]
			output_folders = ['_'.join([''.join(' '.join(re.split('(\d+)', x.split('-')[-1])).split()[:2])] + ' '.join(re.split('(\d+)', x.split('-')[-1])).split()[2:]) for x in folders]
			sub_cnt = 0
			for isub in folders:
				ses_folders = [x for x in os.listdir(os.path.sep.join([self.output_path, isub])) if os.path.isdir(os.path.sep.join([self.output_path, isub, x]))]
				
				session_split = [[x for x in i if x.isdigit()] for i in ses_folders]
				ses_folders_output = ['_'.join([x[0]+x[1],'SE'+x[2]+x[3]]) for x in session_split]
				ses_cnt = 0
				for ises in ses_folders:
					self.conversionStatusText = 'Performing SPReD conversion: session {} of {} for {} at {}'.format(str(ses_cnt+1), str(len(ses_folders)), isub, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
					self.progressEvent.emit(self.conversionStatusText)
					
					old_subfold = [x for x in os.listdir(os.path.sep.join([self.output_path, isub, ises])) if os.path.isdir(os.path.sep.join([self.output_path, isub, ises, x]))]
					new_subfolder = '_'.join([output_folders[sub_cnt], ses_folders_output[ses_cnt]+'_'+ old_subfold[0].upper()])
					old_fold = os.path.sep.join([self.output_path, isub, ises, old_subfold[0]])
					new_fold = os.path.sep.join([self.output_path, 'SPReD', output_folders[sub_cnt], new_subfolder, new_subfolder])
					
					if not os.path.exists(new_fold):
						os.makedirs(new_fold)
					else:
						electrodes_output = [x for x in os.listdir(new_fold) if x.endswith('electrodes.tsv')]
						if electrodes_output:
							electrodes_input = [x for x in os.listdir(old_fold) if x.endswith('electrodes.tsv')]
							os.remove(os.path.sep.join(old_fold, electrodes_input))
							
					moveAllFilesinDir(old_fold, new_fold)
					shutil.make_archive(os.path.dirname(new_fold), 'zip', os.path.dirname(new_fold))
					shutil.rmtree(os.path.dirname(new_fold))
					
					if ises == ses_folders[-1]:
						self.conversionStatusText = ''
						self.progressEvent.emit(self.conversionStatusText)
					
					ses_cnt += 1
				
				sub_cnt += 1
				
				time.sleep(0.1)
			
			folders = [x for x in os.listdir(self.output_path) if 'SPReD' not in x]
			
			if not os.path.exists(os.path.sep.join([self.output_path, 'bids_old'])):
				os.makedirs(os.path.sep.join([self.output_path, 'bids_old']))
								
			for ifiles in folders:
				old_file = os.path.sep.join([self.output_path, ifiles])
				new_file = os.path.sep.join([self.output_path, 'bids_old', ifiles])
				shutil.move(old_file, new_file)
			
			self.running = False
				