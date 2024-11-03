# ICOM 7610 control app
#
#   This is a very minimulistic ICOM IC-7610 control application. This app passes the CAT
#   control data through to a second comm port for use by another application, in my
#   case N1MM+. This app allows control of the following funstions:
#   - On/off of the radio
#   - Power output
#   - RF gain
#   - Break-in control
#   - Mode
#   - Filter
#   - APF
#   - RX antenna
#   Frequency control is done using the spectrum display in N1MM+.
#   The comm ports can be selected by pulling down the bottom of the app's dialog box
#   to expose the comm select boxes. The comm parameters are fixed and the baud rate
#   is set to 115,200 baud. This spped is required for the spectrum display.
#
#   This app could be expanded to offer complete control of the radio but I have found
#   N1MM+'s spectrum control ideal for tuning and only needed a few other options to
#   fully opperate.
#
#   This app is part of my remote operation system for my station.
#
#   Written in python using the pycharm IDE and Tkinter UI.
#
#   Gordon Anderson, KG7YU
#   gaa@owt.com
#   509.628.6851
#
# system imports
from __future__ import absolute_import
import os
import sys
import time
import serial

# Converts integer value to BCD and returns in a tuple
def int2BCD(value):
    message = None
    while(True):
        b = (((int(int(value) / 10) % 10) << 4) | (int(int(value)) % 10))
        if(message == None): message = tuple((b,))
        else: message = tuple((b,)) + message
        value = int(value/100)
        if(value == 0): break
    return message

# Converts BCM tuple in message and returns integer in value
def BCD2int(message):
    value = 0
    for x in message:
        value *= 100
        value += ((x & 0xf0) >> 4) * 10 + (x & 0x0f)
    return value

# This class supports the RS232 communications with methods to open/close the port
#  as well as send messages to the ACOM
class Comm:
    def __init__(self):
        self.isOpen = False
        self.isError = False
        self.ErrorMessage = ""
        self.statusbar = None
        self.stopbits = 1
        self.bytesize = 8
        self.baudrate = 115200
        self.flowcontrol = "None"
        self.port = ""
        self.parity = 'N'
        self.cp = None
    def open(self):
        if self.port == "": return
        xonxoff = False
        rtscts = False
        if self.flowcontrol == "RTS/CTS": rtscts = True
        if self.flowcontrol == "XON/XOFF": xonxoff = True
        try:
            self.cp = serial.Serial(self.port,self.baudrate,self.bytesize,self.parity,self.stopbits,None,xonxoff,rtscts,None,False,None,None)
            self.isError = False
            self.isOpen = True
            self.cp.rts = True
            self.cp.dtr = True
            self.ErrorMessage = "Connected: " + self.port
        except Exception as e:
            self.isError = True
            self.isOpen = False
            self.ErrorMessage = e
    def close(self):
        if self.cp == None:
            self.ErrorMessage = 'Nothing to disconnect!'
            return
        if self.cp.isOpen():
            self.cp.close()
        else:
            self.ErrorMessage = self.port + ' all ready disconnected!'
            return
        self.isOpen = False
        self.ErrorMessage = 'Disconnected: ' + self.port
    def enable(self):
        if self.cp.isOpen():
            self.cp.rts = True
            self.cp.dtr = True
    def disable(self):
        if self.cp.isOpen():
            self.cp.rts = False
            self.cp.dtr = False
    def findPorts(self):
        from serial.tools.list_ports import comports
        ports = []
        for n, (port, desc, hwid) in enumerate(sorted(comports()), 1):
            ports.append(port)
        return ports
    def avaliable(self):
        if (self.isOpen == False): return 0
        return self.cp.inWaiting()
    def getByte(self):
        if (self.isOpen == False): return 0
        if (self.cp.inWaiting() <= 0): return 0
        try:
            return self.cp.read(1)
        except Exception as e:
            self.isError = True
            self.ErrorMessage = e
    def getMessage(self, num):
        if (self.isOpen == False): return 0
        if (self.cp.inWaiting() <= 0): return 0
        try:
            return self.cp.read(num)
        except Exception as e:
            self.isError = True
            self.ErrorMessage = e
            return 0
    def sendMessage(self, message):
        if (self.isOpen == False): return
        try:
            self.cp.flush()
            self.cp.write(message)
            self.isError = False
        except Exception as e:
            self.isError = True
            self.ErrorMessage = e
    def sendString(self, message):
        if(self.isOpen == False): return
        try:
            self.cp.flush()
            self.cp.write(message.encode('utf-8'))
            self.isError = False
        except Exception as e:
            self.isError = True
            self.ErrorMessage = e

class ICOM:
    def __init__(self, comm):
        self.cp = comm
        self.preamble = 0xFE
        self.transAddr = 0x98
        self.controlAddr = 0x01
        self.endOfMess = 0xFD
        self.commCAT = ""
        self.commPT = ""
        self.ICOMmessage = None
    def sendMessage(self, message, numPreamble=2):
        """
        frame and send a CAT control message.
        message is a sequence of bytes to send.
        numPreamble controls how often to repeat the preamble.
        This is 2 for standard messages, in order to power on a rig set it to
        at least 150.
        """
        self.ICOMmessage = (self.preamble,) * numPreamble
        self.ICOMmessage += (self.transAddr,self.controlAddr,)
        self.ICOMmessage += message
        self.ICOMmessage += (self.endOfMess,)
        self.cp.sendMessage(self.ICOMmessage)
    def save(self):
        self.saveSettings(os.path.dirname(sys.executable) + "/ICOM.settings")
    def load(self):
        self.loadSettings(os.path.dirname(sys.executable) + "/ICOM.settings")
    def saveSettings(self, fileName):
        try:
            f = open(fileName, "wt")
            f.write("CATport," + self.commCAT + "\n")
            f.write("PTport," + self.commPT + "\n")
            f.close()
        except Exception as e:
            self.isError = True
            self.ErrorMessage = e
    def loadSettings(self, fileName):
        try:
            f = open(fileName, "rt")
            for x in f:
                y = x.split(",")
                arg = ""
                if len(y) >= 2: arg = y[1].strip()
                if y[0] == "CATport": self.commCAT = arg
                elif y[0] == "PTport": self.commPT = arg
            f.close()
        except Exception as e:
            self.isError = True
            self.ErrorMessage = e


# ICOM main
cindex = 0
def main():

    def processMessage(message):
        try:
            for i in range(message.count(icom.endOfMess)):
                j = message.index(icom.endOfMess)
                if (message[(message[:j+1].index(icom.transAddr) - 1)] == icom.controlAddr):
                    for x in c:
                        x.setVal(message)
                        #print(message)
                        if(message.count(0xFA) != 0): Status.set("Power off")
                        else: Status.set("Power on")
                    return message
                message = message[j+1:]
        except:
            return (0,0)
    def echo():
        # Read all avalible chars and echo
        num = commCAT.avaliable()
        if(num > 0):
            message = commCAT.getMessage(num)
            processMessage(message)

    # ICOM radio CAT port
    commCAT = Comm()

	# Create the application objects and open ports
    icom = ICOM(commCAT)
    icom.load()
    commCAT.port = icom.commCAT
    commPT.port = icom.commPT
    commCAT.open()
    commPT.open()


if __name__ == "__main__":
    main()
