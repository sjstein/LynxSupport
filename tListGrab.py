
import anlLynxUtilities as Utilities
import time
import configparser


RolloverTime=int(0)                #This needs to be clears after a start command.
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

    global RolloverTime
    if (clear): RolloverTime = int(0)

    recTime = 0
    recEvent = 0
    Time = int(0)
    conv = float(timeBase)
    conv /= 1000  # Convert to uS

    for event in td.getEvents():
        recTime = event.getTime()
        recEvent = event.getEvent()

        if (0 == (recTime & ROLLOVERBIT)): # Normal event
            Time = RolloverTime | (recTime & 0x7FFF) # Accumulate new time increment
        else:
            print(f'Rolled over. Entering with recTime ({recTime}) giving Time ({Time})')
            LSBofTC = int(0)
            MSBofTC = int(0)
            LSBofTC |= (recTime & 0x7FFF) << 15  # Mask off the rollover bit and push up to the MSB
            MSBofTC |= recEvent << 30  # During rollover, recEvent has time info instead of event #
            if(MSBofTC != 0):
                print('Whoa! An actual MSB event!!')

            RolloverTime = MSBofTC | LSBofTC

            # goto next event
            continue
        print(f'Event:{recEvent} at {Time * conv} (uS)')
        fn.write(f'{Time*conv},{recEvent}\n')
        Time = 0


f = open('events.csv', 'w+')
f.write('time(us),event\n')

config = configparser.ConfigParser()
config.read('listmode.cfg')
lynx_ip = config['LYNX']['Ip']
print(f'found ip# {lynx_ip} of type {type(lynx_ip)}')
lynx_user = config['LYNX']['User']
lynx_pw = config['LYNX']['Pw']
det_voltage = config['DETECTOR']['Hv']




try:   
    #Setup the Python env
    Utilities.setup()
    
    #import the device device proxy and other resources
    from DeviceFactory import *
    from ParameterCodes import *
    from CommandCodes import *
    from ParameterTypes import *
    from ListData import *


    #Working with input 1
    input = 1
    
    #Create the interface
    device = DeviceFactory.createInstance(DeviceFactory.DeviceInterface.IDevice)
        
    #Open a connection to the device
    device.open("", lynx_ip)
    
    #Display the name of the device
    print("You are connected to: %s"%device.getParameter(ParameterCodes.Network_MachineName, 0))

    #Gain ownership

    device.lock(lynx_user, lynx_pw, input)

    #Stop any running acquisition
    device.control(CommandCodes.Stop, input)
    device.control(CommandCodes.Abort, input)

    #Setup the HVPS
    #Utilities.setupHVPS(device)

    HV_Value = 650
    # Set HV magnitude
    device.setParameter(ParameterCodes.Input_Voltage, HV_Value, input)
    # Turn on HV
    device.setParameter(ParameterCodes.Input_VoltageStatus, True, input)
    while (device.getParameter(ParameterCodes.Input_VoltageRamping, input) is True):
        print("HVPS is ramping...")
        time.sleep(.2)

    #Set the acquisition mode
    acq_mode = 5 # Tlist type
    device.setParameter(ParameterCodes.Input_Mode, acq_mode, input)

    #Disable external sync
    device.setParameter(ParameterCodes.Input_ExternalSyncStatus, 0, input)
    
    #Setup run time in real mode
    run_time = 60 # time in seconds to acquire
    device.setParameter(ParameterCodes.Preset_Real, run_time, input)
        
    #Clear data and time
    device.control(CommandCodes.Clear, input)
    
    #Set the current memory group    
    group=1
    device.setParameter(ParameterCodes.Input_CurrentGroup, group, input)
    
    #Start the acquisition
    device.control(CommandCodes.Start, input)

    #Continue to poll device and display information while it is acquiring

    while True:
        #Get the status
        status = device.getParameter(ParameterCodes.Input_Status, input)
        print(f'status={status}')
        #Get the list data
        listB = device.getListData(input)
        print(f'current list state: {listB}')
       # print("Start time: %s; Live time (uS): %d; Real time (uS): %d; Timebase (nS): %d; Flags: %d"%(listB.getStartTime(), listB.getLiveTime(), listB.getRealTime(), listB.getTimebase(), listB.getFlags()))
        
        #See which data was received and present it
        #if (isinstance(listB, ListData)):
        #    for event in listB.getEvents():
        #        print("Event: %d"%event)
        #else:
        outputTlist(listB, listB.getTimebase(), False, f)
        
        if ((0 == (StatusBits.Busy & status)) and (0 == (StatusBits.Waiting & status))):
            break
    print("Program complete")

    ## [[e.getTime(), e.getEvent()] for e in mylist._TlistData__events]


except Exception as e:
    #Handle any exceptions
    Utilities.dumpException(e)
