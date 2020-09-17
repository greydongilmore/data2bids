# -*- coding: utf-8 -*-
"""
Created on Sat Dec 29 13:49:51 2018

@author: Greydon
"""
import sys
import os
import pandas as pd
import datetime
import shutil
import numpy as np
import json
import re

from PySide2 import QtGui, QtCore, QtWidgets

from widgets import gui_layout
from widgets import settings_panel
from edf2bids import edf2bids
from bids2spred import bids2spred
from dicomAnon import dicomAnon

from helpers import read_input_dir, read_output_dir, bidsHelper

class SettingsDialog(QtWidgets.QDialog, settings_panel.Ui_Dialog):
	def __init__(self):
		super(SettingsDialog, self).__init__()
		self.setupUi(self)
		
		# set initials values to widgets
		self.ieeg_file_metadata = {
			'TaskName': 'EEG Clinical',
			'Experimenter': ['John Smtih, Wayne Smith'],
			'Lab': 'Some cool lab',
			'InstitutionName': 'Some University',
			'InstitutionAddress': '123 Fake Street, Fake town, Fake country',
			'ExperimentDescription': '',
			'DatasetName': '',
			}
		
		self.natus_info = {
			'Manufacturer': 'Natus',
			'ManufacturersModelName': 'Neuroworks',
			'SamplingFrequency': 1000,
			'HighpassFilter': np.nan,
			'LowpassFilter': np.nan,
			'MERUnit': 'uV',
			'PowerLineFrequency': 60,
			'RecordingType': 'continuous',
			'iEEGCoordinateSystem': 'continuous',
			'iEEGElectrodeInfo': {
					'Manufacturer': 'AdTech',
					'Type': 'depth',
					'Material': 'Platinum',
					'Diameter': 1.3
					},
			'EEGElectrodeInfo': {
					'Manufacturer': 'AdTech',
					'Type': 'scalp',
					'Material': 'Platinum',
					'Diameter': 1.3
					},
			'ChannelInfo': {
					'Patient Event': {'type': 'PatientEvent', 'name': 'PE'},
					'DC': {'type': 'DAC', 'name': 'DAC'},
					'TRIG': {'type': 'TRIG', 'name': 'TR'},
					'OSAT': {'type': 'OSAT', 'name': 'OSAT'},
					'PR': {'type': 'PR', 'name': 'MISC'},
					'Pleth': {'type': 'Pleth', 'name': 'MISC'},
					'EDF Annotations': {'type': 'Annotations', 'name': 'ANNO'},
					'C': {'type': 'unused', 'name': 'unused'},
					'X': {'type': 'unused', 'name': 'unused'},
					'EKG': {'type': 'EKG', 'name': 'EKG'},
					'EMG': {'type': 'EMG', 'name': 'EMG'},
					'EOG': {'type': 'EOG', 'name': 'EOG'},
					'ECG': {'type': 'ECG', 'name': 'ECG'}
					}
		 }
		
class MainWindow(QtWidgets.QMainWindow, gui_layout.Ui_MainWindow):
	def __init__(self):
		super(self.__class__, self).__init__()
		
		self.setupUi(self)
		self.settingsPanel = SettingsDialog()
		self.bidsSettingsSetup()
		
		self.cancel_button_color = "background-color: rgb(255,0,0);color: black"
		self.spred_button_color = "background-color: rgb(0, 85, 255);color: black"
		self.convert_button_color = "background-color: rgb(79, 232, 109);color: black"
		self.inactive_color = "background-color: rgb(160, 160, 160);color: rgb(130, 130, 130)"
		
		self.updateStatus("Welcome to edf2bids converter. Load your directory.")
		self.sText.setVisible(0)
		self.conversionStatus.setReadOnly(True)
		self.cancelButton.setEnabled(False)
		self.cancelButton.setStyleSheet(self.inactive_color)
		self.spredButton.setEnabled(False)
		self.spredButton.setStyleSheet(self.inactive_color)
		self.userAborted = False
		
		self.l1 = QtWidgets.QTreeWidgetItem(["Check items are already present in output directory."])
		
# 		self.deidentifyInputDir.stateChanged.connect(self.onDeidentifyCheckbox)
		self.offsetDate.stateChanged.connect(self.onOffsetdateCheckbox)
		
		self.threadpool = QtCore.QThreadPool()
		
		self.loadDirButton.clicked.connect(self.onLoadDirButton)
		self.outDirButton.clicked.connect(self.onOutDirButton)
		self.convertButton.clicked.connect(self.onConvertButton)
		self.spredButton.clicked.connect(self.onSpredButton)
		self.imagingButton.clicked.connect(self.onImagingButton)
		
		self.actionLoad_data.triggered.connect(self.onLoadDirButton)
		self.actionSettings.triggered.connect(self.onSettingsButton)
		self.settingsPanel.buttonBoxJson.accepted.connect(self.onSettingsAccept)
		self.settingsPanel.buttonBoxJson.rejected.connect(self.onSettingsReject)
		self.actionQuit.triggered.connect(self.close)
	
	def onSettingsReject(self):
		pass
	
	def bidsSettingsSetup(self):
		config_name = 'bids_settings.json'
		if getattr(sys, 'frozen', False):
			self.application_path = os.path.dirname(sys.argv[0])
		elif __file__:
			self.application_path = os.path.dirname(os.path.realpath(__file__))
			
		file = os.path.join(self.application_path, config_name)
		if not os.path.exists(file):
			bids_settings_json_temp = {}
			bids_settings_json_temp['json_metadata'] = self.settingsPanel.ieeg_file_metadata
			bids_settings_json_temp['natus_info'] = self.settingsPanel.natus_info
			bids_settings_json_temp['settings_panel'] = {'Deidentify_source': False,
														  'offset_dates': True}
			
			json_output = json.dumps(bids_settings_json_temp, indent=4)
			with open(file, 'w') as fid:
				fid.write(json_output)
				fid.write('\n')
		else:
			with open(file) as settings_file:
				bids_settings_json_temp = json.load(settings_file)
		
		self.bids_settings = bids_settings_json_temp
		
