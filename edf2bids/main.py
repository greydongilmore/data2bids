# -*- coding: utf-8 -*-
"""
Created on Sat Dec 29 13:49:51 2018

@author: Greydon
"""
import os
import sys
import numpy as np
import pandas as pd
pd.set_option('precision', 6)
import json
from collections import OrderedDict
import datetime
from shutil import copyfile
import gzip
import mne
import re

from edf2bids.helpers import EDFReader, padtrim, sorted_nicely, partition, determine_groups, is_float

# Metadata used for the dataset decription
ieeg_file_metadata = {
        'TaskName': '24hr Recording',
        'Experimenter': ['Greydon Gilmore'],
        'Lab': 'Khan Lab',
        'InstitutionName': 'Western University',
        'InstitutionAddress': '339 Windermere Road, London, Ontario, Canada',
        'ExperimentDescription': '',
        'DatasetName': '',
        }

# Metadeata for the equipment used for recordings 
natus_info = {
        'Manufacturer': 'Natus',
        'ManufacturersModelName': 'Neuroworks',
        'SamplingFrequency': 1000,
        'HighpassFilter': np.nan,
        'LowpassFilter': np.nan,
        'MERUnit': 'uV',
        'PowerLineFrequency': 60,
        'RecordingType': 'continuous',
        'iEEGCoordinateSystem': 'continuous',
        'ElectrodeInfo': {
                'Manufacturer': 'AdTech',
                'Type': 'depth',
                'Material': 'Platinum',
                'Diameter': 1.3
                }
     }

# Metadata used for the coordinate information 
coord_system_info = {
                'ACPC': {'Units': 'mm', 
                         'Description': 'Coordinate system with the origin at anterior '\
                                        'commissure (AC), negative y-axis going through the posterior '\
                                        'commissure (PC), z-axis going to a mid-hemisperic point which '\
                                        'lies superior to the AC-PC line, x-axis going to the right.',
                         'ProcessingDescription': 'surface_projection',
                         'IntendedFor': ''}
                }

# Channel description for the recording equipment
natus_channel_info = {
                'DC': {'type': 'DAC', 'name': 'DAC'},
                'TRIG': {'type': 'TRIG', 'name': 'TR'},
                'OSAT': {'type': 'OSAT', 'name': 'OSAT'},
                'PR': {'type': 'PR', 'name': 'MISC'},
                'Pleth': {'type': 'Pleth', 'name': 'MISC'},
                'EDF Annotations': {'type': 'Annotations', 'name': 'ANNO'},
                'C': {'type': 'unused', 'name': 'unused'}
                }

def _write_tsv(fname, df, overwrite=False, verbose=False, append = False):
    """
    Write dataframe to a .tsv file
    
    """
    
    if os.path.exists(fname) and not overwrite:
        pass
    
    if os.path.exists(fname) and append:
        with open(fname,'a') as fd:
            df.to_csv(fd, sep='\t', index=False, header = False, na_rep='n/a')
    else:
        df.to_csv(fname, sep='\t', index=False, na_rep='n/a')

def _write_json(dictionary, fname, overwrite=False, verbose=False):
    """
    Write JSON to a file.
    
    """
    
    json_output = json.dumps(dictionary, indent=4)
    with open(fname, 'w') as fid:
        fid.write(json_output)
        fid.write('\n')

    if verbose is True:
        print(os.linesep + "Writing '%s'..." % fname + os.linesep)
        print(json_output)

