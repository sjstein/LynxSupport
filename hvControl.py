import argparse
import sys
import os

from aspLibs.aspUtilities import IntRange
from aspLibs.aspUtilities import V_HIGH
from aspLibs.aspUtilities import AspLogger

VOLT_LOW = 0
VOLT_HIGH = 1000

datatypespath = '\\DataTypes'  # This is the subdirectory with the Lynx data structure definitions

parser = argparse.ArgumentParser(description='Program to turn on/off HV supply of Lynx',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument('-s', '--status', help='Return status of Lynx HV settings and current value', action='store_true')
parser.add_argument('-o', '--on', help='Turn HV supply ON', action='store_true')
parser.add_argument('-f', '--off', help='Turn HV supply OFF', action='store_true')
parser.add_argument('-p', '--polarity', help='HV Polarity [(P)ositive or (N)egative]', type=str,
                    choices=['P', 'p', 'N', 'n'], default='N')
parser.add_argument('-v', '--voltage', help=f'HV Voltage value ({VOLT_LOW},{VOLT_HIGH})',
                    type=IntRange(VOLT_LOW, VOLT_HIGH))
parser.add_argument('-i', '--input', help='MCA input number. 0, 1, or 2', type=IntRange(0, 2), default=1)

# Read arguments passed on command line
args = parser.parse_args()

# Parse command line arguments
lynxIP = args.lynxIP
log = AspLogger(V_HIGH)  # No real need for verbosity argument in this program, so echo everything

try:
    # Setup the Python env
    sys.path.append(os.getcwd() + datatypespath)  # append DataTypes subdir to system path for Lynx library imports
    from DeviceFactory import DeviceFactory
    from ParameterCodes import ParameterCodes

    mca_input = args.input

    # Instantiate the device object
    device = DeviceFactory.createInstance(DeviceFactory.DeviceInterface.IDevice)

    # Open a connection to the device
    device.open('', lynxIP)

    # Get device name
    dev_name = device.getParameter(ParameterCodes.Network_MachineName, 0)

    # Gain ownership
    # BARF on this hard-coded horror. However this will remain until Canberra responds with a reasonable way
    #  for us to take control as a user instead of always admin
    device.lock('Administrator', 'Password', mca_input)

    if args.voltage is not None:
        log.disp(f'{dev_name}: Setting HV magnitude to {args.voltage}V')
        device.setParameter(ParameterCodes.Input_Voltage, args.voltage, mca_input)
        exit()

    if args.polarity is not None:
        if args.polarity.upper() == 'P':
            log.disp('{dev_name}: Setting HV polarity to POSITIVE')
            device.setParameter(ParameterCodes.Input_VoltagePolarity, False, mca_input)
        else:
            log.disp('{dev_name}: Setting HV polarity to NEGATIVE')
            device.setParameter(ParameterCodes.Input_VoltagePolarity, True, mca_input)

    if args.on:
        log.disp(f'{dev_name}: Turning HV supply ON')
        device.setParameter(ParameterCodes.Input_VoltageStatus, True, mca_input)
        exit()

    if args.off:
        log.disp(f'{dev_name}: Turning HV supply OFF')
        device.setParameter(ParameterCodes.Input_VoltageStatus, False, mca_input)
        exit()

    if args.status:
        hv_set = device.getParameter(ParameterCodes.Input_Voltage, mca_input)
        hv_read = round(device.getParameter(ParameterCodes.Input_VoltageReading, mca_input), 2)
        if device.getParameter(ParameterCodes.Input_VoltagePolarity, mca_input):  # Returns True if negative
            hv_polarity = '-'
        else:
            hv_polarity = '+'
        if device.getParameter(ParameterCodes.Input_VoltageStatus, mca_input):
            hv_status = 'ON'
        else:
            hv_status = 'OFF'
        log.disp(f'{dev_name}: HV Supply is {hv_status} and set to {hv_polarity}{hv_set}, reading back {hv_read}V')
        exit()

except Exception as e:
    # Handle any exceptions
    print(f'Exception caught : {e}')
