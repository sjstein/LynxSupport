import anlLynxUtilities as Utilities
import argparse
import configparser
import os
import time

from datetime import datetime

from aspLibs.aspUtilities import IntRange
from aspLibs.aspUtilities import V_NONE, V_HIGH
from aspLibs.aspUtilities import DATA_DIR
from aspLibs.aspUtilities import AspLogger

# Clear counters and set up constants
RolloverTime = 0
time_acc = 0
config_file = 'lynxlistmode.cfg'
ROLLOVERBIT = 0x8000
ROLLOVERMASK = 0x7fff
LYNXINPUT = 1  # Memory bank 1 (MCA)
POLARITY_NEG = True
POLARITY_POS = False
LYNXMEMORYGROUP = 1
COL_HEADER = 'T_us,ch\n'


def output_tlist(td, time_base, clear, fn):
    """
    Description:
        Write timestamped events to file
    Arguments:
        td (in, TlistData)  The time stamped list data buffer.
        time_base (in, int) The time base (nS)
        clear (in, bool)    Resets the global time counter
        fn (in, str)        Filename to write TList data to
    Return:
        int                 Number of events processed

    Note:
        When a rollover occurs, the MSBit (bit 15) of event_Time is set.
        At this point, the **event** variable contains bits 30-45 of the time (no event info).
        This means: The event number is 15 bits, so can be (int)0 to (int)32,768
        If a rollover occurs, it appears we are notified of this via the rollover flag (bit 15 in eventTime)
        regardless of if an event happened. This is to keep us in sync with the new state of the clock.
    """

    global RolloverTime, time_acc
    if clear:
        RolloverTime = 0
        time_acc = 0

    time_conversion = time_base / 1000  # Conversion to uS

    nbr_events = len(td.getEvents())

    for event in td.getEvents():
        event_dt = event.getTime()
        event_nbr = event.getEvent()
        if (event_dt & ROLLOVERBIT) == 0:  # Normal event
            event_time = RolloverTime | (event_dt & ROLLOVERMASK)  # add new time increment
        else:
            # Rollover event - adjust clock
            nbr_events -= 1  # This isn't a real event, so don't count
            tc_lsb = int(0)
            tc_msb = int(0)
            tc_lsb |= (event_dt & ROLLOVERMASK) << 15  # Mask off the rollover bit and push up to the MSB
            tc_msb |= event_nbr << 30  # During rollover, event_nbr has time info instead of event number
            RolloverTime = tc_msb | tc_lsb  # Adjust our clock for larger time
            continue  # goto next event, do not record this rollover
        locdatestr = datetime.now().strftime('%Y%m%d')
        loctimestr = datetime.now().strftime('%H:%M:%S.%f')
        fn.write(f'{round(event_time * time_conversion, 1)},{event_nbr},{locdatestr} {loctimestr}\n')
        time_acc += event_dt & ROLLOVERMASK
    return nbr_events  # Indicate the number of events processed
# End function definition