#ifile = file_list[1]
def get_file_info(raw_file_path):
    """
    Extract header data from EDF file.
    
    """
    file_list = [x.lower() for x in os.listdir(raw_file_path) if x.endswith('.edf')]
    filesInfo = []
    for ifile in file_list:
        filen = os.path.join(raw_file_path, ifile)
        file_in = EDFReader()
        try:
            meas_info, chan_info = file_in.open(filen)
            header = file_in.readHeader()
            file_in.close()
            
            values = partition(header[1]['ch_names'])
            seeg_chan_idx = [i for i, x in enumerate(values) if x[0] not in list(natus_channel_info.keys())]
            group_info = determine_groups(np.array(header[1]['ch_names'])[seeg_chan_idx])
            
            file_info = [
                ('FileName', ifile),
                ('Gender', meas_info['gender']),
                ('Age', int(np.floor(((datetime.datetime.strptime(meas_info['meas_date'].split(' ')[0],"%Y-%m-%d") 
                        - datetime.datetime.strptime(datetime.datetime.strptime(meas_info['birthdate'],
                        '%d-%b-%Y').strftime('%Y-%m-%d'),"%Y-%m-%d")).days)/365)) if meas_info['birthdate'] else ''),
                ('Date', meas_info['meas_date'].split(' ')[0]),
                ('Time', meas_info['meas_date'].split(' ')[1]),
                ('DataOffset', meas_info['data_offset']),
                ('NRecords', meas_info['n_records']),
                ('RecordLength', meas_info['record_length']),
                ('NChan', meas_info['nchan']),
                ('Highpass', meas_info['highpass']),
                ('Lowpass', meas_info['lowpass']),
                ('Groups', group_info)]
            
            ch_info = {}
            ch_info['SEEG'] = OrderedDict([
                ('ChannelCount', len(seeg_chan_idx)),
                ('Unit', np.array(header[1]['units'])[seeg_chan_idx]),
                ('ChanName', np.array(header[1]['ch_names'])[seeg_chan_idx]),
                ('Type', 'SEEG')])
            
            for key in natus_channel_info.keys():
                chan_idx = [i for i, x in enumerate(values) if x[0] == key]
                ch_info[key] = OrderedDict([
                        ('ChannelCount', len(chan_idx)),
                        ('Unit', np.array(header[1]['units'])[chan_idx]),
                        ('ChanName', np.array(header[1]['ch_names'])[chan_idx]),
                        ('Type', natus_channel_info[key]['name'])])
            
            file_info.append(['ChanInfo',OrderedDict(ch_info)])
            
            file_info = OrderedDict(file_info)
            file_info['ChanInfo'] = ch_info
            filesInfo.append(file_info)
        except:
            print('Something wrong with file', ifile)
        
    filesInfo = sorted(filesInfo, key=lambda k: (k['Date'], k['Time'])) 
    
    return filesInfo

