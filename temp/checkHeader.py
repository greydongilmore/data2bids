#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import io
import os
import string
import array
from datetime import datetime
from collections import namedtuple

class EDFexception(Exception):
	def __init__(self, message):
		self.message = message
		super().__init__(self.message)

class EDFfileCheck:
	EDFLIB_TIME_DIMENSION     = 10000000
	EDFLIB_MAXSIGNALS               = 640
	EDFLIB_MAX_ANNOTATION_LEN       = 512

	EDFSEEK_SET = 0
	EDFSEEK_CUR = 1
	EDFSEEK_END = 2

	EDFLIB_FILETYPE_EDF                 = 0
	EDFLIB_FILETYPE_EDFPLUS             = 1
	EDFLIB_FILETYPE_BDF                 = 2
	EDFLIB_FILETYPE_BDFPLUS             = 3
	
	
	
	EDFLIB_MALLOC_ERROR                = -1
	EDFLIB_NO_SUCH_FILE_OR_DIRECTORY   = -2
	EDFLIB_FILE_CONTAINS_FORMAT_ERRORS = -3

	EDFLIB_MAXFILES_REACHED            = -4
	EDFLIB_FILE_READ_ERROR             = -5
	EDFLIB_FILE_ALREADY_OPENED         = -6
	EDFLIB_FILETYPE_ERROR              = -7
	EDFLIB_FILE_WRITE_ERROR            = -8
	EDFLIB_NUMBER_OF_SIGNALS_INVALID   = -9
	EDFLIB_FILE_IS_DISCONTINUOUS      = -10
	EDFLIB_INVALID_READ_ANNOTS_VALUE  = -11
	EDFLIB_INVALID_ARGUMENT           = -12
	EDFLIB_FILE_CLOSED                = -13

	EDFLIB_DO_NOT_READ_ANNOTATIONS = 0
	EDFLIB_READ_ANNOTATIONS        = 1
	EDFLIB_READ_ALL_ANNOTATIONS    = 2

	EDFLIB_NO_SIGNALS                 = -20
	EDFLIB_TOO_MANY_SIGNALS           = -21
	EDFLIB_NO_SAMPLES_IN_RECORD       = -22
	EDFLIB_DIGMIN_IS_DIGMAX           = -23
	EDFLIB_DIGMAX_LOWER_THAN_DIGMIN   = -24
	EDFLIB_PHYSMIN_IS_PHYSMAX         = -25
	EDFLIB_DATARECORD_SIZE_TOO_BIG    = -26

	EDFLIB_VERSION = 100
	
	EDFAnnotationStruct = namedtuple("annotation", ["onset", "duration", "description"])
	
	def __init__(self, path: str):
		self.__path = path
		self.__status_ok = 0
		self.__edf = 0
		self.__bdf = 0
		self.__edfplus = 0
		self.__bdfplus = 0
		self.__discontinuous = 0
		self.__patient = ""
		self.__recording = ""
		self.__plus_patientcode = ""
		self.__plus_gender = ""
		self.__plus_birthdate = ""
		self.__plus_patient_name = ""
		self.__plus_patient_additional = ""
		self.__plus_startdate = ""
		self.__plus_admincode = ""
		self.__plus_technician = ""
		self.__plus_equipment = ""
		self.__plus_recording_additional = ""
		self.__reserved = ""
		self.__starttime_offset = 0
		self.annotationslist = []
		
		self.error_types={
			-1:'EDFLIB_MALLOC_ERROR',
			-2:'EDFLIB_NO_SUCH_FILE_OR_DIRECTORY',
			-3:'EDFLIB_FILE_CONTAINS_FORMAT_ERRORS',
			-4:'EDFLIB_MAXFILES_REACHED',
			-5:'EDFLIB_FILE_READ_ERROR',
			-6:'EDFLIB_FILE_ALREADY_OPENED',
			-7:'EDFLIB_FILETYPE_ERROR',
			-8:'EDFLIB_FILE_WRITE_ERROR',
			-9:'EDFLIB_NUMBER_OF_SIGNALS_INVALID',
			-10:'EDFLIB_FILE_IS_DISCONTINUOUS',
			-11:'EDFLIB_INVALID_READ_ANNOTS_VALUE',
			-12:'EDFLIB_INVALID_ARGUMENT',
			-13:'EDFLIB_FILE_CLOSED',
			-20:'EDFLIB_NO_SIGNALS',
			-21:'EDFLIB_TOO_MANY_SIGNALS',
			-22:'EDFLIB_NO_SAMPLES_IN_RECORD',
			-23:'EDFLIB_DIGMIN_IS_DIGMAX',
			-24:'EDFLIB_DIGMAX_LOWER_THAN_DIGMIN',
			-25:'EDFLIB_PHYSMIN_IS_PHYSMAX',
			-26:'EDFLIB_DATARECORD_SIZE_TOO_BIG'
			}
		
		try:
			self.__file_in = open(path, "rb")
		except OSError as e:
			raise EDFexception("Can not open file for reading: %s" %(e.strerror))
	
	def checkEDFheader(self):
		self.__err = self._checkHeader()
		if self.__err:
			self.__file_in.close()
			raise EDFexception(f"File is not valid EDF(+) or BDF(+). {self.error_types[self.__err]}")
	
	def checkAnnotations(self):
		self.__annotlist_sz = 0
		self.__annots_in_file = 0
		self.__err = self.__get_annotations()
		if self.__err != 0:
			self.__file_in.close()
			raise EDFexception("File is not valid EDF+ or BDF+.")


	def _checkHeader(self):
	
		str4 = bytearray(4)
		str8 = bytearray(8)
		str16 = bytearray(16)
		str80 = bytearray(80)
		str128 = bytearray(128)
	
		######### Check the base header (first 256 bytes) ##############################
		self.__file_in.seek(0, io.SEEK_END)
		if self.__file_in.tell() < 512: # There must be at least one signal thus the header must have at least 512 bytes
			return -1
		hdr = bytearray(256)
		self.__file_in.seek(0, io.SEEK_SET)
		self.__file_in.readinto(hdr)
	
		######### Check for non-printable ASCII characters #############################
		for i in range(1, 256):
			if hdr[i] < 32 or hdr[i] > 126:
				return -2
	
		############################# VERSION ##########################################
		if hdr[0] == 48:
			for i in range(1, 8):
				if hdr[i] != 32:
					return -3
	
			self.__edf = 1
		else:
			if hdr[0] == 255 and \
				 hdr[1] == ord('B') and \
				 hdr[2] == ord('I') and \
				 hdr[3] == ord('O') and \
				 hdr[4] == ord('S') and \
				 hdr[5] == ord('E') and \
				 hdr[6] == ord('M') and \
				 hdr[7] == ord('I'):
				 self.__bdf = 1
			else:
				return -4
	
	###################### PATIENTNAME #############################################
		self.__patient = hdr[8:88]
	
	####################### RECORDING ##############################################
		self.__recording = hdr[88:168]
	
	####################### STARTDATE ##############################################
		if hdr[170] != 46 or hdr[173] != 46 or \
		 hdr[168] < 48 or hdr[168] > 57 or \
		 hdr[169] < 48 or hdr[169] > 57 or \
		 hdr[171] < 48 or hdr[171] > 57 or \
		 hdr[172] < 48 or hdr[172] > 57 or \
		 hdr[174] < 48 or hdr[174] > 57 or \
		 hdr[175] < 48 or hdr[175] > 57:
			return -5
	
		str8 = hdr[168:176]
		str8[2] = 0
		str8[5] = 0
	
		self.__startdate_day = self.__atoi_nonlocalized(str8, 0)
		self.__startdate_month = self.__atoi_nonlocalized(str8, 3)
		self.__startdate_year = self.__atoi_nonlocalized(str8, 6)
	
		if self.__startdate_day < 1 or self.__startdate_day > 31:
			return -5
	
		if self.__startdate_month < 1 or self.__startdate_month > 12:
			return -6
	
		if self.__startdate_year > 84:
			self.__startdate_year += 1900
		else:
			self.__startdate_year += 2000
	
		####################### STARTTIME ##############################################
		if hdr[178] != 46 or hdr[181] != 46 or \
		 hdr[176] < 48 or hdr[176] > 57 or \
		 hdr[177] < 48 or hdr[177] > 57 or \
		 hdr[179] < 48 or hdr[179] > 57 or \
		 hdr[180] < 48 or hdr[180] > 57 or \
		 hdr[182] < 48 or hdr[182] > 57 or \
		 hdr[183] < 48 or hdr[183] > 57:
			return -5
		
		str8 = hdr[176:184]
		str8[2] = 0
		str8[5] = 0
	
		self.__starttime_hour = self.__atoi_nonlocalized(str8, 0)
		self.__starttime_minute = self.__atoi_nonlocalized(str8, 3)
		self.__starttime_second = self.__atoi_nonlocalized(str8, 6)
	
		if self.__starttime_hour > 23 or self.__starttime_minute > 59 or self.__starttime_second > 59:
			return -7
	
		self.__l_starttime = 3600 * self.__starttime_hour
		self.__l_starttime += 60 * self.__starttime_minute
		self.__l_starttime += self.__starttime_second
		self.__l_starttime *= self.EDFLIB_TIME_DIMENSION
		
		################## NUMBER OF SIGNALS IN HEADER #################################
		str4 = hdr[252:256]
	
		if self.__is_integer_number(str4):
			return -8
	
		self.__edfsignals = self.__atoi_nonlocalized(str4, 0)
	
		if self.__edfsignals < 1 or self.__edfsignals > 640:
			return -9
	
	################### NUMBER OF BYTES IN HEADER ##################################
	
		str8 = hdr[184:192]
	
		if self.__is_integer_number(str8):
			return -10
	
		self.__hdrsize = self.__atoi_nonlocalized(str8, 0)
	
		if self.__hdrsize != ((self.__edfsignals + 1) * 256):
			return -11
	
	######################## RESERVED FIELD ########################################
	
		self.__reserved = hdr[192:236].decode("ascii")
	
		if self.__edf:
			self.__filetype = self.EDFLIB_FILETYPE_EDF
			if self.__reserved[:5] == "EDF+C":
				self.__edfplus = 1
				self.__filetype = self.EDFLIB_FILETYPE_EDFPLUS
			if self.__reserved[:5] == "EDF+D":
				self.__edfplus = 1
				self.__discontinuous = 1
				self.__filetype = self.EDFLIB_FILETYPE_EDFPLUS
		if self.__bdf:
			self.__filetype = self.EDFLIB_FILETYPE_BDF
			if self.__reserved[:5] == "BDF+C":
				self.__bdfplus = 1
				self.__filetype = self.EDFLIB_FILETYPE_BDFPLUS
			if self.__reserved[:5] == "BDF+D":
				self.__bdfplus = 1
				self.__discontinuous = 1
				self.__filetype = self.EDFLIB_FILETYPE_BDFPLUS
	
	##################### NUMBER OF DATARECORDS ####################################
	
		str8 = hdr[236:244]
	
		if self.__is_integer_number(str8):
			return -12
	
		self.__datarecords = self.__atoi_nonlocalized(str8, 0)
	
		if self.__datarecords < 1:
			return -13
	
	###################### DATARECORD DURATION #####################################
	
		str8 = hdr[244:252]
		if self.__is_number(str8):
			return -14
		
		self.__data_record_duration = self.__atof_nonlocalized(str8)
	
		if self.__data_record_duration < -0.000001:
			return -15
	
		self.__long_data_record_duration = self.__get_long_duration_hdr(str8)
	
	################ START WITH THE SIGNALS IN THE HEADER ##########################
	
		hdr = bytearray(self.__hdrsize)
		self.__file_in.seek(0, io.SEEK_SET)
		self.__file_in.readinto(hdr)
	
	######### Check for non-printable ASCII characters #############################
		for i in range(1, self.__hdrsize):
			if hdr[i] < 32 or hdr[i] > 126:
				return -16
	
	####################### LABELS #################################################
	
		self.__param_label = [str] * self.__edfsignals
	
		self.__param_annotation = array.array('i')
		self.__annot_ch = array.array('i')
		for i in range(0, self.__edfsignals):
			self.__param_annotation.append(0)
			self.__annot_ch.append(0)
		
		self.__nr_annot_chns = 0
		for i in range(0, self.__edfsignals):
			self.__param_label[i] = hdr[256 + (i * 16) : 256 + (i * 16) + 16].decode("ascii")
	
			if self.__edfplus != 0:
				if self.__param_label[i] == "EDF Annotations ":
					self.__annot_ch[self.__nr_annot_chns] = i
					self.__nr_annot_chns += 1
					self.__param_annotation[i] = 1
		
			if self.__bdfplus != 0:
				if self.__param_label[i] == "BDF Annotations ":
					self.__annot_ch[self.__nr_annot_chns] = i
					self.__nr_annot_chns += 1
					self.__param_annotation[i] = 1
	
		if(self.__edfplus != 0 or self.__bdfplus != 0) and self.__nr_annot_chns == 0:
			return -17
	
		if self.__edfsignals != self.__nr_annot_chns or (self.__edfplus == 0 and self.__bdfplus == 0):
			if self.__data_record_duration < 0.0000001:
				return -18
	
	##################### TRANSDUCER TYPES #########################################
	
		self.__param_transducer = [str] * self.__edfsignals
		for i in range(0, self.__edfsignals):
			self.__param_transducer[i] = hdr[256 + (self.__edfsignals * 16) + (i * 80) : 256 + (self.__edfsignals * 16) + (i * 80) + 80].decode("ascii")
			if self.__edfplus != 0 or self.__bdfplus != 0:
				if self.__param_annotation[i] != 0:
					if self.__param_transducer[i] != "                                                                                ":
						return -19
	
	##################### PHYSICAL DIMENSIONS ######################################
	
		self.__param_physdimension = [str] * self.__edfsignals
		for i in range(0, self.__edfsignals):
			self.__param_physdimension[i] = hdr[256 + (self.__edfsignals * 96) + (i * 8) : 256 + (self.__edfsignals * 96) + (i * 8) + 8].decode("ascii")
	
	##################### PHYSICAL MINIMUMS ########################################
	
		self.__param_phys_min = array.array('d')
		for i in range(0, self.__edfsignals):
			str8 = hdr[256 + (self.__edfsignals * 104) + (i * 8) : 256 + (self.__edfsignals * 104) + (i * 8) + 8]
			if self.__is_number(str8):
				return -20
			self.__param_phys_min.append(self.__atof_nonlocalized(str8))
	
	##################### PHYSICAL MAXIMUMS ########################################
	
		self.__param_phys_max = array.array('d')
		for i in range(0, self.__edfsignals):
			str8 = hdr[256 + (self.__edfsignals * 112) + (i * 8) : 256 + (self.__edfsignals * 112) + (i * 8) + 8]
			if self.__is_number(str8):
				return -21
			self.__param_phys_max.append(self.__atof_nonlocalized(str8))
			if self.__param_phys_max[i] == self.__param_phys_min[i]:
				return -22
	
	##################### DIGITAL MINIMUMS #########################################
	
		self.__param_dig_min = array.array('i')
		for i in range(0, self.__edfsignals):
			str8 = hdr[256 + (self.__edfsignals * 120) + (i * 8) : 256 + (self.__edfsignals * 120) + (i * 8) + 8]
			if self.__is_integer_number(str8):
				return -23
			self.__param_dig_min.append(self.__atoi_nonlocalized(str8, 0))
		
			if self.__edfplus != 0:
				if self.__param_annotation[i] != 0:
					if self.__param_dig_min[i] != -32768:
						return -24
		
			if self.__bdfplus != 0:
				if self.__param_annotation[i] != 0:
					if self.__param_dig_min[i] != -8388608:
						return -25
		
			if self.__edf != 0:
				if self.__param_dig_min[i] > 32767 or self.__param_dig_min[i] < -32768:
					return -26
		
			if self.__bdf != 0:
				if self.__param_dig_min[i] > 8388607 or self.__param_dig_min[i] < -8388608:
					return -27
	
	##################### DIGITAL MAXIMUMS #########################################
	
		self.__param_dig_max = array.array('i')
		for i in range(0, self.__edfsignals):
			str8 = hdr[256 + (self.__edfsignals * 128) + (i * 8) : 256 + (self.__edfsignals * 128) + (i * 8) + 8]
			if self.__is_integer_number(str8):
				return -24
			self.__param_dig_max.append(self.__atoi_nonlocalized(str8, 0))
		
			if self.__edfplus != 0:
				if self.__param_annotation[i] != 0:
					if self.__param_dig_max[i] != 32767:
						return -24
		
			if self.__bdfplus != 0:
				if self.__param_annotation[i] != 0:
					if self.__param_dig_max[i] != 8388607:
						return -25
		
			if self.__edf != 0:
				if self.__param_dig_max[i] > 32767 or self.__param_dig_max[i] < -32768:
					return -26
		
			if self.__bdf != 0:
				if self.__param_dig_max[i] > 8388607 or self.__param_dig_max[i] < -8388608:
					return -27
		
			if self.__param_dig_min[i] >= self.__param_dig_max[i]:
				return -28
	
	##################### PREFILTER FIELDS #########################################
	
		self.__param_prefilter = [str] * self.__edfsignals
		for i in range(0, self.__edfsignals):
			self.__param_physdimension[i] = hdr[256 + (self.__edfsignals * 96) + (i * 8) : 256 + (self.__edfsignals * 96) + (i * 8) + 8].decode("ascii")
	
	
		self.__param_prefilter = [str] * self.__edfsignals
		for i in range(0, self.__edfsignals):
			self.__param_prefilter[i] = hdr[256 + (self.__edfsignals * 136) + (i * 80) : 256 + (self.__edfsignals * 136) + (i * 80) + 80].decode("ascii")
			if self.__edfplus != 0 or self.__bdfplus != 0:
				if self.__param_annotation[i] != 0:
					if self.__param_prefilter[i] != "                                                                                ":
						return -29
	
	################# NR OF SAMPLES IN EACH DATARECORD #############################
	
		self.__recordsize = 0
		self.__param_smp_per_record = array.array('i')
		for i in range(0, self.__edfsignals):
			str8 = hdr[256 + (self.__edfsignals * 216) + (i * 8) : 256 + (self.__edfsignals * 216) + (i * 8) + 8]
			if self.__is_integer_number(str8):
				return -30
			self.__param_smp_per_record.append(self.__atoi_nonlocalized(str8, 0))
			if self.__param_smp_per_record[i] < 1:
				return -31
			self.__recordsize += self.__param_smp_per_record[i]
		if self.__bdf != 0:
			self.__recordsize *= 3
			if self.__recordsize > (15 * 1024 * 1024):
				return -32
		else:
			self.__recordsize *= 2
			if self.__recordsize > (10 * 1024 * 1024):
				return -33
	
	##################### RESERVED FIELDS ##########################################
	
		self.__param_reserved = [str] * self.__edfsignals
		for i in range(0, self.__edfsignals):
			self.__param_reserved[i] = hdr[256 + (self.__edfsignals * 224) + (i * 32) : 256 + (self.__edfsignals * 224) + (i * 32) + 32].decode("ascii")
	
	##################### EDF+ PATIENTNAME #########################################
	
		if self.__edfplus != 0 or self.__bdfplus != 0:
			error = 0
			dotposition = 0
			str80 = hdr[8 : 88]
			for i in range(0, 80):
				if str80[i] == 32:
					dotposition = i
					break
			dotposition += 1
			if dotposition > 73 or dotposition < 2:
				error = 1
			if str80[dotposition + 2] != ord('X'):
				if dotposition > 65:
					error = 1
			if str80[dotposition] != ord('M') and str80[dotposition] != ord('F') and str80[dotposition] != ord('X'):
				error = 1
			dotposition += 1
			if str80[dotposition] != 32:
				error = 1
			if str80[dotposition + 1] == ord('X'):
				if str80[dotposition + 2] != 32:
					error = 1
				if str80[dotposition + 3] == 32:
					error = 1
			else:
				if str80[dotposition + 12] != 32:
					error = 1
				if str80[dotposition + 13] == 32:
					error = 1
				dotposition += 1
				str16 = str80[dotposition : dotposition + 11]
				if str16[2] != 45 or str16[6] != 45:
					error = 1
				str16[2] = 0
				str16[6] = 0
				if str16[0] < 48 or str16[0] > 57:
					error = 1
				if str16[1] < 48 or str16[1] >57:
					error = 1
				if str16[7] < 48 or str16[7] >57:
					error = 1
				if str16[8] < 48 or str16[8] >57:
					error = 1
				if str16[9] < 48 or str16[9] >57:
					error = 1
				if str16[10] < 48 or str16[10] > 57:
					error = 1
				if self.__atof_nonlocalized(str16) < 1 or self.__atof_nonlocalized(str16) > 31:
					error = 1
				if str16[3] != ord('J') and str16[4] != ord('A') and str16[5] != ord('N'):
					if str16[3] != ord('F') and str16[4] != ord('E') and str16[5] != ord('B'):
						if str16[3] != ord('M') and str16[4] != ord('A') and str16[5] != ord('R'):
							if str16[3] != ord('A') and str16[4] != ord('P') and str16[5] != ord('R'):
								if str16[3] != ord('M') and str16[4] != ord('A') and str16[5] != ord('Y'):
									if str16[3] != ord('J') and str16[4] != ord('U') and str16[5] != ord('N'):
										if str16[3] != ord('J') and str16[4] != ord('U') and str16[5] != ord('L'):
											if str16[3] != ord('A') and str16[4] != ord('U') and str16[5] != ord('G'):
												if str16[3] != ord('S') and str16[4] != ord('E') and str16[5] != ord('P'):
													if str16[3] != ord('O') and str16[4] != ord('C') and str16[5] != ord('T'):
														if str16[3] != ord('N') and str16[4] != ord('O') and str16[5] != ord('V'):
															if str16[3] != ord('D') and str16[4] != ord('E') and str16[5] != ord('C'):
																error = 1
			if error != 0:
				return -35
		
			p = 0
			if str80[p] == ord('X'):
				self.__plus_patientcode = ""
				p += 2
			else:
				for i in range(0, 80 - p):
					if str80[i + p] == 32:
						break
					str128[i] = str80[i + p]
					if str128[i] == ord('_'):
						str128[i] = 32
				self.__plus_patientcode = str128[0 : i].decode("ascii")
				p += (i + 1)
		
			if str80[p] == ord('M'):
				self.__plus_gender = "Male"
			else:
				if str80[p] == ord('F'):
					self.__plus_gender = "Female"
				else:
					self.__plus_gender = ""
			p += 2
		
			if str80[p] == ord('X'):
				self.__plus_birthdate = ""
				p += 2
			else:
				for i in range(0, 80 - p):
					if str80[i + p] == 32:
						break
					str128[i] = str80[i + p]
				str128[2] = 32
				str128[3] += 32
				str128[4] += 32
				str128[5] += 32
				str128[6] = 32
				p += (i + 1)
				self.__plus_birthdate = str128[0 : 11].decode("ascii")
		
			for i in range(0, 80 - p):
				if str80[i + p] == 32:
					break
				str128[i] = str80[i + p]
				if str128[i] == ord('_'):
					str128[i] = 32
			p += (i + 1)
			self.__plus_patient_name = str128[0 : i].decode("ascii")
		
			for i in range(0, 80 - p):
				str128[i] = str80[i + p]
			p += (i + 1)
			self.__plus_patient_additional = str128[0 : i].decode("ascii")
	
	##################### EDF+ RECORDINGFIELD ######################################
	
		if self.__edfplus != 0 or self.__bdfplus != 0:
			error = 0
			p = 0
			r = 0
			str80 = hdr[88 : 168]
			if str80[0 : 10].decode("ascii") != "Startdate ":
				return -36
		
			if str80[10] == ord('X'):
				if str80[11] != 32:
					error = 1
				if str80[12] == 32:
					error = 1
				p = 12
			else:
				if str80[21] != 32:
					error = 1
				if str80[22] == 32:
					error = 1
				p = 22
				str16 = str80[10 : 10 + 11]
				if str16[2] != 45 or str16[6] != 45:
					error = 1
				str16[2] = 0
				str16[6] = 0
				if str16[0] < 48 or str16[0] > 57:
					error = 1
				if str16[1] < 48 or str16[1] >57:
					error = 1
				if str16[7] < 48 or str16[7] >57:
					error = 1
				if str16[8] < 48 or str16[8] >57:
					error = 1
				if str16[9] < 48 or str16[9] >57:
					error = 1
				if str16[10] < 48 or str16[10] > 57:
					error = 1
				if self.__atof_nonlocalized(str16) < 1 or self.__atof_nonlocalized(str16) > 31:
					error = 1
				r = 0
				if str16[3] == ord('J') and str16[4] == ord('A') and str16[5] == ord('N'):
					r = 1
				else:
					if str16[3] == ord('F') and str16[4] == ord('E') and str16[5] == ord('B'):
						r = 2
					else:
						if str16[3] == ord('M') and str16[4] == ord('A') and str16[5] == ord('R'):
							r = 3
						else:
							if str16[3] == ord('A') and str16[4] == ord('P') and str16[5] == ord('R'):
								r = 4
							else:
								if str16[3] == ord('M') and str16[4] == ord('A') and str16[5] == ord('Y'):
									r = 5
								else:
									if str16[3] == ord('J') and str16[4] == ord('U') and str16[5] == ord('N'):
										r = 6
									else:
										if str16[3] == ord('J') and str16[4] == ord('U') and str16[5] == ord('L'):
											r = 7
										else:
											if str16[3] == ord('A') and str16[4] == ord('U') and str16[5] == ord('G'):
												r = 8
											else:
												if str16[3] == ord('S') and str16[4] == ord('E') and str16[5] == ord('P'):
													r = 9
												else:
													if str16[3] == ord('O') and str16[4] == ord('C') and str16[5] == ord('T'):
														r = 10
													else:
														if str16[3] == ord('N') and str16[4] == ord('O') and str16[5] == ord('V'):
															r = 11
														else:
															if str16[3] == ord('D') and str16[4] == ord('E') and str16[5] == ord('C'):
																r = 12
															else:
																error = 1
			if error != 0:
				return -37
		
			n = 0
			for i in range(p, 80):
				if i > 78:
					error = 1
					break
				if str80[i] == 32:
					n += 1
					if str80[i + 1] == 32:
						error = 1
						break
				if n > 1:
					break
		
			if error != 0:
				return -38
		
			if hdr[98] != ord('X'):
				for j in range(0, 8):
					str8[j] = hdr[168 + j]
				str8[2] = 0
				str8[5] = 0
				if self.__atoi_nonlocalized(str8, 0) != self.__atoi_nonlocalized(str16, 0):
					error = 1
				if self.__atoi_nonlocalized(str8, 3) != r:
					error = 1
				if self.__atoi_nonlocalized(str8, 6) != self.__atoi_nonlocalized(str16, 9):
					error = 1
				if error != 0:
					return -39
		
				self.__startdate_year = self.__atoi_nonlocalized(str16, 7)
		
				if self.__startdate_year < 1970:
					return -40
		
			p = 10
			for i in range(0, 80 - p):
				if str80[i + p] == 32:
					break
				str128[i] = str80[i + p]
			str128[2] = 32
			str128[3] += 32
			str128[4] += 32
			str128[5] += 32
			str128[6] = 32
			p += (i + 1)
			self.__plus_startdate = str128[0 : i].decode("ascii")
		
			if str80[p] == ord('X'):
				plus_admincode = ""
				p += 2
			else:
				for i in range(0, 80 - p):
					if str80[i + p] == 32:
						break
					str128[i] = str80[i + p]
					if str128[i] == ord('_'):
						str128[i] = 32
				p += (i + 1)
				self.__plus_admincode = str128[0 : i].decode("ascii")
		
			if str80[p] == ord('X'):
				plus_technician = ""
				p += 2
			else:
				for i in range(0, 80 - p):
					if str80[i+p] == 32:
						break
				str128[i] = str80[i + p]
				if str128[i] == ord('_'):
					str128[i] = 32
				p += (i + 1)
				self.__plus_technician = str128[0 : i].decode("ascii")
		
			if str80[p] == ord('X'):
				plus_equipment = ""
				p += 2
			else:
				for i in range(0, 80 - p):
					if str80[i + p] == 32:
						break
					str128[i] = str80[i + p]
					if str128[i] == ord('_'):
						str128[i] = 32
				p += (i + 1)
				self.__plus_equipment = str128[0 : i].decode("ascii")
		
			for i in range(0, 80 - p):
				str128[i] = str80[i + p]
			p += (i + 1)
			self.__plus_recording_additional = str128[0 : i].decode("ascii")
	
	######################### FILESIZE #############################################
	
		self.__file_in.seek(0, os.SEEK_END)
		if self.__file_in.tell() != (self.__recordsize * self.__datarecords) + self.__hdrsize:
			return -41
	
		self.__param_buf_offset = array.array('i')
	
		self.__param_bitvalue = array.array('d')
	
		self.__param_offset = array.array('d')
	
		n = 0
		for i in range(0, self.__edfsignals):
			self.__param_buf_offset.append(n)
			if self.__bdf != 0:
				n += self.__param_smp_per_record[i] * 3
			else:
				n += self.__param_smp_per_record[i] * 2
		
			self.__param_bitvalue.append((self.__param_phys_max[i] - self.__param_phys_min[i]) / (self.__param_dig_max[i] - self.__param_dig_min[i]))
			self.__param_offset.append(self.__param_phys_max[i] / self.__param_bitvalue[i] - self.__param_dig_max[i])
	
		self.__mapped_signals = array.array('i')
		j = 0
		for i in range(0, self.__edfsignals):
			if self.__param_annotation[i] == 0:
				self.__mapped_signals.append(i)
				j += 1
	
		self.__param_sample_pntr = array.array('i')
		for i in range(0, self.__edfsignals):
			self.__param_sample_pntr.append(0)
	
		return 0
	
	def __get_annotations(self):
		i = 0
		j = 0
		k = 0
		p = 0
		r = 0
		n = 0
		max_ = 0
		onset = 0
		duration = 0
		duration_start = 0
		zero = 0
		max_tal_ln = 0
		error = 0
		annots_in_record = 0
		annots_in_tal = 0
		elapsedtime = 0
		time_tmp = 0
		samplesize = 2

		data_record_duration = self.__long_data_record_duration

		if self.__bdfplus != 0:
			samplesize = 3

		cnv_buf = bytearray(self.__recordsize)

		for i in range(0, self.__nr_annot_chns):
			if max_tal_ln < (self.__param_smp_per_record[self.__annot_ch[i]] * samplesize):
				max_tal_ln = self.__param_smp_per_record[self.__annot_ch[i]] * samplesize

		if max_tal_ln < 128:
			max_tal_ln = 128

		scratchpad = bytearray(max_tal_ln + 3)
		time_in_txt = bytearray(max_tal_ln + 3)
		duration_in_txt = bytearray(max_tal_ln + 3)

		self.__file_in.seek((self.__edfsignals + 1) * 256, io.SEEK_SET)

		for i in range(0, self.__datarecords):
			self.__file_in.readinto(cnv_buf)

