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
from dicom2bids import dicom2bids

from helpers import read_input_dir, read_output_dir, bidsHelper, warningBox

class Delegate(QtWidgets.QStyledItemDelegate):
	def initStyleOption(self, option, index):
		super().initStyleOption(option, index)
		columns = (0, 1)
		padding = len(index.sibling(index.row(), 0).data())
		if padding <=1:
			text = str(6*" ").join([index.sibling(index.row(), c).data() for c in columns])
		else:
			text = str(4*" ").join([index.sibling(index.row(), c).data() for c in columns])
		option.text = text

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
					'Diameter': 0.86
					},
			'EEGElectrodeInfo': {
					'Manufacturer': 'AdTech',
					'Type': 'scalp',
					'Material': 'Platinum',
					'Diameter': 10
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
		
		self.output_path=None
		
		self.cancel_button_color = "background-color: rgb(255,0,0);color: black"
		self.pause_button_color = "background-color: rgb(173, 127, 168);color: black"
		self.spred_button_color = "background-color: rgb(0, 85, 255);color: black"
		self.convert_button_color = "background-color: rgb(79, 232, 109);color: black"
		self.inactive_color = "background-color: rgb(160, 160, 160);color: rgb(130, 130, 130)"
		
		self.updateStatus("Welcome to data2bids converter. Load your directory.")
		self.sText.setVisible(0)
		#self.conversionStatus.setReadOnly(True)
		self.cancelButton.setEnabled(False)
		self.cancelButton.setStyleSheet(self.inactive_color)
		self.pauseButton.setEnabled(False)
		self.pauseButton.setStyleSheet(self.inactive_color)
		self.spredButton.setEnabled(False)
		self.spredButton.setStyleSheet(self.inactive_color)
		self.userAborted = False
		self.eegConversionDone=False
		self.imagingConversionDone=False
		self.imagingDataPresent=False
		
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
														  'offset_dates': False}
			
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
		bids_file = os.path.join(self.application_path, 'bids_settings.json')
		with open(bids_file) as settings_file:
			bids_settings_json_temp = json.load(settings_file)
		
		if 'lastInputDirectory' not in bids_settings_json_temp.keys():
			bids_settings_json_temp['lastInputDirectory']=[]
			json_output = json.dumps(bids_settings_json_temp, indent=4)
			with open(bids_file, 'w') as fid:
				fid.write(json_output)
				fid.write('\n')
			
			with open(bids_file) as settings_file:
				bids_settings_json_temp = json.load(settings_file)
		
		if bids_settings_json_temp['lastInputDirectory']:
			dialog = QtWidgets.QFileDialog(self, directory=bids_settings_json_temp['lastInputDirectory'])
		else:
			dialog = QtWidgets.QFileDialog(self)
			
		dialog.setFileMode(QtWidgets.QFileDialog.DirectoryOnly)
		self.treeViewLoad.clear()
		self.treeViewOutput.clear()
		self.sText.setVisible(0)
		if not self.convertButton.isEnabled():
			self.convertButton.setEnabled(True)
			self.convertButton.setStyleSheet(self.convert_button_color)
		if self.cancelButton.isEnabled():
			self.cancelButton.setEnabled(False)
			self.convertButton.setStyleSheet(self.cancel_button_color)
		if self.pauseButton.isEnabled():
			self.pauseButton.setEnabled(False)
			self.pauseButton.setStyleSheet(self.inactive_color)
		if self.spredButton.isEnabled():
			self.spredButton.setEnabled(False)
			self.spredButton.setStyleSheet(self.inactive_color)
		if dialog.exec_():
			self.updateStatus("Loading input directory...")
			self.input_path = dialog.selectedFiles()[0]
			if self.input_path != bids_settings_json_temp['lastInputDirectory']:
				bids_settings_json_temp['lastInputDirectory']=self.input_path
				json_output = json.dumps(bids_settings_json_temp, indent=4)
				with open(bids_file, 'w') as fid:
					fid.write(json_output)
					fid.write('\n')
			
			self.file_info, self.chan_label_file, self.imaging_data = read_input_dir(self.input_path, self.bids_settings)
			self.treeViewLoad.setEditTriggers(self.treeViewLoad.NoEditTriggers)
			self.treeViewLoad.itemDoubleClicked.connect(self.checkEdit)
			
			for isub, values in self.file_info.items():
				parent = QtWidgets.QTreeWidgetItem(self.treeViewLoad)
				parent.setText(0, "{}".format(str(isub)))
				
				parent.setText(10, 'Yes' if self.chan_label_file[isub] else 'No')
				parent.setText(11, 'Yes' if self.imaging_data[isub]['imaging_dir'] else 'No')
				if self.imaging_data[isub]['imaging_dir']:
					self.imagingDataPresent=True
				
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

						chan_type = 'SEEG' if 'SEEG' in list(values[ises][irun]['ChanInfo'].keys()) else 'EEG'
						
						model = QtGui.QStandardItemModel()
						model.appendRow([QtGui.QStandardItem("View Labels"), QtGui.QStandardItem("")])
						row_cnt=1
						for i in list(values[ises][irun]['ChanInfo'][chan_type]['ChanName']):
							it1 = QtGui.QStandardItem(f"{row_cnt}")
							it1.setEnabled(False)
							it2 = QtGui.QStandardItem(f"{i}")
							it2.setEnabled(False)
							model.appendRow([it1, it2])
							row_cnt +=1
						
						
						combobox_labels = QtWidgets.QComboBox()
						delegate = Delegate(combobox_labels)
						combobox_labels.setItemDelegate(delegate)
						combobox_labels.setModel(model)
						combobox_labels.setStyleSheet("QAbstractItemView{color: black}")
						combobox_labels.setFont(QtGui.QFont("Arial", 10))

						
						layout_lab = QtWidgets.QHBoxLayout()
						layout_lab.setContentsMargins(4,0,4,0)
						combobox_labels.setLayout(layout_lab)

						self.treeViewLoad.setItemWidget(child, 12, combobox_labels)

						
			header_padding = 14
			self.treeViewLoad.setHeaderItem(QtWidgets.QTreeWidgetItem([self.padentry('Name', 120), self.padentry("Date", 20), self.padentry("Time", 14), 
															  self.padentry("Size", 12), self.padentry("Frequency", 12), self.padentry("Duration", 12),
															  self.padentry("EDF Type",12), self.padentry('Type', header_padding), self.padentry('Task', header_padding),
															  self.padentry('Ret/Pro', header_padding), self.padentry('Channel File', 10), self.padentry('Imaging Data', 10),
															  self.padentry('Channel Labels', 20)]))
			
			self.treeViewLoad.header().setDefaultAlignment(QtCore.Qt.AlignHCenter)
			
			header = self.treeViewLoad.header()
			
			for column in range(header.count()):
				header.setSectionResizeMode(column, self.treeViewLoad.header().ResizeToContents)
				width = header.sectionSize(column)
				header.setSectionResizeMode(column, self.treeViewLoad.header().Interactive)
				header.resizeSection(column, width)
			
			
			font = QtGui.QFont()
			font.setBold(True)
			self.treeViewLoad.header().setFont(font)
			
			if not self.imagingDataPresent:
				self.imagingButton.setEnabled(False)
				self.imagingButton.setStyleSheet(self.inactive_color)
		
		self.updateStatus("Input directory loaded. Select output directory.")
		
		if all(len(value) == 0 for value in self.file_info.values()):
			self.convertButton.setEnabled(False)
			self.convertButton.setStyleSheet(self.inactive_color)

	def checkEdit(self, item, column):
		if column == 4:
			self.treeViewLoad.editItem(item, column)
			
	def onOutDirButton(self):
		bids_file = os.path.join(self.application_path, 'bids_settings.json')
		with open(bids_file) as settings_file:
			bids_settings_json_temp = json.load(settings_file)
		
		if 'lastOutputDirectory' not in bids_settings_json_temp.keys():
			bids_settings_json_temp['lastOutputDirectory']=[]
			json_output = json.dumps(bids_settings_json_temp, indent=4)
			with open(bids_file, 'w') as fid:
				fid.write(json_output)
				fid.write('\n')
			
			with open(bids_file) as settings_file:
				bids_settings_json_temp = json.load(settings_file)
		
		if bids_settings_json_temp['lastOutputDirectory']:
			dialog = QtWidgets.QFileDialog(self, directory=bids_settings_json_temp['lastOutputDirectory'])
		else:
			dialog = QtWidgets.QFileDialog(self)
			
		padding = 8
		dialog.setFileMode(QtWidgets.QFileDialog.Directory)
		self.treeViewOutput.clear()
		self.conversionStatus.clear()
		self.sText.setVisible(0)
		
		if not self.convertButton.isEnabled() and not all(len(value) == 0 for value in self.file_info.values()):
			self.convertButton.setEnabled(True)
			self.convertButton.setStyleSheet(self.convert_button_color)
		if self.cancelButton.isEnabled():
			self.cancelButton.setEnabled(False)
			self.convertButton.setStyleSheet(self.cancel_button_color)
		if self.spredButton.isEnabled():
			self.spredButton.setEnabled(False)
			self.spredButton.setStyleSheet(self.inactive_color)
		if self.pauseButton.isEnabled():
			self.pauseButton.setEnabled(False)
			self.pauseButton.setStyleSheet(self.inactive_color)
		if not self.imagingDataPresent:
			self.imagingButton.setEnabled(False)
			self.imagingButton.setStyleSheet(self.inactive_color)
				
		if dialog.exec_():
			self.updateStatus("Loading output directory...")
			self.output_path = dialog.selectedFiles()[0]
			
			if len(os.listdir(self.output_path)) != 0:
				warningBox("Output directory is not empty!")
				return
		
			if self.output_path != bids_settings_json_temp['lastOutputDirectory']:
				bids_settings_json_temp['lastOutputDirectory']=self.output_path
				json_output = json.dumps(bids_settings_json_temp, indent=4)
				with open(bids_file, 'w') as fid:
					fid.write(json_output)
					fid.write('\n')
				
			root = self.treeViewLoad.invisibleRootItem()
			parent_count = root.childCount()
			
			for i in range(parent_count):
				sub = root.child(i).text(0)
				child_count = root.child(i).childCount()
				
				self.file_info[sub]=sum(self.file_info[sub],[])
				
				ses_cnt = 0
				for j in range(child_count):
					item = root.child(i).child(j)
					if self.file_info[sub][ses_cnt]['DisplayName'] == item.text(0):
						if self.file_info[sub][ses_cnt]['SamplingFrequency'] != int(item.text(4)):
							self.file_info[sub][ses_cnt]['SamplingFrequency'] = int(item.text(4))
							self.file_info[sub][ses_cnt]['TotalRecordTime'] = round((((self.file_info[sub][ses_cnt]['NRecords']*(int(item.text(4))*self.file_info[sub][ses_cnt]['RecordLength']))/int(item.text(4)))/60)/60,3)
						
						if self.file_info[sub][ses_cnt]['RecordingType'] != self.treeViewLoad.itemWidget(item, 7).currentText():
							self.file_info[sub][ses_cnt]['RecordingType'] = self.treeViewLoad.itemWidget(item, 7).currentText()
						
						if self.file_info[sub][ses_cnt]['RecordingLength'] != self.treeViewLoad.itemWidget(item, 8).currentText():
							self.file_info[sub][ses_cnt]['RecordingLength'] = self.treeViewLoad.itemWidget(item, 8).currentText()
					
						if self.file_info[sub][ses_cnt]['Retro_Pro'] != self.treeViewLoad.itemWidget(item, 9).currentText():
							self.file_info[sub][ses_cnt]['Retro_Pro'] = self.treeViewLoad.itemWidget(item, 9).currentText()
				
					ses_cnt+=1
					
			self.new_sessions = read_output_dir(self.output_path, self.file_info, self.offsetDate.isChecked(), self.bids_settings, participants_fname=None)
			