def make_bids_filename(subject_id=None, session_id=None, run=None, suffix=None, prefix=None):
    """
    Generate a BIDS filename.
    
    """
    if isinstance(session_id, str):
        if 'ses' in session_id:
            session_id = session_id.split('-')[1]
            
    order = OrderedDict([('sub', subject_id if subject_id is not None else None),
                         ('ses', session_id if session_id is not None else None),
                         ('run', run if run is not None else None)])

    filename = []
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
    Generate a BIDS folder structure.
    
    """
    path = []
    if 'sub' not in subject_id:
        path = ['-'.join(['sub', subject_id])]
    else:
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

def _dataset_json(dataset_fname):
    """
    Dataset description JSON file.
    
    """
    info_dataset_json = OrderedDict([
        ('Name', ieeg_file_metadata['DatasetName']),
        ('BIDSVersion', ''),
        ('License', ''),
        ('Authors', ieeg_file_metadata['Experimenter']),
        ('Acknowledgements', 'say here what are your acknowledgments'),
        ('HowToAcknowledge', 'say here how you would like to be acknowledged'),
        ('Funding', ["list your funding sources"]),
        ('ReferencesAndLinks', ["a data paper", "a resource to be cited when using the data"]),
        ('DatasetDOI', '')])
    
    _write_json(info_dataset_json, dataset_fname)

def _participants_data(subject_id, file_info_sub, participants_fname):
    """
    Participant tsv file generation.
    
    """
    if subject_id is None:
        with open(participants_fname, 'w') as writeFile:
            writeFile.write("\t".join(['participant_id','age','sex','group']))
            writeFile.write( "\n" )
            
    else:
        df = pd.DataFrame(OrderedDict([
                          ('participant_id', 'sub-' + subject_id if subject_id is not None else ''),
                          ('age', file_info_sub[0]['Age']),
                          ('sex', file_info_sub[0]['Gender']),
                          ('group', 'patient')]), index= [0])
    
        _write_tsv(participants_fname, df, overwrite=False, verbose=False, append = True) 
    
def _scans_data(file_name, file_info_run, scans_fname, systemInfo):
    """
    Scans tsv file with session specific recording information.
    
    """
    acq_time = 'T'.join([file_info_run['Date'].replace('_','-'), file_info_run['Time']])
    
    df = pd.DataFrame(OrderedDict([
                  ('filename', file_name),
                  ('acq_time', acq_time),
                  ('duration', round((((file_info_run['NRecords']*128)/systemInfo['SamplingFrequency'])/60)/60,3))
                  ]), index=[0])
    
    _write_tsv(scans_fname, df, overwrite=False, verbose=False, append = True)        
    
def _coordsystem_json(file_info_run, coord_fname, coord_intendedFor, systemInfo, overwrite=False, verbose=False):
    """
    Coordinate system JSON file.
    
    """
    coord_info = coord_system_info[list(coord_system_info.keys())[0]]
    
    info_coordsystem_json = OrderedDict([
        ('iEEGCoordinateSystem', list(coord_system_info.keys())[0]),
        ('iEEGCoordinateUnits', coord_info['Units']),
        ('iEEGCoordinateSystemDescription', coord_info['Description']),
        ('iEEGCoordinateProcessingDescription', coord_info['ProcessingDescription']),
        ('IntendedFor', coord_intendedFor)])
    
    _write_json(info_coordsystem_json, coord_fname, overwrite, verbose)
    
    print('Finished writing', coord_fname.split('\\')[-1], '\n')
    
def _electrodes_data(file_info_run, electrodes_fname, systemInfo, coordinates=None, electrode_imp=None, overwrite=False, verbose=False):
    """
    Electrodes data tsv file for each session.
    
    """
    include_chans = ['SEEG']
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
                values.append([x for x in file_info_run['Groups'] if item.startswith(x)][0])
                material.append(systemInfo['ElectrodeInfo']['Material'])
                manu.append(systemInfo['ElectrodeInfo']['Manufacturer'])
                size.append(systemInfo['ElectrodeInfo']['Diameter'])
                typ.append('depth')
        else:
            values = np.repeat('n/a', len(info_temp['ChanName']))
            material = np.repeat('n/a', len(info_temp['ChanName']))
            manu = np.repeat('n/a', len(info_temp['ChanName']))
            size = np.repeat('n/a', len(info_temp['ChanName']))
            typ = np.repeat('n/a', len(info_temp['ChanName']))

        df = pd.DataFrame(OrderedDict([
                      ('name', info_temp['ChanName']),
                      ('x', coordinates[0] if coordinates is not None else None),
                      ('y', coordinates[1] if coordinates is not None else None),
                      ('z', coordinates[2] if coordinates is not None else None),
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
    
    _write_tsv(electrodes_fname, df_electrodes, overwrite, verbose, append = True)
    
    print('Finished writing', electrodes_fname.split('\\')[-1], '\n')

#file_info_run = file_data[irun]
#ichan = chan_idx[0]
def _channels_data(file_info_run, channels_fname, run, systemInfo, data_path, overwrite=False, verbose=False):
    """
    Channels data tsv file for each session.
    
    """
    include_chans = ['SEEG']
    chan_idx = [i for i, x in enumerate(list(file_info_run['ChanInfo'].keys())) if x in include_chans]
    mainDF = pd.DataFrame([])
    for ichan in chan_idx:
        info_temp = file_info_run['ChanInfo'][list(file_info_run['ChanInfo'].keys())[ichan]]
        
        if 'SEEG' in info_temp['Type']:
            values = []
            for item in info_temp['ChanName']:
                values.append([x for x in file_info_run['Groups'] if item.startswith(x)][0])
        else:
            values = np.repeat('n/a', len(info_temp['ChanName']))

        df = pd.DataFrame(OrderedDict([
                      ('name', info_temp['ChanName']),
                      ('type', np.repeat(info_temp['Type'], len(info_temp['ChanName']))),
                      ('units', info_temp['Unit']),
                      ('sampling_frequency', np.repeat(systemInfo['SamplingFrequency'], len(info_temp['ChanName']))),
                      ('low_cutoff', np.repeat(file_info_run['Lowpass'] if file_info_run['Lowpass'] is not None else 'n/a', len(info_temp['ChanName']))),
                      ('high_cutoff', np.repeat(file_info_run['Highpass'] if file_info_run['Highpass'] is not None else 'n/a', len(info_temp['ChanName']))),
                      ('notch', np.repeat('n/a',len(info_temp['ChanName']))),
                      ('reference', np.repeat('n/a',len(info_temp['ChanName']))),
                      ('group', values)]))
        
        mainDF = pd.concat([mainDF, df], ignore_index = True, axis = 0) 
        
    _write_tsv(channels_fname, mainDF, overwrite, verbose, append = False)
    
    print('Finished writing', channels_fname.split('\\')[-1], '\n')

def _annotations_data(file_info_run, annotation_fname, data_path, raw_file_path, overwrite, verbose):
    """
    Annotations data tsv file for each session. Patient specific annotations 
    about seizure events etc.
    
    """
    ignoreNotes = ('Closed','De-block','Opened','Video','Impedance', 'Stop Recording','Saturation Recovery','Breakout box','Gain/Filter','Clip Note',
                   'Headbox Disconnecting', 'Headbox Reconnected')
    
    file_in = EDFReader()
    file_in.open(os.path.join(raw_file_path, file_info_run['FileName']))
    header = file_in.readHeader()
    chanindx = [x for x in header[1]['ch_names'] if not x.endswith('Annotations')]
    annotTemp = mne.io.read_raw_edf(os.path.join(raw_file_path, file_info_run['FileName']), preload=True, exclude = chanindx[1:], verbose=None)
    events_edf = annotTemp.find_edf_events()[[i for i,x in enumerate(annotTemp.find_edf_events()) if not x[2].isdigit() and not is_float(x[2]) and not x[2].startswith(ignoreNotes)]]
    file_in.close()

    df = pd.DataFrame(OrderedDict([
                      ('timestamp', [x[0] for x in events_edf]),
                      ('event', [x[2] for x in events_edf])]))
                
    _write_tsv(annotation_fname, df, overwrite, verbose, append = True)

def _sidecar_json(file_info_run, sidecar_fname, run, systemInfo, kind, overwrite=False, verbose=False):
    """
    Sidecar JSON file for the edf file.
    
    """
    info_sidecar_json = OrderedDict([
        ('TaskName', ieeg_file_metadata['TaskName']),
        ('InstitutionName', ieeg_file_metadata['InstitutionName']),
        ('InstitutionAddress', ieeg_file_metadata['InstitutionAddress']),
        ('Manufacturer', systemInfo['Manufacturer']),
        ('ManufacturersModelName', systemInfo['ManufacturersModelName']),
        ('SamplingFrequency', systemInfo['SamplingFrequency']),
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
        ('PowerLineFrequency', systemInfo['PowerLineFrequency']),
        ('RecordingDuration', round((((file_info_run['NRecords']*128)/systemInfo['SamplingFrequency'])/60)/60,3)),
        ('RecordingType', 'continuous'),
        ('SubjectArtefactDescription', ''),
        ('iEEGPlacementScheme', ''),
        ('iEEGElectrodeGroups', ''),
        ('iEEGReference', ''),
        ('ElectrodeManufacturer', systemInfo['ElectrodeInfo']['Manufacturer']),
        ('ElectricalStimulationParameters', '')])
    
    _write_json(info_sidecar_json, sidecar_fname, overwrite, verbose)
    
    print('Finished writing', sidecar_fname.split('\\')[-1], '\n')

#file_data = [file_info[ises]]
#overwrite = False
#make_dir = False
def raw_to_bids(subject_id, session_id, file_data, systemInfo, raw_file_path, output_path,
                    coordinates, electrode_imp, make_dir, overwrite, verbose, compress):
    """
    Main loop for building BIDS database
    
    """
    data_path = make_bids_folders(subject_id, session_id, 'ieeg', output_path, make_dir, overwrite)
    electrodes_fname = make_bids_filename(subject_id, session_id, run=None, suffix='electrodes.tsv', prefix=data_path)
    coord_fname = make_bids_filename(subject_id, session_id, run=None, suffix = 'coordsystem.json', prefix=data_path)
    Intended_for = data_path.split('sub')[-1].split('\\')
    num_runs = len(file_data)

    for irun in range(num_runs):
        run = str(irun+1).zfill(2)
            
        channels_fname = make_bids_filename(subject_id, session_id, run, suffix='channels.tsv', prefix=data_path)
        sidecar_fname = make_bids_filename(subject_id, session_id, run, suffix='ieeg.json', prefix=data_path)
        data_fname = make_bids_filename(subject_id, session_id, run, suffix = 'ieeg.edf', prefix=data_path)
        scans_fname = make_bids_filename(subject_id, session_id=None, run=None, suffix='scans.tsv', prefix=os.path.join(output_path, 'sub-'+subject_id))
        annotation_fname = make_bids_filename(subject_id, session_id, run, suffix='annotations.tsv', prefix=data_path)
        
        # De-identify the file
        with open(os.path.join(raw_file_path, file_data[irun]['FileName']), 'r+b') as fid:
            assert(fid.tell() == 0)
            fid.seek(8)
            fid.write(padtrim('sub-' + subject_id, 80).encode('utf-8')) # subject id
            fid.write(padtrim(make_bids_filename(None, session_id, run, suffix='ieeg.edf', prefix=''), 80).encode('utf-8')) # recording id
            
        # File compression using GZIP
        if compress:
            with open(os.path.join(raw_file_path, file_data[irun]['FileName']), 'rb') as src, gzip.open(data_fname + '.gz', 'wb') as dst:        
                dst.writelines(src)
            coord_intendedFor_suffix = 'ieeg.edf.gz'
            data_fname = data_fname + '.gz'
        else:
            copyfile(os.path.join(raw_file_path, file_data[irun]['FileName']), data_fname)
            coord_intendedFor_suffix = 'ieeg.edf'
        
        _annotations_data(file_data[irun], annotation_fname, data_path, raw_file_path, overwrite, verbose)
        
        _scans_data('/'.join(data_fname.split('\\')[-2:]), file_data[irun], scans_fname, systemInfo)
        
        _channels_data(file_data[irun], channels_fname, run, systemInfo, data_path, overwrite=overwrite, verbose=verbose)
        _sidecar_json(file_data[irun], sidecar_fname, run, systemInfo, 'mer', overwrite=overwrite, verbose=verbose)
    
    coord_intendedFor = make_bids_filename(subject_id, session_id, run=run, suffix = coord_intendedFor_suffix, prefix='/'.join(['sub'+Intended_for[0]] + Intended_for[1:])).replace('\\','/')
    _electrodes_data(file_data[irun], electrodes_fname, systemInfo, coordinates=coordinates, electrode_imp=electrode_imp, overwrite=overwrite, verbose=verbose)
    _coordsystem_json(file_data[irun], coord_fname, coord_intendedFor, systemInfo, overwrite=overwrite, verbose=verbose)

#%%   
data_dir = r'F:\projects\iEEG\sourcedata'
output_path = r'F:\projects\iEEG\bids'
compression = True
ifold = folders[5]
session_start = 1
ises = 1
def main(data_dir, output_path, compression):
    
    dataset_fname = make_bids_filename(None, session_id=None, run=None, suffix='dataset_description.json', prefix=output_path)
    if not os.path.exists(dataset_fname):
        _dataset_json(dataset_fname)
        
    folders = sorted_nicely([x for x in os.listdir(data_dir) if x.startswith('sub')])
    participants_fname = make_bids_filename(None, session_id=None, run=None, suffix='participants.tsv', prefix=output_path)
    
    if os.path.exists(participants_fname):
        participant_tsv = pd.read_table(participants_fname)
    else:
        _participants_data(None, participants_fname)
        participant_tsv = pd.read_table(participants_fname)
        
    for ifold in folders: 
        subject_id = 'P' + ifold.split('-')[1]          
        raw_file_path = os.path.join(data_dir, ifold)
        file_info = get_file_info(raw_file_path)
        num_sessions = len(file_info)
        newSessions = True
        
        # True if subject already in participant.tsv file
        if 'sub-' + subject_id in participant_tsv['participant_id'].values:
            in_table = True
            sessionsDone = sorted_nicely([x for x in os.listdir(os.path.join(output_path,'sub-'+subject_id)) if x.startswith('ses')])
            
            # Determine if new sessions to run, and where to begin
            if len(sessionsDone) < num_sessions:
                session_start = num_sessions-(num_sessions - len(sessionsDone))
            else:
                newSessions = False
        else:
            session_start = 0
            in_table = False
            
        if newSessions:
            for ises in range(session_start, num_sessions):
                session_id = str(ises+1).zfill(3)
                systemInfo = natus_info
    
                raw_to_bids(subject_id, session_id, [file_info[ises]], systemInfo, raw_file_path, output_path,
                            coordinates=None, electrode_imp=None, make_dir=True, overwrite=True, verbose=False, compress=compression)
            
            if not in_table: 
                _participants_data(subject_id, [file_info[0]], participants_fname)
                
            participant_tsv = pd.read_table(participants_fname)
            
        else:
            print('Participant', 'sub-' + subject_id, 'already exists in the dataset!')
        
if __name__ == "__main__":

    if len(sys.argv)-1 < 1:
        print ("Usage: python " + os.path.basename(__file__) +
               " data_dir output_dir")
        sys.exit()
    else:
        data_dir = sys.argv[1]
        output_dir = sys.argv[2]
        if len(sys.argv)>3:
            compression = sys.argv[3]
            if compression=='True':
                compression = True
                print("Will compress the EDF file.")
            else:
                compression = False
                print("Will not compress the EDF file.")
        else:
            compression = False
            print("Will not compress the EDF file.")
  
    main(data_dir, output_dir, compression)