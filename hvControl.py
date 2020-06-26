import anlLynxUtilities as Utilities
import time
import argparse

V_LOW = 0
V_HIGH = 1000

class IntRange:
    """
    Class used to validate that a CL argument (int type) is within
    [min,max] range. Utilized with 'type' parameter of add_argument.
    e.g.    argparse.add_argument('...',type=IntRange,...)
    """

    def __init__(self, imin=None, imax=None):
        self.imin = imin
        self.imax = imax

    def __call__(self, arg):
        try:
            value = int(arg)
        except ValueError:
            raise self.exception()
        if (self.imin is not None and value < self.imin) or (self.imax is not None and value > self.imax):
            raise self.exception()
        return value

    def exception(self):
        if self.imin is not None and self.imax is not None:
            return argparse.ArgumentTypeError(f'Must be an integer in the range [{self.imin}, {self.imax}]')
        elif self.imin is not None:
            return argparse.ArgumentTypeError(f'Must be an integer >= {self.imin}')
        elif self.imax is not None:
            return argparse.ArgumentTypeError(f'Must be an integer <= {self.imax}')
        else:
            return argparse.ArgumentTypeError('Must be an integer')



parser = argparse.ArgumentParser(description='Program to turn on/off HV supply of Lynx', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('lynxIP', help='IP Number of Lynx.')
parser.add_argument('-s', '--status', help='Return status of HV (ON/OFF)', action='store_true')
parser.add_argument('-o', '--on', help='Turn HV supply ON', action='store_true')
parser.add_argument('-f', '--off', help='Turn HV supply OFF', action='store_true')
parser.add_argument('-p', '--polarity', help='HV Polarity [(P)ositive or (N)egative]')
parser.add_argument('-v', '--voltage', help=f'HV Voltage value ({V_LOW},{V_HIGH})',
                    type=IntRange(V_LOW, V_HIGH))

# Read arguments passed on command line
args = parser.parse_args()

# Parse command line arguments
lynxIP = args.lynxIP  # Server IP  - not optional

try:   
    #Setup the Python env
    Utilities.setup()
    
    #import the device device proxy and other resources
    from DeviceFactory import *
    from ParameterCodes import *
    from CommandCodes import *
    from ParameterTypes import *
    from ListData import *

    if args.status == True:  # Requesting status
        status = True
        print(f'Status function not implemented at this point')
        exit()


    #Working with input 1
    input = 1
    
    #Create the interface
    device = DeviceFactory.createInstance(DeviceFactory.DeviceInterface.IDevice)
        
    #Open a connection to the device
    device.open("", lynxIP)
    
    #Display the name of the device
    print("You are connected to: %s"%device.getParameter(ParameterCodes.Network_MachineName, 0))

    #Gain ownership

    device.lock("Administrator", "Password", input)

    #Stop any running acquisition
    device.control(CommandCodes.Stop, input)
    device.control(CommandCodes.Abort, input)

    #Setup the HVPS
    #Utilities.setupHVPS(device)

    # HV_Value = 650
    if args.voltage is not None:
        print(f'Setting HV magnitude to {args.voltage}V')
        device.setParameter(ParameterCodes.Input_Voltage, args.voltage, input)
        exit()

    # Set HV magnitude
   # device.setParameter(ParameterCodes.Input_Voltage, HV_Value, input)
    if args.on == True:
        print(f'Turning HV supply ON')
        device.setParameter(ParameterCodes.Input_VoltageStatus, True, input)
        exit()

    if args.off == True:
        print(f'Turning HV supply OFF')
        device.setParameter(ParameterCodes.Input_VoltageStatus, False, input)
        exit()

except Exception as e:
    #Handle any exceptions
    Utilities.dumpException(e)