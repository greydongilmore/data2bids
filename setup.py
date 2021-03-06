# -*- coding: utf-8 -*-

# A simple setup script to create an executable using PyQt5. This also
# demonstrates the method for creating a Windows executable that does not have
# an associated console.
#
# PyQt5app.py is a very simple type of PyQt5 application
#
# Run the build process by running the command 'python setup.py build'
#
# If everything works well you should find a subdirectory in the build
# subdirectory that contains the files needed to run the application
#
import sys
from cx_Freeze import setup, Executable

base = 'Win32GUI' if sys.platform=='win32' else None

includepackages= ['google','googleapiclient']
includefiles = ['edf2bids.py', 'helpers.py', 'bids2spred.py', 'dicom2bids.py', 'version.json', 'widgets/', 'static/', 'ext_lib/']
includefiles+=['C:\\Users\\greydon\\AppData\\Local\\Programs\\Python\\Python38\\Lib\\site-packages\\google_api_python_client-2.0.2.dist-info']

buildOptions = {
		'build_exe': {
		'includes': 'atexit',
		"include_files": includefiles,
		"packages": includepackages,
		'include_msvcr': True
		}
}

executables = [
	Executable('main.py', base=base, targetName = 'data2bids', icon="static/eplink_icon.ico")
]

setup(name='data2bids',
		version = '1.0',
		description = 'Convert clinical data files to BIDS/SPReD format.',
		options = buildOptions,
		executables = executables)