# 		self.deidentifyInputDir.setChecked(self.bids_settings['settings_panel']['Deidentify_source'])
		self.offsetDate.setChecked(self.bids_settings['settings_panel']['offset_dates'])
	
# 	def onDeidentifyCheckbox(self):
# 		file = os.path.join(self.application_path, 'bids_settings.json')
# 		with open(file) as settings_file:
# 				bids_settings_json_temp = json.load(settings_file)
# 				
# 		if bids_settings_json_temp['settings_panel']['Deidentify_source'] != self.deidentifyInputDir.isChecked():
# 			bids_settings_json_temp['settings_panel']['Deidentify_source'] = self.deidentifyInputDir.isChecked()
# 			json_output = json.dumps(bids_settings_json_temp, indent=4)
# 			with open(file, 'w') as fid:
# 				fid.write(json_output)
# 				fid.write('\n')
# 				
# 			self.bids_settings = bids_settings_json_temp
	
	def onOffsetdateCheckbox(self):
		file = os.path.join(self.application_path, 'bids_settings.json')
		with open(file) as settings_file:
				bids_settings_json_temp = json.load(settings_file)
				
		if bids_settings_json_temp['settings_panel']['offset_dates'] != self.offsetDate.isChecked():
			bids_settings_json_temp['settings_panel']['offset_dates'] = self.offsetDate.isChecked()
			json_output = json.dumps(bids_settings_json_temp, indent=4)
			with open(file, 'w') as fid:
				fid.write(json_output)
				fid.write('\n')
				
			self.bids_settings = bids_settings_json_temp
			
	def onSettingsButton(self):
		self.settingsPanel.textboxDatasetName.setText(self.bids_settings['json_metadata']['DatasetName'])
		self.settingsPanel.textboxExperimenter.setText(self.bids_settings['json_metadata']['Experimenter'][0])
		self.settingsPanel.textboxLab.setText(self.bids_settings['json_metadata']['Lab'])
		self.settingsPanel.textboxInstitutionName.setText(self.bids_settings['json_metadata']['InstitutionName'])
		self.settingsPanel.textboxInstitutionAddress.setText(self.bids_settings['json_metadata']['InstitutionAddress'])
		
		self.settingsPanel.textboxIEEGManufacturer.setText(self.bids_settings['natus_info']['iEEGElectrodeInfo']['Manufacturer'])
		self.settingsPanel.textboxIEEGType.setText(self.bids_settings['natus_info']['iEEGElectrodeInfo']['Type'])
		self.settingsPanel.textboxIEEGMaterial.setText(self.bids_settings['natus_info']['iEEGElectrodeInfo']['Material'])
		self.settingsPanel.textboxIEEGDiameter.setText(str(self.bids_settings['natus_info']['iEEGElectrodeInfo']['Diameter']))
		
		self.settingsPanel.textboxEEGManufacturer.setText(self.bids_settings['natus_info']['EEGElectrodeInfo']['Manufacturer'])
		self.settingsPanel.textboxEEGType.setText(self.bids_settings['natus_info']['EEGElectrodeInfo']['Type'])
		self.settingsPanel.textboxEEGMaterial.setText(self.bids_settings['natus_info']['EEGElectrodeInfo']['Material'])
		self.settingsPanel.textboxEEGDiameter.setText(str(self.bids_settings['natus_info']['EEGElectrodeInfo']['Diameter']))
		
		self.settingsPanel.exec_()
	
	def onSettingsAccept(self):
		if self.bids_settings['json_metadata']['DatasetName'] != self.settingsPanel.textboxDatasetName.text():
			self.bids_settings['json_metadata']['DatasetName'] = self.settingsPanel.textboxDatasetName.text()
		if self.bids_settings['json_metadata']['Experimenter'][0] != self.settingsPanel.textboxExperimenter.text():
			self.bids_settings['json_metadata']['Experimenter'] = [self.settingsPanel.textboxExperimenter.text()]
		if self.bids_settings['json_metadata']['Lab'] != self.settingsPanel.textboxLab.text():
			self.bids_settings['json_metadata']['Lab'] = self.settingsPanel.textboxLab.text()
		if self.bids_settings['json_metadata']['InstitutionName'] != self.settingsPanel.textboxInstitutionName.text():
			self.bids_settings['json_metadata']['InstitutionName'] = self.settingsPanel.textboxInstitutionName.text()
		if self.bids_settings['json_metadata']['InstitutionAddress'] != self.settingsPanel.textboxInstitutionAddress.text():
			self.bids_settings['json_metadata']['InstitutionAddress'] = self.settingsPanel.textboxInstitutionAddress.text()
		
		if self.bids_settings['natus_info']['iEEGElectrodeInfo']['Manufacturer'] != self.settingsPanel.textboxIEEGManufacturer.text():
			self.bids_settings['natus_info']['iEEGElectrodeInfo']['Manufacturer'] = self.settingsPanel.textboxIEEGManufacturer.text()
		if self.bids_settings['natus_info']['iEEGElectrodeInfo']['Type'] != self.settingsPanel.textboxIEEGType.text():
			self.bids_settings['natus_info']['iEEGElectrodeInfo']['Type'] = self.settingsPanel.textboxIEEGType.text()
		if self.bids_settings['natus_info']['iEEGElectrodeInfo']['Material'] != self.settingsPanel.textboxIEEGMaterial.text():
			self.bids_settings['natus_info']['iEEGElectrodeInfo']['Material'] = self.settingsPanel.textboxIEEGMaterial.text()
		if self.bids_settings['natus_info']['iEEGElectrodeInfo']['Diameter'] != self.settingsPanel.textboxIEEGDiameter.text():
			self.bids_settings['natus_info']['iEEGElectrodeInfo']['Diameter'] = self.settingsPanel.textboxIEEGDiameter.text()	
			
		if self.bids_settings['natus_info']['EEGElectrodeInfo']['Manufacturer'] != self.settingsPanel.textboxEEGManufacturer.text():
			self.bids_settings['natus_info']['EEGElectrodeInfo']['Manufacturer'] = self.settingsPanel.textboxEEGManufacturer.text()
		if self.bids_settings['natus_info']['EEGElectrodeInfo']['Type'] != self.settingsPanel.textboxEEGType.text():
			self.bids_settings['natus_info']['EEGElectrodeInfo']['Type'] = self.settingsPanel.textboxEEGType.text()
		if self.bids_settings['natus_info']['EEGElectrodeInfo']['Material'] != self.settingsPanel.textboxEEGMaterial.text():
			self.bids_settings['natus_info']['EEGElectrodeInfo']['Material'] = self.settingsPanel.textboxEEGMaterial.text()
		if self.bids_settings['natus_info']['EEGElectrodeInfo']['Diameter'] != self.settingsPanel.textboxEEGDiameter.text():
			self.bids_settings['natus_info']['EEGElectrodeInfo']['Diameter'] = self.settingsPanel.textboxEEGDiameter.text()
		
		file = os.path.join(self.application_path, 'bids_settings.json')
		json_output = json.dumps(self.bids_settings, indent=4)
		with open(file, 'w') as fid:
			fid.write(json_output)
			fid.write('\n')
				
	def onLoadDirButton(self):
		dialog = QtWidgets.QFileDialog(self)
		dialog.setFileMode(QtWidgets.QFileDialog.Directory)
		self.treeViewLoad.clear()
		self.treeViewOutput.clear()
		self.sText.setVisible(0)
		if not self.convertButton.isEnabled():
			self.convertButton.setEnabled(True)
			self.convertButton.setStyleSheet(self.convert_button_color)
		if self.cancelButton.isEnabled():
			self.cancelButton.setEnabled(False)
			self.convertButton.setStyleSheet(self.cancel_button_color)
		if self.spredButton.isEnabled():
			self.spredButton.setEnabled(False)
			self.spredButton.setStyleSheet(self.inactive_color)
		if dialog.exec_():
			self.updateStatus("Loading input directory...")
			self.input_path = dialog.selectedFiles()[0]
			self.file_info, self.chan_label_file, self.imaging_data = read_input_dir(self.input_path, self.bids_settings)
			self.treeViewLoad.setEditTriggers(self.treeViewLoad.NoEditTriggers)
			self.treeViewLoad.itemDoubleClicked.connect(self.checkEdit)
			
			imaging_data=False
			for isub, values in self.file_info.items():
				parent = QtWidgets.QTreeWidgetItem(self.treeViewLoad)
				parent.setText(0, "{}".format(str(isub)))
				
				parent.setText(10, 'Yes' if self.chan_label_file[isub] else 'No')
				parent.setText(11, 'Yes' if self.imaging_data[isub]['imaging_dir'] else 'No')
				if self.imaging_data[isub]['imaging_dir']:
					imaging_data=True
				
				parent.setTextAlignment(10, QtCore.Qt.AlignCenter)
				for ises in range(len(values)):
					for irun in range(len(values[ises])):
						date = values[ises][irun]['Date']
						time = values[ises][irun]['Time']
						date_collected = datetime.datetime.strptime(' '.join([date, time]), '%Y-%m-%d %H:%M:%S')
						
						child = QtWidgets.QTreeWidgetItem(parent)
						child.setFlags(child.flags() | ~QtCore.Qt.ItemIsSelectable)
						child.setText(0, values[ises][irun]['DisplayName'])
						child.setText(1, "{}".format(date_collected.date()))
						child.setTextAlignment(1, QtCore.Qt.AlignCenter)
						child.setText(2, "{}".format(date_collected.time()))
						child.setTextAlignment(2, QtCore.Qt.AlignCenter)
						child.setText(3, "{:.3f}".format(np.round(os.stat(os.path.join(self.input_path, values[ises][irun]['SubDir'], values[ises][irun]['FileName'])).st_size/1000000000,3)))
						child.setTextAlignment(3, QtCore.Qt.AlignCenter)
						child.setText(4, str(values[ises][irun]['SamplingFrequency']))
						child.setTextAlignment(4, QtCore.Qt.AlignCenter)
						child.setText(5, "{:.3f}".format(values[ises][irun]['TotalRecordTime']))
						child.setTextAlignment(5, QtCore.Qt.AlignCenter)
						child.setText(6, values[ises][irun]['EDF_type'])
						child.setTextAlignment(6, QtCore.Qt.AlignCenter)
						
						combobox_type = QtWidgets.QComboBox()
						combobox_type.addItems(['iEEG','Scalp'])
						combobox_type.setCurrentText(values[ises][irun]['RecordingType'])
						layout1 = QtWidgets.QHBoxLayout()
						layout1.setContentsMargins(4,0,4,0)
						combobox_type.setLayout(layout1)
						self.treeViewLoad.setItemWidget(child, 7, combobox_type)
						
						combobox_length = QtWidgets.QComboBox()
						combobox_length.addItems(['Full','Clip','CS'])
						combobox_length.setCurrentText(values[ises][irun]['RecordingLength'])
						layout2 = QtWidgets.QHBoxLayout()
						layout2.setContentsMargins(4,0,4,0)
						combobox_length.setLayout(layout2)
						self.treeViewLoad.setItemWidget(child, 8, combobox_length)
						
						combobox_retpro = QtWidgets.QComboBox()
						combobox_retpro.addItems(['Ret','Pro'])
						combobox_retpro.setCurrentText(values[ises][irun]['Retro_Pro'])
						layout0 = QtWidgets.QHBoxLayout()
						layout0.setContentsMargins(4,0,4,0)
						combobox_retpro.setLayout(layout0)
						self.treeViewLoad.setItemWidget(child, 9, combobox_retpro)
						
						child.setText(10, 'Yes' if values[ises][irun]['ses_chan_label'] else 'No')
						child.setTextAlignment(10, QtCore.Qt.AlignCenter)
						
			header_padding = 12
			self.treeViewLoad.setHeaderItem(QtWidgets.QTreeWidgetItem([self.padentry('Name', 25), self.padentry("Date", header_padding), self.padentry("Time", header_padding), 
															  self.padentry("Size", header_padding), self.padentry("Frequency", header_padding), self.padentry("Duration", header_padding),
															  self.padentry("EDF Type",header_padding), self.padentry('Type', header_padding), self.padentry('Task', header_padding),
															  self.padentry('Ret/Pro', header_padding), self.padentry('Channel File', header_padding), self.padentry('Imaging Data', header_padding)]))
			
			for icol in range(11):
				self.treeViewLoad.header().setSectionResizeMode(icol,self.treeViewLoad.header().ResizeToContents)
				
			self.treeViewLoad.header().setDefaultAlignment(QtCore.Qt.AlignHCenter)

			font = QtGui.QFont()
			font.setBold(True)
			self.treeViewLoad.header().setFont(font)
			
			if not imaging_data:
				self.imagingButton.setEnabled(False)
				self.imagingButton.setStyleSheet(self.inactive_color)
		
		self.updateStatus("Input directory loaded. Select output directory.")
	
	def checkEdit(self, item, column):
		if column == 4:
			self.treeViewLoad.editItem(item, column)
			
	def onOutDirButton(self):
		padding = 8
		dialog = QtWidgets.QFileDialog(self)
		dialog.setFileMode(QtWidgets.QFileDialog.Directory)
		self.treeViewOutput.clear()
		self.conversionStatus.clear()
		self.sText.setVisible(0)
		if not self.convertButton.isEnabled():
			self.convertButton.setEnabled(True)
			self.convertButton.setStyleSheet(self.convert_button_color)
		if self.cancelButton.isEnabled():
			self.cancelButton.setEnabled(False)
			self.convertButton.setStyleSheet(self.cancel_button_color)
		if self.spredButton.isEnabled():
			self.spredButton.setEnabled(False)
			self.spredButton.setStyleSheet(self.inactive_color)
			
		if dialog.exec_():
			self.updateStatus("Loading output directory...")
			self.output_path = dialog.selectedFiles()[0]
			root = self.treeViewLoad.invisibleRootItem()
			parent_count = root.childCount()
			
			for i in range(parent_count):
				sub = root.child(i).text(0)
				child_count = root.child(i).childCount()
				ses_cnt = 0
				for j in range(child_count):
					item = root.child(i).child(j)
					for ses_cnt in range(len(self.file_info[sub])):
						for irun in range(len(self.file_info[sub][ses_cnt])):
							if self.file_info[sub][ses_cnt][irun]['DisplayName'] == item.text(0):
								if self.file_info[sub][ses_cnt][irun]['SamplingFrequency'] != int(item.text(4)):
									self.file_info[sub][ses_cnt][irun]['SamplingFrequency'] = int(item.text(4))
									self.file_info[sub][ses_cnt][irun]['TotalRecordTime'] = round((((self.file_info[sub][ses_cnt][irun]['NRecords']*(int(item.text(4))*self.file_info[sub][ses_cnt][irun]['RecordLength']))/int(item.text(4)))/60)/60,3)
								
								if self.file_info[sub][ses_cnt][irun]['RecordingType'] != self.treeViewLoad.itemWidget(item, 7).currentText():
									self.file_info[sub][ses_cnt][irun]['RecordingType'] = self.treeViewLoad.itemWidget(item, 7).currentText()
								
								if self.file_info[sub][ses_cnt][irun]['RecordingLength'] != self.treeViewLoad.itemWidget(item, 8).currentText():
									self.file_info[sub][ses_cnt][irun]['RecordingLength'] = self.treeViewLoad.itemWidget(item, 8).currentText()
							
								if self.file_info[sub][ses_cnt][irun]['Retro_Pro'] != self.treeViewLoad.itemWidget(item, 9).currentText():
									self.file_info[sub][ses_cnt][irun]['Retro_Pro'] = self.treeViewLoad.itemWidget(item, 9).currentText()
								
						
			self.new_sessions = read_output_dir(self.output_path, self.file_info, self.offsetDate.isChecked(), self.bids_settings, participants_fname=None)
			