################ process annotationsignals (if any) ############################

			error = 0

			for r in range(0, self.__nr_annot_chns):
				n = 0
				zero = 0
				onset = 0
				duration = 0
				duration_start = 0
				annots_in_tal = 0
				annots_in_record = 0

				p = self.__param_buf_offset[self.__annot_ch[r]]
				max_ = self.__param_smp_per_record[self.__annot_ch[r]] * samplesize

################ process one annotation signal #################################

				if cnv_buf[p + max_ - 1] != 0:
					return 5

				if r == 0:  # if it's the first annotation signal, then check the timekeeping annotation
					error = 1

					for k in range(0, max_ - 2):
						scratchpad[k] = cnv_buf[p + k]
						if scratchpad[k] == 20:
							if cnv_buf[p + k + 1] != 20:
								return 6
							scratchpad[k] = 0
							if self.__is_onset_number(scratchpad) != 0:
								return 36
							else:
								time_tmp = self.__get_long_time(scratchpad)

								if i != 0:
									if self.__discontinuous != 0:
										if (time_tmp - elapsedtime) < data_record_duration:
											return 4
									else:
										if (time_tmp - elapsedtime) != data_record_duration:
											return 3
								else:
									if (time_tmp >= self.EDFLIB_TIME_DIMENSION) or (time_tmp < 0):
										return 2
									else:
										self.__starttime_offset = int(time_tmp)
										self.__filestart_dt = datetime(self.__startdate_year, self.__startdate_month, self.__startdate_day, self.__starttime_hour, self.__starttime_minute, self.__starttime_second, self.__starttime_offset // 10)

								elapsedtime = time_tmp
								error = 0
								break


				for k in range(0, max_):
					scratchpad[n] = cnv_buf[p + k]

					if scratchpad[n] == 0:
						if zero == 0:
							if k != 0:
								if cnv_buf[p + k - 1] != 20:
									return 33
							n = 0
							onset = 0
							duration = 0
							duration_start = 0
							scratchpad[0] = 0
							annots_in_tal = 0
						zero += 1
						continue
					if zero > 1:
						return 34
					zero = 0

					if (scratchpad[n] == 20) or (scratchpad[n] == 21):
						if scratchpad[n] == 21:
							if (duration != 0) or (duration_start != 0) or (onset != 0) or (annots_in_tal != 0):
								return 35   # it's not allowed to have multiple duration fields in one TAL or to have a duration field which is
														# not immediately behind the onsetfield
							duration_start = 1

						if (scratchpad[n] == 20) and (onset != 0) and (duration_start == 0):
							if (r != 0) or (annots_in_record != 0):
								if duration != 0:
									tmp = self.__atof_nonlocalized(duration_in_txt) * self.EDFLIB_TIME_DIMENSION
									if tmp < -1:
										tmp = -1
								else:
									tmp = -1
								if n > self.EDFLIB_MAX_ANNOTATION_LEN:
									n = self.EDFLIB_MAX_ANNOTATION_LEN
								tmp_str = scratchpad[0 : n].decode("utf-8")
								self.__annots_in_file += 1
								self.annotationslist.append(self.EDFAnnotationStruct(onset = (self.__get_long_time(time_in_txt) - self.__starttime_offset), duration = tmp, description = tmp_str))
							annots_in_tal += 1
							annots_in_record += 1
							n = 0
							continue

						if onset == 0:
							scratchpad[n] = 0
							if self.__is_onset_number(scratchpad) != 0:
								return 36
							onset = 1
							n = 0
							self.__strcpy(time_in_txt, scratchpad)
							continue

						if duration_start != 0:
							scratchpad[n] = 0
							if self.__is_duration_number(scratchpad) != 0:
								return 37

							for j in range(0, n):
								if j == 15:
									break
								duration_in_txt[j] = scratchpad[j]
								if (duration_in_txt[j] < 32) or (duration_in_txt[j] > 126):
									duration_in_txt[j] = 46
							duration_in_txt[j] = 0

							duration = 1
							duration_start = 0
							n = 0
							continue
					n += 1
		return 0


	# Converts a number in ASCII to integer
	def __atoi_nonlocalized(self, str_, i):
		value = 0
		sign = 1
		if i < 0:
			return 0
		
		sz = len(str_)
		if sz < 1:
			return 0

		if i >= sz:
			return 0

		while str_[i] == 32:
			i += 1

		if i >= sz:
			return 0

		if str_[i] == 43 or str_[i] == 45:
			if str_[i] == 45:
				sign = -1
			i += 1

		if i >= sz:
			return 0

		for j in range(i, sz):
			if str_[j] < 48 or str_[j] > 57:
				break
			value *= 10
			value += (str_[j] - 48)

		return (value * sign)
	
	# Checks a string for a valid integer number (left-aligned, filled-up with spaces, etc.)
	def __is_integer_number(self, str_):
		i = 0
		hasspace = 0
		hassign = 0
		digit = 0

		l = len(str_)

		if(l < 1):
			return 1

		if str_[0] == 43 or str_[0] == 45:
			hassign += 1
			i += 1

		for j in range(i, l):
			if str_[j] == 32:
				if(digit == 0):
					return 1
				hasspace += 1
			else:
				if str_[j] < 48 or str_[j] > 57:
					return 1
				else:
					if hasspace > 0:
						return 1
					digit += 1

		if digit > 0:
			return 0
		else:
			return 1

	# Checks a string for a valid (broken) number (left-aligned, filled-up with spaces, etc.)
	def __is_number(self, str_):
		i = 0
		hasspace = 0
		hassign = 0
		digit = 0
		hasdot = 0
		hasexp = 0

		l = len(str_)
		if l < 1:
			return 1

		if str_[0] == 43 or str_[0] == 45:
			hassign += 1
			i += 1

		for j in range(i, l):
			if str_[j] == 101 or str_[j] == 69:
				if digit == 0 or hasexp != 0:
					return 1
				hasexp += 1
				hassign = 0
				digit = 0
				break

			if str_[j] == 32:
				if digit == 0:
					return 1
				hasspace += 1
			else:
				if(str_[j] < 48 or str_[j] > 57) and str_[j] != 46:
					return 1
				else:
					if hasspace != 0:
						return 1
					if str_[j] == 46:
						if hasdot != 0:
							return 1
						hasdot += 1
					else:
						digit += 1

		i = j
		if hasexp != 0:
			i += 1
			if i == l:
				return 1

			if str_[i] == 43 or str_[i] == 45:
				hassign += 1
				i += 1

			for j in range(i, l):
				if str_[i] == 32:
					if digit == 0:
						return 1
					hasspace += 1
				else:
					if str_[i] < 48 or str_[i] > 57:
						return 1
					else:
						if hasspace != 0:
							return 1

						digit += 1

		if digit != 0:
			return 0
		else:
			return 1
	
	# Converts a (broken) number in ASCII to double
	def __atof_nonlocalized(self, str_):
		i = 0
		j = 0
		dot_pos = -1
		decimals = 0
		sign = 1
		exp_pos = -1
		exp_sign = 1
		exp_val = 0
	
		value = 0.0
		value2 = 0.0
	
		l = len(str_)
	
		if l < 1:
			return 0
	
		value = self.__atoi_nonlocalized(str_, 0)
	
		while str_[i] == 32:
			i += 1
	
		if str_[i] == 43 or str_[i] == 45:
			if str_[i] == 45:
				sign = -1
			i += 1
	
		for j in range(i, l):
			if str_[j] == 101 or str_[j] == 69:
				exp_pos = j
				break
	
			if(str_[j] < 48 or str_[j] > 57) and str_[j] != 46:
				break
	
			if dot_pos >= 0:
				if str_[j] >= 48 and str_[j] <= 57:
					decimals += 1
				else:
					break
	
			if str_[j] == 46:
				if dot_pos < 0:
					dot_pos = j
	
		if decimals != 0:
			value2 = self.__atoi_nonlocalized(str_, dot_pos + 1) * sign
	
			i = 1
	
			while 0 != decimals:
				decimals -= 1
				i *= 10
			value2 /= i
			value += value2
	
		if exp_pos > 0:
			i = exp_pos + 1
	
			if i < l:
				if str_[i] == 43:
					i += 1
				else:
					if str_[i] == 45:
						exp_sign = -1
						i += 1
	
			if i < l:
				exp_val = self.__atoi_nonlocalized(str_, i)
	
				if exp_val > 0:
					for j in range(0, exp_val):
						if exp_sign > 0:
							value *= 10
						else:
							value /= 10
	
		return value

	# Get long duration from a string, used for the header only
	def __get_long_duration_hdr(self, str_):
		i = 0
		l = 8
		hasdot = 0
		dotposition = 0
		value = 0
		radix = 0
	
		if str_[0] == 43 or str_[0] == 45:
			for i in range(0, 7):
				str_[i] = str_[i + 1]
			str_[7] = 32
	
		for i in range(0, 8):
			if str_[i] == 32:
				l = i
				break
	
		for i in range(0, l):
			if str_[i] == 46:
				hasdot = 1
				dotposition = i
				break
	
		if hasdot != 0:
			radix = self.EDFLIB_TIME_DIMENSION
	
			for i in range(dotposition - 1, -1, -1):
				value += ((str_[i] - 48) * radix)
				radix *= 10
	
			radix = self.EDFLIB_TIME_DIMENSION / 10
	
			for i in range(dotposition + 1, l):
				value += ((str_[i] - 48) * radix)
				radix /= 10
		else:
			radix = self.EDFLIB_TIME_DIMENSION
	
			for i in range(l - 1, -1, -1):
				value += ((str_[i] - 48) * radix)
				radix *= 10
	
		return value

	# check duration number
	def __is_duration_number(self, str_):
		hasdot = 0
	
		l = len(str_)
		if l < 1:
			return 1
	
		if (str_[0] == 46) or (str_[l-1] == 46):
			return 1
	
		for i in range(0, l):
			if str_[i] == 0:
				if i < 1:
					return 1
				else:
					return 0
	
			if str_[i] == 46:
				if hasdot != 0:
					return 1
				hasdot += 1
			else:
				if (str_[i] < 48) or (str_[i] > 57):
					return 1
	
		return 0

	# check onset number
	def __is_onset_number(self, str_):
		i = 0
		l = 0
		hasdot = 0
	
		l = len(str_)
	
		if l < 2:
			return 1
	
		if (str_[0] != 43) and (str_[0] != 45):
			return 1
	
		if (str_[1] == 46) or (str_[l - 1] == 46):
			return 1
	
		for i in range(1, l):
			if str_[i] == 0:
				if i < 2:
					return 1
				else:
					return 0
	
			if str_[i] == 46:
				if hasdot != 0:
					return 1
				hasdot += 1
			else:
				if (str_[i] < 48) or (str_[i] > 57):
					return 1
	
		return 0

	# get long time
	def __get_long_time(self, str_):
		i = 0
		l = 0
		hasdot = 0
		dotposition = 0
		neg = 0
		value = 0
		radix = 0
	
		l = self.__strlen(str_)
		if l < 1:
			return 0
	
		if str_[0] == 43:
			i += 1
		else:
			if str_[0] == 45:
				neg = 1
				i += 1
	
		for i in range(i, l):
			if str_[i] == 46:
				hasdot = 1
				dotposition = i
				break
	
		if hasdot != 0:
			radix = self.EDFLIB_TIME_DIMENSION
	
			for i in range(dotposition - 1, 0, -1):
				value += ((str_[i] - 48) * radix)
				radix *= 10
	
			radix = self.EDFLIB_TIME_DIMENSION / 10
	
			for i in range(dotposition + 1, l):
				value += ((str_[i] - 48) * radix)
				radix /= 10
	
		else:
			radix = self.EDFLIB_TIME_DIMENSION
	
			for i in range(l - 1, 0, -1):
				value += ((str_[i] - 48) * radix)
				radix *= 10
	
		if neg != 0:
			return -value
	
		return value

	# get string length
	def __strlen(self, str_):
		l = len(str_)
		for i in range(0, l):
			if str_[i] == 0:
				return i
		return (i + 1)

	# copy a string
	def __strcpy(self, dest, src):
		sz = len(dest) - 1
	
		srclen = self.__strlen(src)
	
		if srclen > sz:
			srclen = sz
	
		if srclen < 0:
			return 0
	
		for i in range(0, srclen):
			dest[i] = src[i]
	
		dest[srclen] = 0
	
		return srclen
	
	def as_dict(self):
		header={'__annot_ch': list(self.__annot_ch),
				'__data_record_duration': self.__data_record_duration,
				'__datarecords': self.__datarecords,
				'__edfsignals': self.__edfsignals,
				'__mapped_signals': list(self.__mapped_signals),
				'__nr_annot_chns': self.__nr_annot_chns,
				'__param_annotation': list(self.__param_annotation),
				'__param_bitvalue': list(self.__param_bitvalue),
				'__param_buf_offset': list(self.__param_buf_offset),
				'__param_dig_max': list(self.__param_dig_max),
				'__param_dig_min': list(self.__param_dig_min),
				'__param_label': self.__param_label,
				'__param_offset': list(self.__param_offset),
				'__param_phys_max': list(self.__param_phys_max),
				'__param_phys_min': list(self.__param_phys_min),
				'__param_physdimension': self.__param_physdimension,
				'__param_prefilter': self.__param_prefilter,
				'__param_physdimension': self.__param_physdimension,
				'__param_sample_pntr': list(self.__param_sample_pntr),
				'__param_smp_per_record': list(self.__param_smp_per_record),
				'__param_transducer': self.__param_transducer,
				'__patient': self.__patient.decode('latin-1').split(' ')[:4],
				'__plus_admincode': self.__plus_admincode,
				'__plus_birthdate': self.__plus_birthdate,
				'__plus_equipment': self.__plus_equipment,
				'__plus_gender': self.__plus_gender,
				'__plus_patient_additional': self.__plus_patient_additional,
				'__plus_patient_name': self.__plus_patient_name,
				'__plus_patientcode': self.__plus_patientcode,
				'__plus_recording_additional': self.__plus_recording_additional,
				'__plus_startdate': self.__plus_startdate,
				'__plus_technician': self.__plus_technician,
				'__recording': self.__recording.decode('latin-1').split(' ')[:5],
				'__recordsize': self.__recordsize,
				'__reserved': self.__reserved,
				'__startdate_day': self.__startdate_day,
				'__startdate_month': self.__startdate_month,
				'__startdate_year': self.__startdate_year,
				'__starttime_hour': self.__starttime_hour,
				'__starttime_minute': self.__starttime_minute,
				'__starttime_offset': self.__starttime_offset,
				'__starttime_second': self.__starttime_second
				}
		return header

def edfC2D(file):
	with open(file, 'r+b') as fid:
		assert(fid.tell() == 0)
		fid.seek(192)
		fid.write(bytes(str("EDF+D") + ' ' * (44-len("EDF+D")), encoding="ascii"))

def edfD2C(file):
	with open(file, 'r+b') as fid:
		assert(fid.tell() == 0)
		fid.seek(192)
		fid.write(bytes(str("EDF+C") + ' ' * (44-len("EDF+C")), encoding="ascii"))


#%%
import json

filen = r'D:/ieeg_data/working_dir/Burnham~ Laura_f4d6e656-71f9-4bfa-864d-efb867c18583.EDF'


hdl=EDFfileCheck(filen)
header=hdl.checkEDFheader()
header=hdl.checkAnnotations()
tempdict=hdl.as_dict()

data_path=r'F:\iEEG_study\edf_data\new\sub-043'

files = [x for x in os.listdir(data_path) if x.lower().endswith('.edf')]
for ifile in files:
	with open(os.path.join(data_path,ifile), 'r+b') as fid:
		assert(fid.tell() == 0)
		fid.seek(192)
	# 	print(fid.read(44))
		fid.write(bytes(str("EDF+D") + ' ' * (44-len("EDF+C")), encoding="ascii"))

header[192 : 192 + 5] = bytes("EDF+C", encoding="ascii")


		
edfC2D(filen)
edfD2C(filen)