parser = argparse.ArgumentParser(description='Python script to configure and take listmode data from a LYNX MCA.',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('-c', '--config', help='Name of configuration file.', default=config_file)
parser.add_argument('-v', '--verbosity', help=f'Verbosity level {V_NONE} (silent) to {V_HIGH} (most verbose).',
                    type=IntRange(V_NONE, V_HIGH), default=2)
args = parser.parse_args()
log = AspLogger(args.verbosity)

# Parse config file
config = configparser.ConfigParser()
config.read(args.config)
lynx_ip = config['LYNX']['Ip']
lynx_user = config['LYNX']['User']
lynx_pw = config['LYNX']['Pw']
control_hv = config['LYNX']['Control_Hv']
control_hv = True if control_hv.lower() == 'true' else False    # Default to False for malformed parm in cfg file
det_voltage = config['DETECTOR']['Hv']
acq_time = config['DETECTOR']['Time_Limit']
acq_mode = config['DETECTOR']['Time_Type']
file_pre = config['DATA']['File_Pre'].replace(' ', '_')
file_post = config['DATA']['File_Post'].replace(' ', '_')
file_chunk = config['DATA']['File_Chunk']
det_name = config['DETECTOR']['Name']
det_serial = config['DETECTOR']['Sn']
file_note1 = config['DATA']['File_Note1']
file_note2 = config['DATA']['File_Note2']

# Set up file naming structure
# Time and date strings for filename
now = datetime.now()
datestr = now.strftime('%Y%m%d')
timestr = now.strftime('%H%M')

file_nbr = 1  # Counter to keep track of file number
file_events = 0  # Counter to keep track of events written in each file

# Main loop
try:
    # Setup the Python env
    Utilities.setup()

    # Grab basically everything possible. Barf.
    from DeviceFactory import *
    from ParameterCodes import *
    from CommandCodes import *
    from ParameterTypes import *
    from ListData import *

    device = DeviceFactory.createInstance(DeviceFactory.DeviceInterface.IDevice)  # Create the interface
    device.open("", lynx_ip)  # Open connection
    log.info(f'Connected to: {device.getParameter(ParameterCodes.Network_MachineName, 0)}')
    device.lock(lynx_user, lynx_pw, LYNXINPUT)  # Take over ownership of device
    device.control(CommandCodes.Stop, LYNXINPUT)  # Stop any running acquisition
    device.control(CommandCodes.Abort, LYNXINPUT)
    if control_hv:
        log.info(f'Turning on HV, magnitude: {det_voltage}')
        device.setParameter(ParameterCodes.Input_Voltage, det_voltage, LYNXINPUT)  # Set HV magnitude
        device.setParameter(ParameterCodes.Input_VoltageStatus, POLARITY_NEG, LYNXINPUT)  # Turn on HV
        while device.getParameter(ParameterCodes.Input_VoltageRamping, LYNXINPUT) is True:  # Wait for HV to ramp
            log.warn('HVPS is ramping...')
            time.sleep(.5)
        read_hv = device.getParameter(ParameterCodes.Input_Voltage, LYNXINPUT)
    else:
        read_hv = device.getParameter(ParameterCodes.Input_Voltage, LYNXINPUT)
        status_hv = device.getParameter(ParameterCodes.Input_VoltageStatus, LYNXINPUT)
        log.info(f'Using preset HV setting: {read_hv}')
        if not status_hv:
            log.erro(f'Lynx high voltage supply is currently set to OFF - aborting acquisition.')
            exit(-1)
    device.setParameter(ParameterCodes.Input_Mode, InputModes.Tlist, LYNXINPUT)  # set Tlist acquisition mode
    device.setParameter(ParameterCodes.Input_ExternalSyncStatus, 0, LYNXINPUT)  # Disable external sync
    if acq_mode == 'Live':  # Set up acquisition time and type
        device.setParameter(ParameterCodes.Preset_Live, acq_time, LYNXINPUT)
    else:
        device.setParameter(ParameterCodes.Preset_Real, acq_time, LYNXINPUT)
    device.control(CommandCodes.Clear, LYNXINPUT)  # Reset memory
    device.setParameter(ParameterCodes.Input_CurrentGroup, LYNXMEMORYGROUP, LYNXINPUT)  # Using memory group 1
    device.control(CommandCodes.Start, LYNXINPUT)  # Start acquisition

    iteration = 0
    total_events = 0

    # Read energy coefficients for archiving
    energy_offset = device.getParameter(ParameterCodes.Calibrations_Energy_Offset, LYNXINPUT)
    energy_slope = device.getParameter(ParameterCodes.Calibrations_Energy_Slope, LYNXINPUT)

    # Create subdirectories for data archiving
    if not os.path.isdir(DATA_DIR):
        os.mkdir(DATA_DIR)
    data_path = f'{DATA_DIR}/{datestr}'
    if not os.path.isdir(data_path):
        os.mkdir(data_path)

    # Create info file
    iname = f'{data_path}/logInfo_{file_pre}_{datestr}_{timestr}.txt'
    if os.path.isfile(iname):
        log.erro(f'info file "{iname}" already exists')
        exit(-1)
    ifile = open(iname, 'w')
    log.info(f'Opening info file : {iname}')
    ifile.write(f'Note 1: {file_note1}\n')
    ifile.write(f'Note 2: {file_note2}\n')
    ifile.write(f'Detector: {det_name}, s/n: {det_serial}, voltage: {read_hv}\n')
    ifile.write(f'Calibration: {energy_offset} {energy_slope}\n')
    ifile.write('Files written:\n--------------\n')
    ifile.close()   # No need to leave open until writing data

    # Create archive file
    fname = f'{data_path}/{file_pre}_{datestr}_{timestr}_{file_nbr}.{file_post}'
    if os.path.isfile(fname):
        log.erro(f'archive file "{fname}" already exists')
        exit(-1)
    f = open(fname, 'w')
    log.info(f'Opening archive file : {fname}')
    f.write(COL_HEADER)
    # Leaving the archive file open as it is written so frequently
    # Perhaps not the best idea?

    # Continually poll device and display information while it is acquiring
    while True:
        iteration += 1
        # Get the status (see ./DataTypes/ParameterTypes.py for enumerations
        status = device.getParameter(ParameterCodes.Input_Status, LYNXINPUT)
        if (status & StatusBits.Busy) == 0 and (status & StatusBits.Waiting) == 0:
            # No longer acquiring data - time to exit
            break
        fault = device.getParameter(ParameterCodes.Input_Fault, LYNXINPUT)
        # Not sure if we should act on a fault or not - TBD

        # Get the list data
        t_list = device.getListData(LYNXINPUT)
        log.disp(f'Start time: {t_list.getStartTime()}')
        if acq_mode == 'Live':
            log.disp(f'Live time (s): {t_list.getLiveTime() / 1e6}')
        else:
            log.disp(f'Real time (s): {t_list.getRealTime() / 1e6}')
        log.disp(f'Flags: {t_list.getFlags()}')

        # archive the events
        events_processed = output_tlist(t_list, t_list.getTimebase(), False, f)
        log.disp(f'Events: {events_processed}')
        file_events += events_processed
        total_events += events_processed
        if (file_events > float(file_chunk)) & (float(file_chunk) != -1):  # Time to start a new file
            ifile = open(iname, 'a')
            ifile.write(f'{fname } ({file_events} events)\n')    # Record file info
            ifile.close()
            f.close()
            file_nbr += 1
            fname = f'{data_path}/{file_pre}_{datestr}_{timestr}_{file_nbr}.{file_post}'
            log.info(f'Starting new file ({fname}) after writing {file_events} events')
            file_events = 0
            f = open(fname, 'w')
            f.write(COL_HEADER)

    log.info(f'Acquisition complete : total events = {total_events}')
    ifile = open(iname, 'a')
    ifile.write(f'{fname} ({file_events} events)\n--------------\n')  # Record file info
    ifile.write(f'A total of {total_events} events archived.\n')
    f.close()
    ifile.close()

except Exception as e:
    Utilities.dumpException(e)