#			isub = list(new_sessions)[0]
#			values = new_sessions[isub]
# 			if len(self.imaging_data.items()) >0:
# 				if not self.imagingButton.isEnabled():
# 					self.imagingButton.setEnabled(True)
# 					self.imagingButton.setStyleSheet(self.convert_button_color)
# 			else:
# 				if self.imagingButton.isEnabled():
# 					self.imagingButton.setEnabled(False)
# 					self.imagingButton.setStyleSheet(self.inactive_color)
					
			for isub, values in self.new_sessions.items():
				if values['newSessions']:
					parent = QtWidgets.QTreeWidgetItem(self.treeViewOutput)
					parent.setText(0, "{}".format(str(isub)))
					all_sessions = np.unique(values['all_sessions'])
					session_not_done = set(all_sessions).intersection(values['session_labels'])
					self.file_info_final = []
					ses_not_done_cnt = 0
					for isession in all_sessions:
						if isession in session_not_done:
							session_index = values['session_index'][ses_not_done_cnt]
							self.file_info_final.append(self.file_info[isub][session_index])
							for irun in range(len(self.file_info[isub][session_index])):
								date = self.file_info[isub][session_index][irun]['Date']
								if self.offsetDate.isChecked():
									date_study = datetime.datetime.strptime(date,"%Y-%m-%d")
									date = (date_study - datetime.timedelta(5856)).strftime('%Y-%m-%d')
								
								time = self.file_info[isub][session_index][irun]['Time']
								date_collected = datetime.datetime.strptime(' '.join([date, time]), '%Y-%m-%d %H:%M:%S')
								child = QtWidgets.QTreeWidgetItem(parent)
								child.setFlags(child.flags() | QtCore.Qt.ItemIsUserCheckable)
								
								child.setText(0, self.padentry(self.file_info[isub][session_index][irun]['DisplayName'], padding))
								child.setCheckState(0, QtCore.Qt.Unchecked)
								child.setText(1, self.padentry(isession, padding))
								child.setText(2, "{}".format(date_collected.date()))
								child.setTextAlignment(2, QtCore.Qt.AlignCenter)
								child.setText(3, "{}".format(date_collected.time()))
								child.setTextAlignment(3, QtCore.Qt.AlignCenter)
								child.setText(4, str(self.file_info[isub][session_index][irun]['SamplingFrequency']))
								child.setTextAlignment(4, QtCore.Qt.AlignCenter)
								child.setText(5, "{:.3f}".format(self.file_info[isub][session_index][irun]['TotalRecordTime']))
								child.setTextAlignment(5, QtCore.Qt.AlignCenter)
								
								combobox_type_out = QtWidgets.QComboBox()
								combobox_type_out.addItems(['iEEG','Scalp'])
								combobox_type_out.setCurrentText(self.file_info[isub][session_index][irun]['RecordingType'])
								layout3 = QtWidgets.QHBoxLayout()
								layout3.setContentsMargins(4,0,4,0)
								combobox_type_out.setLayout(layout3)
								self.treeViewOutput.setItemWidget(child, 6, combobox_type_out)
								
								combobox_length_out = QtWidgets.QComboBox()
								combobox_length_out.addItems(['Full','Clip','CS'])
								combobox_length_out.setCurrentText(self.file_info[isub][session_index][irun]['RecordingLength'])
								layout4 = QtWidgets.QHBoxLayout()
								layout4.setContentsMargins(4,0,4,0)
								combobox_length_out.setLayout(layout4)
								self.treeViewOutput.setItemWidget(child, 7, combobox_length_out)
								
								combobox_retpro_out = QtWidgets.QComboBox()
								combobox_retpro_out.addItems(['Ret','Pro'])
								combobox_retpro_out.setCurrentText(self.file_info[isub][session_index][irun]['Retro_Pro'])
								layout5 = QtWidgets.QHBoxLayout()
								layout5.setContentsMargins(4,0,4,0)
								combobox_retpro_out.setLayout(layout5)
								self.treeViewOutput.setItemWidget(child, 8, combobox_retpro_out)
						
						
							ses_not_done_cnt += 1
							
						else:
							old_isession = [x[0] for x in values['session_changes'] if isession == x[1]][0]
							
							# Load output scan file
							scans_tsv = pd.read_csv(os.path.join(self.output_path, isub, isub + '_scans.tsv'), sep='\t')
							name_idx = [i for i,z in enumerate(list(scans_tsv['filename'])) if old_isession in z]
							for irun in name_idx:
								date = scans_tsv.loc[irun, 'acq_time'].split('T')[0]
								time = scans_tsv.loc[irun, 'acq_time'].split('T')[1]
								file_n = scans_tsv.loc[irun, 'filename'].split('.edf')[0] + '.json'
								with open(os.path.join(self.output_path, isub, old_isession, file_n)) as side_file:
									side_file_temp = json.load(side_file)
								display_name = scans_tsv.loc[irun, 'filename'].split('.edf')[0]
							
								retpro_out = 'Pro'
								length_out = []
								if 'EPL' in isub:
									old_sub = '_'.join([''.join(' '.join(re.split('(\d+)', isub.split('-')[-1])).split()[:2])] + ' '.join(re.split('(\d+)', isub.split('-')[-1])).split()[2:])
									old_ses = '_'.join([' '.join(re.split('(\D+)', isession.split('-')[-1])).split()[0], ''.join(' '.join(re.split('(\D+)', isession.split('-')[-1])).split()[1:3]), ' '.join(re.split('(\D+)', isession.split('-')[-1])).split()[-1]])
								
									display_name = old_sub + '_' + old_ses
								
									if 'full' in side_file_temp['TaskName'].lower():
										length_out = 'Full'
									elif 'clip' in side_file_temp['TaskName'].lower():
										length_out = 'Clip'
									elif 'cs' in side_file_temp['TaskName'].lower():
										length_out = 'CS'
								
									if length_out:
										display_name = display_name + '_' + length_out.upper()
									
									if 'ret' in side_file_temp['TaskName'].lower():
										retpro_out = 'Ret'
										display_name = display_name + '_' + retpro_out.upper()

								child = QtWidgets.QTreeWidgetItem(parent)
								child.setFlags(child.flags() | QtCore.Qt.ItemIsUserCheckable)
								
								child.setText(0, self.padentry(display_name, padding))
								child.setCheckState(0, QtCore.Qt.Checked)
								child.setText(1, self.padentry(isession, padding))
								child.setText(2, "{}".format(date))
								child.setTextAlignment(2, QtCore.Qt.AlignCenter)
								child.setText(3, "{}".format(time))
								child.setTextAlignment(3, QtCore.Qt.AlignCenter)
								child.setText(4, str(side_file_temp['SamplingFrequency']))
								child.setTextAlignment(4, QtCore.Qt.AlignCenter)
								child.setText(5, "{:.3f}".format(side_file_temp['RecordingDuration']))
								child.setTextAlignment(5, QtCore.Qt.AlignCenter)
								
								combobox_type_out = QtWidgets.QComboBox()
								combobox_type_out.addItems(['iEEG','Scalp'])
								
								if 'SEEGChannelCount' in side_file_temp:
									combobox_type_out.setCurrentText('iEEG')
								elif 'EEGChannelCount' in side_file_temp:
									combobox_type_out.setCurrentText('Scalp')
								
								layout3 = QtWidgets.QHBoxLayout()
								layout3.setContentsMargins(4,0,4,0)
								combobox_type_out.setLayout(layout3)
								self.treeViewOutput.setItemWidget(child, 6, combobox_type_out)
								
								combobox_length_out = QtWidgets.QComboBox()
								combobox_length_out.addItems(['Full','Clip','CS'])
								if length_out:
									combobox_length_out.setCurrentText(length_out)
								layout4 = QtWidgets.QHBoxLayout()
								layout4.setContentsMargins(4,0,4,0)
								combobox_length_out.setLayout(layout4)
								self.treeViewOutput.setItemWidget(child, 7, combobox_length_out)
								
								combobox_retpro_out = QtWidgets.QComboBox()
								combobox_retpro_out.addItems(['Ret','Pro'])
								combobox_retpro_out.setCurrentText(retpro_out)
								layout5 = QtWidgets.QHBoxLayout()
								layout5.setContentsMargins(4,0,4,0)
								combobox_retpro_out.setLayout(layout5)
								self.treeViewOutput.setItemWidget(child, 8, combobox_retpro_out)
								
					self.file_info[isub] = self.file_info_final
				else:
					parent = QtWidgets.QTreeWidgetItem(self.treeViewOutput)
					parent.setText(0, "{}".format(str(isub)))
					
					for x in range(values['num_sessions']):
						scans_tsv = pd.read_csv(os.path.join(self.output_path, isub, isub + '_scans.tsv'), sep='\t')
						name_idx = [i for i,z in enumerate(list(scans_tsv['filename'])) if values['session_labels'][x] in z][-1]
						date = scans_tsv.loc[name_idx, 'acq_time'].split('T')[0]
						time = scans_tsv.loc[name_idx, 'acq_time'].split('T')[1]
						file_n = scans_tsv.loc[name_idx, 'filename'].split('.edf')[0] + '.json'
						with open(os.path.join(self.output_path, isub, values['session_labels'][x], file_n)) as side_file:
							side_file_temp = json.load(side_file)
						
						
						for irun in range(len(self.file_info[isub][x])):
							retpro_out = 'Pro'
							length_out = []
							if 'EPL' in isub:
								old_sub = '_'.join([''.join(' '.join(re.split('(\d+)', isub.split('-')[-1])).split()[:2])] + ' '.join(re.split('(\d+)', isub.split('-')[-1])).split()[2:])
								old_ses = '_'.join([' '.join(re.split('(\D+)', values['session_labels'][x].split('-')[-1])).split()[0], ''.join(' '.join(re.split('(\D+)', values['session_labels'][x].split('-')[-1])).split()[1:3]), ' '.join(re.split('(\D+)', values['session_labels'][x].split('-')[-1])).split()[-1]])
							
								display_name = old_sub + '_' + old_ses
							
								if 'full' in side_file_temp['TaskName'].lower():
									length_out = 'Full'
								elif 'clip' in side_file_temp['TaskName'].lower():
									length_out = 'Clip'
								elif 'cs' in side_file_temp['TaskName'].lower():
									length_out = 'CS'
							
								if length_out:
									display_name = display_name + '_' + length_out.upper()
								
								if 'ret' in side_file_temp['TaskName'].lower():
									retpro_out = 'Ret'
									display_name = display_name + '_' + retpro_out.upper()
							else:
								display_name = self.file_info[isub][x][irun]['DisplayName']
							
							child = QtWidgets.QTreeWidgetItem(parent)
							child.setFlags(child.flags() | QtCore.Qt.ItemIsUserCheckable)
							child.setText(0, self.padentry(display_name, padding))
							child.setCheckState(0, QtCore.Qt.Checked)
							child.setText(1, self.padentry(values['session_labels'][x],padding))
							child.setText(2, "{}".format(date))
							child.setTextAlignment(2, QtCore.Qt.AlignCenter)
							child.setText(3, "{}".format(time))
							child.setTextAlignment(3, QtCore.Qt.AlignCenter)
							child.setText(4, str(side_file_temp['SamplingFrequency']))
							child.setTextAlignment(4, QtCore.Qt.AlignCenter)
							child.setText(5, "{:.3f}".format(side_file_temp['RecordingDuration']))
							child.setTextAlignment(5, QtCore.Qt.AlignCenter)
							
							combobox_type_out = QtWidgets.QComboBox()
							combobox_type_out.addItems(['iEEG','Scalp'])
								
							if 'SEEGChannelCount' in side_file_temp:
								combobox_type_out.setCurrentText('iEEG')
							elif 'EEGChannelCount' in side_file_temp:
								combobox_type_out.setCurrentText('Scalp')
									
							layout3 = QtWidgets.QHBoxLayout()
							layout3.setContentsMargins(4,0,4,0)
							combobox_type_out.setLayout(layout3)
							self.treeViewOutput.setItemWidget(child, 6, combobox_type_out)
							
							combobox_length_out = QtWidgets.QComboBox()
							combobox_length_out.addItems(['Full','Clip','CS'])
							if length_out:
								combobox_length_out.setCurrentText(length_out)
							layout4 = QtWidgets.QHBoxLayout()
							layout4.setContentsMargins(4,0,4,0)
							combobox_length_out.setLayout(layout4)
							self.treeViewOutput.setItemWidget(child, 7, combobox_length_out)
							
							combobox_retpro_out = QtWidgets.QComboBox()
							combobox_retpro_out.addItems(['Ret','Pro'])
							combobox_retpro_out.setCurrentText(retpro_out)
							layout5 = QtWidgets.QHBoxLayout()
							layout5.setContentsMargins(4,0,4,0)
							combobox_retpro_out.setLayout(layout5)
							self.treeViewOutput.setItemWidget(child, 8, combobox_retpro_out)
							
			self.sText.setVisible(1)
			
			header_padding = 12
			self.treeViewOutput.setHeaderItem(QtWidgets.QTreeWidgetItem([self.padentry('Name', 25), self.padentry('Session', header_padding), self.padentry("Date", header_padding), self.padentry("Time", header_padding), 
															  self.padentry("Frequency", header_padding), self.padentry("Duration", header_padding),
															  self.padentry('Type', header_padding), self.padentry('Task', header_padding), self.padentry('Ret/Pro', header_padding)]))
			
			for icol in range(9):
				self.treeViewOutput.header().setSectionResizeMode(icol,self.treeViewOutput.header().ResizeToContents)
				
			self.treeViewOutput.header().setDefaultAlignment(QtCore.Qt.AlignHCenter)
			
			font = QtGui.QFont()
			font.setBold(True)
			self.treeViewOutput.header().setFont(font)
						
		self.updateStatus("Output directory loaded. Ready to convert.")
	
	def onConvertButton(self):
		if getattr(sys, 'frozen', False):
			# frozen
			source_dir = os.path.dirname(sys.executable)
		else:
			# unfrozen
			source_dir = os.path.dirname(os.path.realpath(__file__))
	
		self.conversionStatus.clear()
		self.updateStatus("Converting files...")
		
		### convert script
		dataset_fname = bidsHelper(output_path=self.output_path).write_dataset(return_fname=True)
		if not os.path.exists(dataset_fname):
			bidsHelper(output_path=self.output_path, bids_settings=self.bids_settings).write_dataset()

		# Add a bidsignore file
		if '.bidsignore' not in os.listdir(self.output_path):
			shutil.copy(os.path.join(source_dir, 'static', 'bidsignore'), 
						os.path.join(self.output_path,'.bidsignore'))
		
		# Add a README file
		if not os.path.exists(os.path.join(self.output_path,'README')):
			shutil.copy(os.path.join(source_dir, 'static', 'README'), 
						os.path.join(self.output_path,'README'))
			
		# Add a participants tsv file
		participants_fname = bidsHelper(output_path=self.output_path).write_participants(return_fname=True)
		if os.path.exists(participants_fname):
			self.participant_tsv = pd.read_csv(participants_fname, sep='\t')
		else:
			bidsHelper(output_path=self.output_path).write_participants()
			self.participant_tsv = pd.read_csv(participants_fname, sep='\t')
		
		# Set Qthread
		self.worker = edf2bids()

		self.worker.bids_settings = self.bids_settings
		self.worker.new_sessions = self.new_sessions
		self.worker.file_info = self.file_info
		self.worker.chan_label_file = self.chan_label_file
		self.worker.input_path = self.input_path
		self.worker.output_path = self.output_path
		self.worker.script_path = source_dir
		self.worker.coordinates = None
		self.worker.electrode_imp = None
		self.worker.make_dir = True
		self.worker.overwrite = True
		self.worker.verbose = False
		self.worker.deidentify_source = self.deidentifyInputDir.isChecked()
		self.worker.offset_date = self.offsetDate.isChecked()
		self.worker.test_conversion = self.testConvert.isChecked()
		self.worker.annotations_only = self.annotationsOnly.isChecked()
		
		# Set Qthread signals
		self.worker.signals.progressEvent.connect(self.conversionStatusUpdate)
		self.worker.signals.finished.connect(self.doneConversion)
		
		# Execute
		self.threadpool.start(self.worker) 
