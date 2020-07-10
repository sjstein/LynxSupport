import anlLynxUtilities as Utilities
import configparser
import os
import time

from datetime import datetime

# Clear counters and set up constants
RolloverTime = 0
time_acc = 0
config_file = 'listmode.cfg'
ROLLOVERBIT = 0x8000
ROLLOVERMASK = 0x7fff
LYNXINPUT = 1  # Memory bank 1 (MCA)
POLARITY_NEG = True
POLARITY_POS = False
LYNXMEMORYGROUP = 1


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

        #       print(f'Event:{event_nbr} at {event_time * time_conversion} (uS)')
        fn.write(f'{round(event_time * time_conversion, 1)},{event_nbr}\n')
        time_acc += event_dt & ROLLOVERMASK
    #       print(f'time_acc = {time_acc}')
    return nbr_events  # Indicate the number of events processed


# End function definition


# Parse config file
config = configparser.ConfigParser()
config.read(config_file)
lynx_ip = config['LYNX']['Ip']
lynx_user = config['LYNX']['User']
lynx_pw = config['LYNX']['Pw']
det_voltage = config['DETECTOR']['Hv']
acq_time = config['DETECTOR']['Time_Limit']
acq_mode = config['DETECTOR']['Time_Type']
file_pre = config['DATA']['File_Pre']
file_post = config['DATA']['File_Post']
file_chunk = config['DATA']['File_Chunk']

# Set up file naming structure
# Time and date strings for filename
now = datetime.now()
datestr = now.strftime('%d-%b-%Y')
timestr = now.strftime('%H%M')

file_nbr = 0  # Counter to keep track of file number
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
    print(f'Connected to: {device.getParameter(ParameterCodes.Network_MachineName, 0)}')
    device.lock(lynx_user, lynx_pw, LYNXINPUT)  # Take over ownership of device
    device.control(CommandCodes.Stop, LYNXINPUT)  # Stop any running acquisition
    device.control(CommandCodes.Abort, LYNXINPUT)
    device.setParameter(ParameterCodes.Input_Voltage, det_voltage, LYNXINPUT)  # Set HV magnitude
    device.setParameter(ParameterCodes.Input_VoltageStatus, POLARITY_NEG, LYNXINPUT)  # Turn on HV
    while device.getParameter(ParameterCodes.Input_VoltageRamping, LYNXINPUT) is True:  # Wait for HV to ramp
        print('HVPS is ramping...')
        time.sleep(.2)
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

    # Create archive file
    path = f'./{datestr}'
    if not os.path.isdir(path):
        os.mkdir(path)
    fname = f'./{datestr}/{file_pre}_{timestr}_{file_nbr}.{file_post}'
    if os.path.isfile(fname):
        print(f'ERROR: file "{fname}" already exists')
        exit(-1)
    f = open(fname, 'w')
    print(f'Opening file : {fname}')
    f.write('time(us),event\n')

    # Continually poll device and display information while it is acquiring
    while True:
        iteration += 1
        #      print(f'Iteration # {iteration}')
        # Get the status (see ./DataTypes/ParameterTypes.py for enumerations
        status = device.getParameter(ParameterCodes.Input_Status, LYNXINPUT)
        if (status & StatusBits.Busy) == 0 and (status & StatusBits.Waiting) == 0:
            # No longer acquiring data - time to exit
            f.write(f'Total events processed: {file_events}')
            break
        fault = device.getParameter(ParameterCodes.Input_Fault, LYNXINPUT)
        # Not sure if we should act on a fault or not - TBD

        # Get the list data
        t_list = device.getListData(LYNXINPUT)
        #    print(f'Printing info for list state: {t_list}')
        #    print(f'Start time (uS): {t_list.getStartTime()}')
        #    print(f'Live time (uS): {t_list.getLiveTime()}')
        #    print(f'Real time (uS): {t_list.getRealTime()}')
        #    print(f'Timebase (nS?): {t_list.getTimebase()}')
        #    print(f'Flags: {t_list.getFlags()}')
        # archive the events
        events_processed = output_tlist(t_list, t_list.getTimebase(), False, f)
        file_events += events_processed
        total_events += events_processed

        if (file_events > float(file_chunk)) & (float(file_chunk) != -1):  # Time to start a new file
            f.write(f'Total events processed: {file_events}')
            file_events = 0
            file_nbr += 1
            f.close()
            fname = f'./{datestr}/{file_pre}_{timestr}_{file_nbr}.{file_post}'
            print(f'Starting new file ({fname}) after writing {file_events} events')
            f = open(fname, 'w')
            f.write('time(us),event\n')

    print(f'Acquisition complete : total events = {total_events}')
    f.close()

except Exception as e:
    Utilities.dumpException(e)
