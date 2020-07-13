import sys
import socket
import os
import platform

if sys.version_info >= (3, 0):
    long = int
    raw_input = input

def determineDeviceType(dev):
    """
    Description:
        This method will attempt to determine the type of MCA
    Arguments:
        none
    Exception:
        Exception
    Return:
        1 == Lynx, 3 == Osprey, 5 == DSA-LX
    """
    from ParameterCodes import ParameterCodes
    dtype = dev.getParameter(ParameterCodes.UPnP_DeviceType, 0)
    token = dtype.split(':')
    return int(token[4])

LYNX_MCA_TYPE = 1
OSPREY_MCA_TYPE = 3
DSALX_MCA_TYPE = 5

def setupHVPS(dev):
    import time
    from ParameterCodes import ParameterCodes
    
    input = 1
    devType = determineDeviceType(dev)
    if OSPREY_MCA_TYPE != devType:
        if (1 == getInt("Turn HV ON: (0=NO or 1=Yes):", 0, 1)):
            # Set the value
            HV_Value = getFloat("Enter HV Value: ", 0, 800)
            dev.setParameter(ParameterCodes.Input_Voltage, HV_Value, input)

            #Turn on HV
            dev.setParameter(ParameterCodes.Input_VoltageStatus, True, input)
            
            #Wait till ramping is complete
            while(dev.getParameter(ParameterCodes.Input_VoltageRamping, input) is True):
                print ("HVPS is ramping...")
                time.sleep(.2)
    else:
        # Start of HV Section**************************************************************
        #Turn on HV
        Stabilized_Probe_Bussy = 0x00080000
        Stabilized_Probe_OK = 0x00100000
        
        if (1 == getInt("Stabilized Probe Connected? (0=NO or 1=Yes):", 0, 1)):          #work on the Stabilized Probe
            dev_probe_type = dev.getParameter(ParameterCodes.Input_Status, input)
            if((dev_probe_type & Stabilized_Probe_OK) != Stabilized_Probe_OK):
                print ("Stabilized Probe is not detected!")
                #return
            while ((dev_probe_type & Stabilized_Probe_Bussy) == Stabilized_Probe_Bussy):
                dev_probe_type = dev.getParameter(ParameterCodes.Input_Status, input)
                print ("Waiting for Stabilized Probe...")
                time.sleep(1)
        else:                               #work on the non-Stabilized Probe
            if (1 == getInt("Turn HV ON: (0=NO or 1=Yes):", 0, 1)):
                dev_probe_type = dev.getParameter(ParameterCodes.Input_Status, input)
                if((dev_probe_type & Stabilized_Probe_OK) != Stabilized_Probe_OK):
                    HV_Value = getFloat("Enter HV Value: ", 0, 800)
                    dev.setParameter(ParameterCodes.Input_Voltage, HV_Value, input)
                    dev.setParameter(ParameterCodes.Input_VoltageStatus, True, input)
                    #Wait till ramping is complete
                    while(dev.getParameter(ParameterCodes.Input_VoltageRamping, input) is True):
                        print ("HVPS is ramping...")
                        time.sleep(.2)
                else:
                    print ("Stabilized Probe detected, HV Ignored!")
        # End of HV Section*****************************************************************
    
def setup():    
    """
    Lazy function to add DataTypes subdir to search path for modules
    """

    #  toolkitPath = os.getcwd().replace(os.path.sep+"Examples", os.path.sep+"DataTypes")
    sys.path.append(os.getcwd()+'\\DataTypes')
    
def readLine(txt):
    """
    Description:
        This method will print the text that is supplied
        to the Python console and wait for the user to
        enter a response.  The purpose is to hide the 
        differences in the implementation of raw_input
        between different OS's.  Yes, there are subtle
        difference.
    Arguments:
        txt  (in, string) The text to display
    Return: 
        (string)    The entered value
    """

    val = raw_input(txt)
    return val.replace("\r", "")

def getMcaAddress():
    """
    Description:
        This method will request the IP address from the 
        user via the Python console.
    Arguments:
        none
    Return:
        (String) The value
    """
    error = True
    while error:
        val = readLine("Enter the IP address of your MCA: (a.b.c.d): ")
        try:
            #Use gethostbyname() to verify the IP address is valid
            socket.gethostbyname(val)
            return val
        except:
            pass
