
import anlLynxUtilities as Utilities
import configparser
import os
import time

from datetime import datetime



RolloverTime=int(0)                #This needs to be clears after a start command.
time_acc=int(0)
ROLLOVERBIT=0x00008000              #The rollover bit


def outputTlist(td, timeBase, clear, fn):
    """
    Description:
        This method will reconstruct the time events for time
        stamped list mode before displaying on output
    Arguments:
        td (in, TlistData).  The time stamped list data buffer.
        timeBase (in, int).  The time base (nS)
        clear (in, bool).    Resets the global time counter
        fn (in, str).        Filename to write TList data to
    Return:
        noneP
    """

    # When a rollover occurs, the MSBit (bit 15) of eventTime is set.
    #  At this point, the **event** variable contains bits 30-45 of the time (no event info).
    # This means: The event number is 15 bits, so can be (int)0 to (int)32,768
    # If a rollover occurs, it appears we are notified of this via the rollover flag (bit 15 in eventTime)
    #  regardless of if an event happened. This is to keep us in sync with the new state of the clock.

    global RolloverTime, time_acc
    if (clear):
        RolloverTime = int(0)
        time_acc = int(0)

    recTime = 0
    recEvent = 0
    time = int(0)
    conv = float(timeBase)
    conv /= 1000  # Convert to uS

    nbrEvents = len(td.getEvents())
    eventCount = 0

    for event in td.getEvents():
        recTime = event.getTime()
        recEvent = event.getEvent()

        if (recTime & ROLLOVERBIT) == 0:  # Normal event
            time = RolloverTime | (recTime & 0x7FFF) # Accumulate new time increment
        else:
            nbrEvents -= 1  # This isn't a real event, so don't count
            LSBofTC = int(0)
            MSBofTC = int(0)
            LSBofTC |= (recTime & 0x7FFF) << 15  # Mask off the rollover bit and push up to the MSB
            MSBofTC |= recEvent << 30  # During rollover, recEvent has time info instead of event #
            RolloverTime = MSBofTC | LSBofTC
            # goto next event
            continue

 #       print(f'Event:{recEvent} at {time * conv} (uS)')
        fn.write(f'{round(time*conv, 1)},{recEvent}\n')
        time_acc += recTime & 0x7fff
#        print(f'time_acc = {time_acc}')
        time = 0
    return nbrEvents    # Indicate the number of events processed

now = datetime.now()
datestr = now.strftime('%d-%m-%Y')
timestr = now.strftime('%H%M')


config = configparser.ConfigParser()
config.read('listmode.cfg')
lynx_ip = config['LYNX']['Ip']
lynx_user = config['LYNX']['User']
lynx_pw = config['LYNX']['Pw']
det_voltage = config['DETECTOR']['Hv']
acq_time = config['DETECTOR']['Time_Limit']
file_pre = config['DATA']['File_Pre']
file_post = config['DATA']['File_Post']
file_chunk = config['DATA']['File_Chunk']
fnumber = 0
path = f'./{datestr}'
if not os.path.isdir(path):
    os.mkdir(path)
fname = f'./{datestr}/{file_pre}_{timestr}_{fnumber}.{file_post}'
if os.path.isfile(fname):
    print(f'ERROR: file "{fname}" already exists')
    exit(-1)
f = open(fname, 'w')
f.write('time(us),event\n')
file_events = 0

try:   
    # Setup the Python env
    Utilities.setup()
    
    # import the device device proxy and other resources
    from DeviceFactory import *
    from ParameterCodes import *
    from CommandCodes import *
    from ParameterTypes import *
    from ListData import *

    lynx_input = 1   # Memory bank 1 (MCA)
    
    # Create the interface
    device = DeviceFactory.createInstance(DeviceFactory.DeviceInterface.IDevice)
        
    # Open a connection to the device
    device.open("", lynx_ip)
    
    # Display the name of the device
    print("You are connected to: %s"%device.getParameter(ParameterCodes.Network_MachineName, 0))

    # Gain ownership
    device.lock(lynx_user, lynx_pw, lynx_input)

    # Stop any running acquisition
    device.control(CommandCodes.Stop, lynx_input)
    device.control(CommandCodes.Abort, lynx_input)

    # Set HV magnitude
    device.setParameter(ParameterCodes.Input_Voltage, det_voltage, lynx_input)

    # Turn on HV
    device.setParameter(ParameterCodes.Input_VoltageStatus, True, lynx_input)
    while (device.getParameter(ParameterCodes.Input_VoltageRamping, lynx_input) is True):
        print("HVPS is ramping...")
        time.sleep(.2)

    # Set the acquisition mode
    acq_mode = 5 # Tlist type
    device.setParameter(ParameterCodes.Input_Mode, acq_mode, lynx_input)

    # Disable external sync
    device.setParameter(ParameterCodes.Input_ExternalSyncStatus, 0, lynx_input)
    
    # Setup run time in real mode
    device.setParameter(ParameterCodes.Preset_Real, acq_time, lynx_input)
        
    # Clear data and time
    device.control(CommandCodes.Clear, lynx_input)
    
    # Set the current memory group
    group = 1
    device.setParameter(ParameterCodes.Input_CurrentGroup, group, lynx_input)
    
    # Start the acquisition
    device.control(CommandCodes.Start, lynx_input)

    iteration = 0
    total_events = 0
    # Continually poll device and display information while it is acquiring
    while True:
        iteration += 1
        # Get the status (see ./DataTypes/ParameterTypes.py for enumerations
        status = device.getParameter(ParameterCodes.Input_Status, lynx_input)
        fault = device.getParameter(ParameterCodes.Input_Fault, lynx_input)
   #     print(f'status={status}; fault={fault}')
        # Get the list data
        print(f'Iteration # {iteration}')
        listB = device.getListData(lynx_input)
    #    print(f'Printing info for list state: {listB}')
    #    print(f'Start time (uS): {listB.getStartTime()}')
    #    print(f'Live time (uS): {listB.getLiveTime()}')
    #    print(f'Real time (uS): {listB.getRealTime()}')
    #    print(f'Timebase (nS?): {listB.getTimebase()}')
    #    print(f'Flags: {listB.getFlags()}')

        events_processed = outputTlist(listB, listB.getTimebase(), False, f)
        file_events += events_processed
        total_events += events_processed

        if (file_events > float(file_chunk)) & (float(file_chunk) != -1):   # Time to start a new file
            print(f'Starting new file after writing {file_events} events')
            f.write(f'Total events processed: {file_events}')
            file_events = 0
            fnumber += 1
            f.close()
            fname = f'./{datestr}/{file_pre}_{timestr}_{fnumber}.{file_post}'
            f = open(fname, 'w')
            f.write('time(us),event\n')

        if ((0 == (StatusBits.Busy & status)) and (0 == (StatusBits.Waiting & status))):
            f.write(f'Total events processed: {file_events}')
            f.close()
            break
    print(f'Acquisition complete : total events = {total_events}')

    ## [[e.getTime(), e.getEvent()] for e in mylist._TlistData__events]


except Exception as e:
    # Handle any exceptions
    Utilities.dumpException(e)