#			isub = list(new_sessions)[1]
#			values = new_sessions[isub]
# 			if len(self.imaging_data.items()) >0:
# 				if not self.imagingButton.isEnabled():
# 					self.imagingButton.setEnabled(True)
# 					self.imagingButton.setStyleSheet(self.convert_button_color)
# 			else:
# 				if self.imagingButton.isEnabled():
# 					self.imagingButton.setEnabled(False)
# 					self.imagingButton.setStyleSheet(self.inactive_color)
			
			self.treeViewOutput.setEditTriggers(self.treeViewOutput.NoEditTriggers)
			self.treeViewOutput.itemDoubleClicked.connect(self.checkEditOutput)
			
			for isub, values in self.new_sessions.items():
				if values['newSessions']:
					parent = QtWidgets.QTreeWidgetItem(self.treeViewOutput)
					parent.setText(0, "{}".format(str(isub)))
					
					self.file_info_final = []
					ses_not_done_cnt = 0
					for isession in range(len(values['all_sessions'])):
						if values['all_sessions'][isession] in values['session_labels']:
							self.file_info_final.append(self.file_info[isub][isession])
							
							date = self.file_info[isub][isession]['Date']
							if self.offsetDate.isChecked():
								date_study = datetime.datetime.strptime(date,"%Y-%m-%d")
								date = (date_study - datetime.timedelta(5856)).strftime('%Y-%m-%d')
							
							time = self.file_info[isub][isession]['Time']
							date_collected = datetime.datetime.strptime(' '.join([date, time]), '%Y-%m-%d %H:%M:%S')
							child = QtWidgets.QTreeWidgetItem(parent)
							child.setFlags(child.flags() | ~QtCore.Qt.ItemIsUserCheckable | ~QtCore.Qt.ItemIsSelectable)
							
							child.setText(0, self.padentry(self.file_info[isub][isession]['DisplayName'], padding))
							child.setCheckState(0, QtCore.Qt.Unchecked)
							child.setText(1, self.padentry(values['all_sessions'][isession], padding))
							child.setTextAlignment(1, QtCore.Qt.AlignCenter)
							child.setText(2, "{}".format(date_collected.date()))
							child.setTextAlignment(2, QtCore.Qt.AlignCenter)
							child.setText(3, "{}".format(date_collected.time()))
							child.setTextAlignment(3, QtCore.Qt.AlignCenter)
							child.setText(4, str(self.file_info[isub][isession]['SamplingFrequency']))
							child.setTextAlignment(4, QtCore.Qt.AlignCenter)
							child.setText(5, "{:.3f}".format(self.file_info[isub][isession]['TotalRecordTime']))
							child.setTextAlignment(5, QtCore.Qt.AlignCenter)
							
							combobox_type_out = QtWidgets.QComboBox()
							combobox_type_out.addItems(['iEEG','Scalp'])
							combobox_type_out.setCurrentText(self.file_info[isub][isession]['RecordingType'])
							layout3 = QtWidgets.QHBoxLayout()
							layout3.setContentsMargins(4,0,4,0)
							combobox_type_out.setLayout(layout3)
							self.treeViewOutput.setItemWidget(child, 6, combobox_type_out)
							
							combobox_length_out = QtWidgets.QComboBox()
							combobox_length_out.addItems(['Full','Clip','CS'])
							combobox_length_out.setCurrentText(self.file_info[isub][isession]['RecordingLength'])
							layout4 = QtWidgets.QHBoxLayout()
							layout4.setContentsMargins(4,0,4,0)
							combobox_length_out.setLayout(layout4)
							self.treeViewOutput.setItemWidget(child, 7, combobox_length_out)
							
							combobox_retpro_out = QtWidgets.QComboBox()
							combobox_retpro_out.addItems(['Ret','Pro'])
							combobox_retpro_out.setCurrentText(self.file_info[isub][isession]['Retro_Pro'])
							layout5 = QtWidgets.QHBoxLayout()
							layout5.setContentsMargins(4,0,4,0)
							combobox_retpro_out.setLayout(layout5)
							self.treeViewOutput.setItemWidget(child, 8, combobox_retpro_out)
						
						else:
							old_isession = [x[0] for x in values['session_changes'] if isession == x[1]][0]
							
							# Load output scan file
							scans_tsv = pd.read_csv(os.path.join(self.output_path, isub, isub + '_scans.tsv'), sep='\t')
							name_idx = [i for i,z in enumerate(list(scans_tsv['filename'])) if old_isession in z]

							date = scans_tsv.loc[isession, 'acq_time'].split('T')[0]
							time = scans_tsv.loc[isession, 'acq_time'].split('T')[1]
							file_n = scans_tsv.loc[isession, 'filename'].split('.edf')[0] + '.json'
							with open(os.path.join(self.output_path, isub, old_isession, file_n)) as side_file:
								side_file_temp = json.load(side_file)
							display_name = scans_tsv.loc[isession, 'filename'].split('.edf')[0]
						
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
						
						ses_not_done_cnt += 1
						
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
							layout3.setContentsMargins(0,0,0,0)
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
							combobox_retpro_out.setStyleSheet("padding-left: 5px;")
							
							self.treeViewOutput.setItemWidget(child, 8, combobox_retpro_out)
							
			self.sText.setVisible(1)
			
			header_padding = 20
			self.treeViewOutput.setHeaderItem(QtWidgets.QTreeWidgetItem([self.padentry('Name', 120), self.padentry('Session', header_padding), self.padentry("Date", header_padding), 
																self.padentry("Time", 16), self.padentry("Frequency", 14), self.padentry("Duration", 14),
															  self.padentry('Type', header_padding), self.padentry('Task', header_padding), self.padentry('Ret/Pro', header_padding)]))
			
			self.treeViewOutput.header().setDefaultAlignment(QtCore.Qt.AlignHCenter)
			
			header = self.treeViewOutput.header()
			for column in range(header.count()):
				header.setSectionResizeMode(column, self.treeViewOutput.header().ResizeToContents)
				width = header.sectionSize(column)
				header.setSectionResizeMode(column, self.treeViewOutput.header().Interactive)
				header.resizeSection(column, width)
			
			font = QtGui.QFont()
			font.setBold(True)
			self.treeViewOutput.header().setFont(font)
						
		self.updateStatus("Output directory loaded. Ready to convert.")
	
	def checkEditOutput(self, item, column):
		if column == 1:
			self.treeViewOutput.editItem(item, column)
			
	def onConvertButton(self):
		
		if self.output_path is None:
			warningBox("Please choose an output directory!")
			return
		
		if getattr(sys, 'frozen', False):
			# frozen
			source_dir = os.path.dirname(sys.executable)
		else:
			# unfrozen
			source_dir = os.path.dirname(os.path.realpath(__file__))
	
		self.conversionStatus.clear()
		self.updateStatus("Converting files...")
		
		root = self.treeViewOutput.invisibleRootItem()
		parent_count = root.childCount()
		
		for i in range(parent_count):
			sub = root.child(i).text(0)
			child_count = root.child(i).childCount()
			ses_cnt = 0
			
			ses_cnt=0
			for j in range(child_count):
				item = root.child(i).child(j)
				if self.new_sessions[sub]['session_labels'][ses_cnt] != item.text(1):
					self.new_sessions[sub]['session_labels'][ses_cnt] = item.text(1)
					self.new_sessions[sub]['all_sessions'][ses_cnt] = item.text(1)
				ses_cnt+=1
			
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
		self.edf2bidsWorker = edf2bids()

		self.edf2bidsWorker.bids_settings = self.bids_settings
		self.edf2bidsWorker.new_sessions = self.new_sessions
		self.edf2bidsWorker.file_info = self.file_info
		self.edf2bidsWorker.chan_label_file = self.chan_label_file
		self.edf2bidsWorker.input_path = self.input_path
		self.edf2bidsWorker.output_path = self.output_path
		self.edf2bidsWorker.script_path = source_dir
		self.edf2bidsWorker.coordinates = None
		self.edf2bidsWorker.electrode_imp = None
		self.edf2bidsWorker.make_dir = True
		self.edf2bidsWorker.overwrite = True
		self.edf2bidsWorker.verbose = False
		self.edf2bidsWorker.deidentify_source = self.deidentifyInputDir.isChecked()
		self.edf2bidsWorker.offset_date = self.offsetDate.isChecked()
		self.edf2bidsWorker.dry_run = self.dryRun.isChecked()
		
		# Set Qthread signals
		self.edf2bidsWorker.signals.progressEvent.connect(self.conversionStatusUpdate)
		self.edf2bidsWorker.signals.finished.connect(self.doneConversion)
		self.edf2bidsWorker.signals.errorEvent.connect(self.errorConversion)
		
		# Execute
		self.threadpool.start(self.edf2bidsWorker) 
		
		# Set button states
		self.cancelButton.setEnabled(True)
		self.cancelButton.setStyleSheet(self.cancel_button_color)
		self.cancelButton.clicked.connect(lambda: self.onCancelButton('edf2bids'))
		
		self.pauseButton.setEnabled(True)
		self.pauseButton.setStyleSheet(self.pause_button_color)
		self.pauseButton.pressed.connect(self.edf2bidsWorker.pause)
		self.pauseButton.pressed.connect(lambda: self.onPauseButton('edf2bids'))
		
		self.convertButton.setEnabled(False)
		self.convertButton.setStyleSheet(self.inactive_color)
		self.imagingButton.setEnabled(False)
		self.imagingButton.setStyleSheet(self.inactive_color)
	
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
	
	def onPauseButton(self, worker_name):
		paused=False
		if worker_name in ('edf2bids'):
			if self.edf2bidsWorker.is_paused:
				paused=True
		if worker_name in ('spred2bids'):
			if self.spred2bidsWorker.is_paused:
				paused=True
		if worker_name in ('dicom2bids'):
			if self.dicom2bidsWorker.is_paused:
				paused=True
				
		if paused:
			self.pauseButton.setText('Resume...')
			self.updateStatus("Conversion paused... ")
			#self.conversionStatus.appendPlainText('\nData conversion paused...\n')
			self.cancelButton.setEnabled(False)
			self.cancelButton.setStyleSheet(self.inactive_color)
		else:
			self.pauseButton.setText('Pause')
			self.updateStatus("Conversion resumed...")
			#self.conversionStatus.appendPlainText('\nResuming data conversion...\n')
			self.cancelButton.setEnabled(True)
			self.cancelButton.setStyleSheet(self.cancel_button_color)
		
	def onCancelButton(self, worker_name):
		if worker_name in ('edf2bids'):
			self.edf2bidsWorker.kill()
		if worker_name in ('spred2bids'):
			self.spred2bidsWorker.kill()
		if worker_name in ('dicom2bids'):
			self.dicom2bidsWorker.kill()
		
		self.updateStatus("Conversion cancel requested... ")
		self.conversionStatus.appendPlainText('\nCancelling data conversion... please wait for process to finish\n')
		self.userAborted = True
		self.cancelButton.setEnabled(False)
		self.cancelButton.setStyleSheet(self.inactive_color)
		self.pauseButton.setEnabled(False)
		self.pauseButton.setStyleSheet(self.inactive_color)
		
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
			self.conversionStatus.appendPlainText('File coversion incomplete: Please delete output directory contents and close program.')
			self.updateStatus("Conversion aborted.")
			self.treeViewOutput.clear()
			self.treeViewLoad.clear()
			
			self.spredButton.setEnabled(False)
			self.spredButton.setStyleSheet(self.inactive_color)
			
			self.imagingButton.setEnabled(False)
			self.imagingButton.setStyleSheet(self.inactive_color)
		
		else:
			self.conversionStatus.appendPlainText('\nCompleted conversion at {}'.format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
			self.conversionStatus.appendPlainText('Your data has been BIDsified!\n')
			self.updateStatus("BIDs conversion complete.")
			
			self.spredButton.setEnabled(True)
			self.spredButton.setStyleSheet(self.spred_button_color)
			
			if self.imagingDataPresent and not self.imagingConversionDone:
				self.imagingButton.setEnabled(True)
				self.imagingButton.setStyleSheet(self.convert_button_color)
		
		self.cancelButton.setEnabled(False)
		self.cancelButton.setStyleSheet(self.inactive_color)
		self.convertButton.setEnabled(False)
		self.convertButton.setStyleSheet(self.inactive_color)
		self.pauseButton.setEnabled(False)
		self.pauseButton.setStyleSheet(self.inactive_color)
		
		
	def errorConversion(self, errorInfo):
		self.conversionStatus.appendPlainText('\n')
		self.conversionStatus.appendPlainText('Error occured: {}'.format(errorInfo[1]))
		self.conversionStatus.appendPlainText('{}'.format(errorInfo[2]))
		
		self.updateStatus("Error occured...")
		
		self.treeViewOutput.clear()
		self.treeViewLoad.clear()
			
		self.spredButton.setEnabled(False)
		self.spredButton.setStyleSheet(self.inactive_color)
		self.cancelButton.setEnabled(False)
		self.cancelButton.setStyleSheet(self.inactive_color)
		self.pauseButton.setEnabled(False)
		self.pauseButton.setStyleSheet(self.inactive_color)
		self.convertButton.setEnabled(False)
		self.convertButton.setStyleSheet(self.inactive_color)
		self.imagingButton.setEnabled(False)
		self.imagingButton.setStyleSheet(self.inactive_color)
		
	def onSpredButton(self):
		self.updateStatus('Converting to SPReD format...')
		QtGui.QGuiApplication.processEvents()
		
		# Set Qthread
		self.spred2bidsWorker = bids2spred()
		self.spred2bidsWorker.output_path = self.output_path
		
		# Set Qthread signals
		self.spred2bidsWorker.signals.progressEvent.connect(self.conversionStatusUpdate)
		self.spred2bidsWorker.signals.finished.connect(self.doneSPReDConversion)
		
		# Execute
		self.threadpool.start(self.spred2bidsWorker)
		
		# Set button states
		self.cancelButton.setEnabled(True)
		self.cancelButton.setStyleSheet(self.cancel_button_color)
		self.cancelButton.clicked.connect(lambda: self.onCancelButton('spred2bids'))
		
		self.pauseButton.setEnabled(True)
		self.pauseButton.setStyleSheet(self.pause_button_color)
		self.pauseButton.pressed.connect(self.spred2bidsWorker.pause)
		self.pauseButton.pressed.connect(lambda: self.onPauseButton('spred2bids'))
		
		self.spredButton.setEnabled(False)
		self.spredButton.setStyleSheet(self.inactive_color)
		self.imagingButton.setEnabled(False)
		self.imagingButton.setStyleSheet(self.inactive_color)
		
	def doneSPReDConversion(self):
		if self.userAborted:
			self.conversionStatus.appendPlainText('\nAborted SPReD conversion at {}'.format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
			self.conversionStatus.appendPlainText('SPReD coversion incomplete: Please delete output directory contents and close program.')
			self.updateStatus("SPReD conversion aborted.")
			self.treeViewOutput.clear()
			self.treeViewLoad.clear()
		else:
			self.conversionStatus.appendPlainText('Completed SPReD conversion at {}'.format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
			self.conversionStatus.appendPlainText('Your data has been SPReDified!\n')
			self.updateStatus("SPReD conversion complete.")
		
		self.eegConversionDone=True
		self.spredButton.setEnabled(False)
		self.spredButton.setStyleSheet(self.inactive_color)
		self.cancelButton.setEnabled(False)
		self.cancelButton.setStyleSheet(self.inactive_color)
		self.pauseButton.setEnabled(False)
		self.pauseButton.setStyleSheet(self.inactive_color)
		self.convertButton.setEnabled(False)
		self.convertButton.setStyleSheet(self.inactive_color)
		
		if self.imagingDataPresent and not self.imagingConversionDone:
			self.imagingButton.setEnabled(True)
			self.imagingButton.setStyleSheet(self.convert_button_color)
	
	def onImagingButton(self):
		self.updateStatus('De-identifying imaging data...')
		QtGui.QGuiApplication.processEvents()
			
		# Set Qthread
		self.dicom2bidsWorker = dicom2bids()
		self.dicom2bidsWorker.input_path = self.input_path
		self.dicom2bidsWorker.output_path = self.output_path
		self.dicom2bidsWorker.imaging_data = self.imaging_data
		
		# Set Qthread signals
		self.dicom2bidsWorker.signals.progressEvent.connect(self.conversionStatusUpdate)
		self.dicom2bidsWorker.signals.finished.connect(self.doneImagingConversion)
		
		# Execute
		self.threadpool.start(self.dicom2bidsWorker)
		
		# Set button states
		self.cancelButton.setEnabled(True)
		self.cancelButton.setStyleSheet(self.cancel_button_color)
		self.cancelButton.clicked.connect(lambda: self.onCancelButton('dicom2bids'))
		
		self.pauseButton.setEnabled(True)
		self.pauseButton.setStyleSheet(self.pause_button_color)
		self.pauseButton.pressed.connect(self.dicom2bidsWorker.pause)
		self.pauseButton.pressed.connect(lambda: self.onPauseButton('dicom2bids'))
		
		self.imagingButton.setEnabled(False)
		self.imagingButton.setStyleSheet(self.inactive_color)
		
		if self.convertButton.isEnabled():
			self.convertButton.setEnabled(False)
			self.convertButton.setStyleSheet(self.inactive_color)
	
	def doneImagingConversion(self):
		if self.userAborted:
			self.conversionStatus.appendPlainText('\nAborted image de-identification at {}'.format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
			self.conversionStatus.appendPlainText('Image de-identification incomplete: Please delete output directory contents and close program.')
			self.updateStatus("Image de-identification aborted.")
			self.treeViewOutput.clear()
			self.treeViewLoad.clear()
		else:
			self.conversionStatus.appendPlainText('\nCompleted image de-identification at {}'.format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
			self.updateStatus("Image de-identification complete.")
		
		self.imagingConversionDone=True
		self.imagingButton.setEnabled(False)
		self.imagingButton.setStyleSheet(self.inactive_color)
		self.cancelButton.setEnabled(False)
		self.cancelButton.setStyleSheet(self.inactive_color)
		self.pauseButton.setEnabled(False)
		self.pauseButton.setStyleSheet(self.inactive_color)
		
		if not self.eegConversionDone and not all(len(value) == 0 for value in self.file_info.values()):
			self.convertButton.setEnabled(True)
			self.convertButton.setStyleSheet(self.convert_button_color)
		else:
			self.convertButton.setEnabled(False)
			self.convertButton.setStyleSheet(self.inactive_color)
		
def main():
	app = QtWidgets.QApplication(sys.argv)
	window = MainWindow()
	window.show()
	app.exec_()
	
if __name__ == '__main__':	
	main()