# 		self.worker.start()
		
		# Set button states
		self.cancelButton.setEnabled(True)
		self.cancelButton.setStyleSheet(self.cancel_button_color)
		self.cancelButton.clicked.connect(self.onCancelButton)
		self.convertButton.setEnabled(False)
		self.convertButton.setStyleSheet(self.inactive_color)
	
	def padentry(self, buf, num):
		"""
		Adds padding to string data.
		
		:param buf: input string to pad
		:type buf: string
		:param num: Length of desired output buffer.
		:type num: integer
	
		:return buffer: The input string padded to desired size.
		:type butter: string
	
		"""
		
		if isinstance(buf, float):
			num -= len("{:.3f}".format(buf))
			buffer = ((' ' * int(num/2)) + "{:.3f}".format(buf) + (' ' * int(num/2)))
		else:
			num -= len(str(buf))
			buffer = ((' ' * int(num/2)) + str(buf) + (' ' * int(num/2)))

		return buffer

	def onCancelButton(self):
		self.worker.kill()
		self.updateStatus("Conversion cancel requested...")
		self.conversionStatus.appendPlainText('Cancelling data conversion...\n')
		self.userAborted = True
		self.cancelButton.setEnabled(False)
		self.cancelButton.setStyleSheet(self.inactive_color)
		
	def updateStatus(self, update):
		"""Updates the status bar located at the bottom of the window.
		param: update
			The message to be displayed.
		"""
		self.statusbar.showMessage(update)
	
	def conversionStatusUpdate(self, text):
		if '%' in text:
			if text == 'copy10%':
				self.conversionStatus.appendPlainText('Copying File: ' + text.strip('copy'))
				self.conversionStatus.moveCursor(QtGui.QTextCursor.End)
			elif 'annot' in text:
				self.conversionStatus.insertPlainText(' ' + text.strip('annot'))
			else:
				self.conversionStatus.insertPlainText(' ' + text)
		elif text == '...':
				self.conversionStatus.appendPlainText('Extract/Scrub Annotations: ' + text)
				self.conversionStatus.moveCursor(QtGui.QTextCursor.End)
		else:
			self.conversionStatus.appendPlainText(text)
	
	def doneConversion(self):
		if self.userAborted:
			self.conversionStatus.appendPlainText('\nAborted conversion at {}'.format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
			self.conversionStatus.appendPlainText('File coversion incomplete: Please delete output directory and close program.')
			self.updateStatus("Conversion aborted.")
			self.treeViewOutput.clear()
			self.treeViewLoad.clear()
			
			self.spredButton.setEnabled(False)
			self.spredButton.setStyleSheet(self.inactive_color)
		
		else:
			self.conversionStatus.appendPlainText('\nCompleted conversion at {}'.format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
			self.conversionStatus.appendPlainText('Your data has been BIDsified!\n')
			self.updateStatus("BIDs conversion complete.")
			
			self.spredButton.setEnabled(True)
			self.spredButton.setStyleSheet(self.spred_button_color)
			
		self.cancelButton.setEnabled(False)
		self.cancelButton.setStyleSheet(self.inactive_color)
		self.convertButton.setEnabled(False)
		self.convertButton.setStyleSheet(self.inactive_color)
	
	def onSpredButton(self):
		self.updateStatus('Converting to SPReD format...')
		QtGui.QGuiApplication.processEvents()
		
		# Set Qthread
		self.worker = bids2spred()
		self.worker.output_path = self.output_path
		
		# Set Qthread signals
		self.worker.signals.progressEvent.connect(self.conversionStatusUpdate)
		self.worker.signals.finished.connect(self.doneSPReDConversion)
		
		# Execute
		self.threadpool.start(self.worker)
# 		self.worker.start()
		
		# Set button states
		self.cancelButton.setEnabled(True)
		self.cancelButton.setStyleSheet(self.cancel_button_color)
		self.cancelButton.clicked.connect(self.onCancelButton)
		self.spredButton.setEnabled(False)
		self.spredButton.setStyleSheet(self.inactive_color)
		
	def doneSPReDConversion(self):
		if self.userAborted:
			self.conversionStatus.appendPlainText('\nAborted SPReD conversion at {}'.format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
			self.conversionStatus.appendPlainText('SPReD coversion incomplete: Please delete output directory and close program.')
			self.updateStatus("SPReD conversion aborted.")
			self.treeViewOutput.clear()
			self.treeViewLoad.clear()
		else:
			self.conversionStatus.appendPlainText('Completed SPReD conversion at {}'.format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
			self.conversionStatus.appendPlainText('Your data has been SPReDified!\n')
			self.updateStatus("SPReD conversion complete.")
			
		self.spredButton.setEnabled(False)
		self.spredButton.setStyleSheet(self.inactive_color)
		self.cancelButton.setEnabled(False)
		self.cancelButton.setStyleSheet(self.inactive_color)
		self.convertButton.setEnabled(False)
		self.convertButton.setStyleSheet(self.inactive_color)
	
	def onImagingButton(self):
		self.updateStatus('De-identifying imaging data...')
		QtGui.QGuiApplication.processEvents()
		
		# Set Qthread
		self.worker = dicomAnon()
		self.worker.input_path = self.input_path
		self.worker.output_path = self.output_path
		self.worker.imaging_data = self.imaging_data
		
		# Set Qthread signals
		self.worker.signals.progressEvent.connect(self.conversionStatusUpdate)
		self.worker.signals.finished.connect(self.doneImagingConversion)
		
		# Execute
		self.threadpool.start(self.worker)
# 		self.worker.start()
		
		# Set button states
		self.cancelButton.setEnabled(True)
		self.cancelButton.setStyleSheet(self.cancel_button_color)
		self.cancelButton.clicked.connect(self.onCancelButton)
		self.imagingButton.setEnabled(False)
		self.imagingButton.setStyleSheet(self.inactive_color)
	
	def doneImagingConversion(self):
		if self.userAborted:
			self.conversionStatus.appendPlainText('\nAborted image de-identification at {}'.format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
			self.conversionStatus.appendPlainText('Image de-identification incomplete: Please delete output directory and close program.')
			self.updateStatus("Image de-identification aborted.")
			self.treeViewOutput.clear()
			self.treeViewLoad.clear()
		else:
			self.conversionStatus.appendPlainText('Completed image de-identification at {}'.format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
			self.conversionStatus.appendPlainText('Your imaging data has been de-identified!\n')
			self.updateStatus("Image de-identification complete.")
			
		self.imagingButton.setEnabled(False)
		self.imagingButton.setStyleSheet(self.inactive_color)
		self.cancelButton.setEnabled(False)
		self.cancelButton.setStyleSheet(self.inactive_color)
		self.convertButton.setEnabled(False)
		self.convertButton.setStyleSheet(self.inactive_color)
		
def main():
	app = QtWidgets.QApplication(sys.argv)
	window = MainWindow()
	window.show()
	app.exec_()
	
if __name__ == '__main__':	
	main()