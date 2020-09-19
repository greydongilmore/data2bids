
class EDFexception(Exception):
	def __init__(self, message):
		self.message = message
		super().__init__(self.message)

def checkEDFheader(self, data_fname):

	try:
		self.__file_in = open(data_fname, "rb")
	except OSError as e:
		raise EDFexception("Can not open file for reading: %s" %(e.strerror))

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

	self.__filestart_dt = datetime(self.__startdate_year, self.__startdate_month, self.__startdate_day, self.__starttime_hour, self.__starttime_minute, self.__starttime_second, 0)

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
		self.__filetype = 0
		if self.__reserved[:5] == "EDF+C":
			self.__edfplus = 1
			self.__filetype = 1
		if self.__reserved[:5] == "EDF+D":
			self.__edfplus = 1
			self.__discontinuous = 1
			self.__filetype = 1
	if self.__bdf:
		self.__filetype = 2
		if self.__reserved[:5] == "BDF+C":
			self.__bdfplus = 1
			self.__filetype = 3
		if self.__reserved[:5] == "BDF+D":
			self.__bdfplus = 1
			self.__discontinuous = 1
			self.__filetype = 3

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
		if self.__param_transducer[i] != "":
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
		if self.__param_prefilter[i] != "":
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