def getSpectralMode():
    """
    Description:
        This method will return the spectral acquisition mode
        that has been entered by the Python console
    Arguments:
        none
    Return: 
        (int) The value
    """
    error=True
    while error:
        try:
            val = readLine("Select the acquisition mode: (0=Pha, 1=Dlfc)")
            val = int(val)
            if (0 == val):
                return val      #Pha
            elif(1 == val):
                return 3        #Dlfc
        except: 
            pass
def getListMode():
    """
    Description:
        This method will return the list acquisition mode
        that has been entered by the Python console
    Arguments:
        none
    Return: 
        (int) The value
    """
    error=True
    while error:
        try:
            val = readLine("Select the acquisition mode: (0=List, 1=Tlist)")
            val = int(val)
            if (0 == val):
                return 4 #List
            elif(1 == val):
                return 5 #Tlist
        except: 
            pass
def getPresetMode():
    """
    Description:
        This method will return the preset mode
        that has been entered by the Python console
    Arguments:
        none
    Return: 
        (int) The value
    """
    error=True
    while error:
        try:
            val = readLine("Select the preset mode: (0=None, 1=Real, 2=Live)")
            val = int(val)
            if (0 == val):
                return 0 #PresetModes.PresetNone
            elif(1 == val):
                return 2 #PresetModes.PresetRealTime
            elif(2 == val):
                return 1 #PresetModes.PresetLiveTime
        except: 
            pass
def getMCSPresetMode():
    """
    Description:
        This method will return the MCS preset mode
        that has been entered by the Python console
    Arguments:
        none
    Return: 
        (int) The value
    """
    error=True
    while error:
        try:
            val = readLine("Select the acquisition mode: (0=None, 1=Sweeps)")
            val = int(val)
            if (0 == val):
                return 0 #PresetModes.PresetNone
            elif(1 == val):
                return 4 #PresetModes.PresetSweeps            
        except: 
            pass        
def getFloat(text, min, max):
    """
    Description:
        This method will return a floating point value
        that has been entered by the Python console
    Arguments:
        text    (in, string) The text description
        min     (in, float) The min value
        max     (in, float) The max value
    Return: 
        (float) The value
    """
    val=0.0
    error = True
    while error:
        try:
            val = readLine(text)
            val = float(val)
            if ((val >= min) and (val <= max)):
                return val
        except:
            pass
def getInt(text, min, max):
    """
    Description:
        This method will return an integer value
        that has been entered by the Python console
    Arguments:
        text    (in, string) The text description
        min     (in, int) The min value
        max     (in, int) The max value
    Return: 
        (int) The value
    """
    val=0
    error = True
    while error:
        try:
            val = readLine(text)
            val = int(val)
            if ((val >= min) and (val <= max)):
                return val
        except:
            pass
def dumpException(ex):
    """
    Description:
        This method will print out the exception
        information
    Arguments:
        ex    (in, Exception) The exception
    Return: 
        none
    """
    print("Exception caught.  Details: %s"%str(ex))

RolloverTime=long(0)                #This needs to be clears after a start command.
ROLLOVERBIT=0x00008000              #The rollover bit

def reconstructAndOutputTlistData(td, timeBase, clear):
    """
    Description:
        This method will reconstruct the time events for time
        stamped list mode before displaying on output
    Arguments:
        td (in, TlistData).  The time stamped list data buffer.
        timeBase (in, int).  The time base (nS)
        clear (in, bool).    Resets the global time counter
    Return:
        none
    """
    global RolloverTime
    if (clear): RolloverTime = long(0)
    
    recTime=0
    recEvent=0
    Time=long(0)  
    conv = float(timeBase)
    conv /= 1000 #Convert to ms
    
    for event in td.getEvents():          
        recTime=event.getTime()
        recEvent=event.getEvent()
        
        if (0 == (recTime&ROLLOVERBIT)): 
            Time = RolloverTime | (recTime & 0x7FFF)
        else:
            LSBofTC = int(0)
            MSBofTC = int(0)
            LSBofTC |= (recTime & 0x7FFF) << 15
            MSBofTC |= recEvent << 30
            RolloverTime = MSBofTC | LSBofTC 
            
            #goto next event
            continue
        print("Event: " + str(event.getEvent()) + "; Time (uS): " + str(Time*conv))
        Time=0
        
def isLocalAddressAccessible():
    """
    Description:
        This method will determine whether the network address
        of the local network adapter can be obtained.
    Arguments:
        none
    Return: 
        (bool)    True indicates that the network address can be obtained
    """
    try:
        if ("Linux" == platform.system()):
            remote = ("www.python.org", 80)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect( remote )
            ip, localport = s.getsockname()
            s.close()
        else:
            return True
    except:
        return False
    return True
    