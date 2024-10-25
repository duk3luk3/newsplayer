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
import tkinter as tk
from tkinter import ttk
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

# ICOM control class. These objects control radio functions. One of these objects
# is created for each function of the radio you wish to control.
# Parameters:
#   parent = parent window, root is called from main
#   name = label name used for control
#   type = LineEdit for numeric parameter display and entry. ComboBox for
#          selection from a list of options
#   cmd = Tuple that contains the radio command for parameter update
#   pool = Tuple that contains the command to read the parameter from the radio
#   range = Tuple that contains the conversion from the radio's raw data to displayed
#           units. For LineEdit this contains 4 values, for eample a 0 to 255 radio data
#           range converted to 0 to 100 is (0,255,0,100). For ComboBox the tuple contains
#           a list of values from the radio followed by the display values, for example
#           (0,1,"Off","On")
#   comm =  object that contains the sendmessage function for the radio, in this implementation
#           icom
#   x,y = Position of this object on the parent window
# Methods
#   Update()
#   Clear()
#   SetVal(message)
class Control:
    def __init__(self, parent, name, type, cmd, poll, range, comm, x, y):
        self.master = parent
        self.name = name
        self.cp = comm
        self.x=x
        self.y=y
        self.range = range
        self.cmd = cmd
        self.poll = poll
        self.type = type
        self.index = 0
        self.entVal = None
        self.comboBox = None
        self.chkBox = None
        self.callBackSendMessage = None
        # get background color from parent if avalible
        try: bg = self.master.cget('bg')
        except: bg ="gray92"
        if self.type == 'LineEdit':
            self.frame = tk.Frame(self.master, bg=bg)
            self.frame.place(x=x, y=y, width=170, height=25)
            self.lblName = tk.Label(self.frame, text=self.name, bg=bg, justify=tk.LEFT)
            self.lblName.place(x=0, y=0)
            self.entVal = tk.Entry(self.frame, width=9, bd=0, relief=tk.FLAT)
            self.entVal.place(x=75, y=0)
            self.entVal.bind("<Return>", self.EntryChange)
            self.entVal.bind("<FocusOut>", self.EntryChange)
        elif self.type == 'ComboBox':
            self.frame = tk.Frame(self.master, bg=bg)
            self.frame.place(x=x, y=y, width=200, height=25)
            self.lblName = tk.Label(self.frame, text=self.name, bg=bg)
            self.lblName.place(x=0, y=0)
            self.comboBox = ttk.Combobox(self.frame, width=8)
            self.comboBox.place(x=75, y=0)
            self.comboBox.bind('<<ComboboxSelected>>', self.EntryChange)
            self.comboBox['values'] = self.range[int(len(self.range)/2):]
    def Clear(self):
        if self.type == 'LineEdit':
            self.entVal.delete(0, 'end')
        if self.type == 'ComboBox':
            self.comboBox.set("")
    def EntryChange(self, event):
        if self.cp == None: return
        if self.type == 'LineEdit':
            i = self.entVal.get()
            i = int(self.Scale(i,self.range[2:4],self.range[0:2]) + 0.5)
            self.cp.sendMessage(self.cmd + int2BCD(i))
        if self.type == 'ComboBox':
            i = self.range.index(self.comboBox.get()) - int(len(self.range)/2)
            if(self.callBackSendMessage != None): self.callBackSendMessage(self.cmd + tuple((self.range[i],)))
            else: self.cp.sendMessage(self.cmd + tuple((self.range[i],)))
    def Scale(self, Xvalue, Xrange, Yrange):
        if(int(Xvalue) <= int(Xrange[0])): return int(Yrange[0])
        if(int(Xvalue) >= int(Xrange[1])): return int(Yrange[1])
        return float((float(Xvalue) - float(Xrange[0]))/float((Xrange[1]) - float(Xrange[0])) * (float(Yrange[1]) - float(Yrange[0])) + float(Yrange[0]))
    def update(self):
        if self.type == 'LineEdit':
            if(type(self.poll) == tuple):
                self.cp.sendMessage(self.poll)
        if self.type == 'ComboBox':
            if(type(self.poll) == tuple):
                self.cp.sendMessage(self.poll)
    def setVal(self, message):
        if(type(self.poll) == tuple):
            if(self.poll == tuple(message[4:4+len(self.poll)])):
                if self.type == 'LineEdit':
                    i = BCD2int(tuple(message[4+len(self.poll):message.index(self.cp.endOfMess)]))
                    i = int(self.Scale(i, self.range[0:2], self.range[2:4]) + 0.5)
                    if(self.entVal.focus_get() != self.entVal):
                        self.entVal.delete(0, 'end')
                        self.entVal.insert(0,i)
                    return
                if self.type == 'ComboBox':
                    #i = message[4+len(self.poll):message.index(self.cp.endOfMess)]
                    i = message[4 + len(self.poll) + self.index:4 + len(self.poll)+1+self.index]
                    i = self.range.index(int.from_bytes(i,"big"))
                    self.comboBox.current(i)


# This class supports the RS232 communications with methods to open/close the port
#  as well as send messages to the ACOM
class Comm:
    def __init__(self, parent):
        self.master = parent
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
        while self.cp.isOpen():
            self.master().update()
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
    def __init__(self, parent, comm):
        self.master = parent
        self.cp = comm
        self.preamble = 0xFE
        self.transAddr = 0x98
        self.controlAddr = 0x01
        self.endOfMess = 0xFD
        self.commCAT = ""
        self.commPT = ""
        self.ICOMmessage = None
    def sendMessage(self, message):
        self.ICOMmessage = tuple((self.preamble,self.preamble,self.transAddr,self.controlAddr))
        self.ICOMmessage += message
        self.ICOMmessage += tuple((self.endOfMess,))
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
    def CATportSelected(event):
        commCAT.port = CATportsel.get()
    def PTportSelected(event):
        commPT.port = PTportsel.get()
    def connectPressed():
        # Save settings
        icom.commCAT = commCAT.port
        icom.commPT = commPT.port
        icom.save()
        # open comm post and start echo process
        commCAT.open()
        commPT.open()
        echo()
        root.geometry('360x180')
    def echo():
        # Read all avalible chars and echo
        num = commCAT.avaliable()
        if(num > 0):
            message = commCAT.getMessage(num)
            commPT.sendMessage(message)
            processMessage(message)
        num = commPT.avaliable()
        if (num > 0):
            message = commPT.getMessage(num)
            commCAT.sendMessage(message)
        root.after(10, echo)
    def powerOnPressed():
        message = tuple((icom.preamble,))
        for i in range(150):
           message += tuple((icom.preamble,))
        message += icom.transAddr,icom.controlAddr, 0x18, 0x01, icom.endOfMess
        commCAT.sendMessage(message)
    def powerOffPressed():
        icom.sendMessage((0x18,0x00))
        for x in c:
            x.Clear()
        Status.set("Power off")
    def poll():
        if(commCAT.isOpen == False): Status.set("Not connected")
        global cindex
        c[cindex].update()
        cindex += 1
        if(cindex >= len(c)): cindex = 0;
        if(cindex == 0): root.after(2000, poll)
        else: root.after(50, poll)
    def filterEntryChange(message):
        i = c[bandI].range.index(c[bandI].comboBox.get()) - int(len(c[bandI].range) / 2)
        i = message[0], i, message[1]
        icom.sendMessage(i)

    #System setup
    root = tk.Tk()
    root.geometry('360x180')
    root.title("iCOM IC-7610, Version 1.0")
    # ICOM radio CAT port
    commCAT = Comm(root)
    # Pass through port to allow another app to use the CAT port with a vertical comm port app
    commPT = Comm(root)

    lblLabel = tk.Label(root, text="CAT port", anchor="w")
    lblLabel.place(x=10, y=180, width=100, height=15)
    CATportsel = ttk.Combobox(root, width=20)
    CATportsel['values'] = [""] + commCAT.findPorts()
    CATportsel.bind("<<ComboboxSelected>>", CATportSelected)
    CATportsel.set(commCAT.port)
    CATportsel.place(x=110, y=180, width=200)

    lblLabel = tk.Label(root, text="Pass thru port", anchor="w")
    lblLabel.place(x=10, y=205, width=100, height=15)
    PTportsel = ttk.Combobox(root, width=20)
    PTportsel['values'] = [""] + commPT.findPorts()
    PTportsel.bind("<<ComboboxSelected>>", PTportSelected)
    PTportsel.set(commPT.port)
    PTportsel.place(x=110, y=205, width=200)

    btAccept = ttk.Button(root, text="Connect", command=connectPressed)
    btAccept.place(x=10, y=230, width=100)
	
	# Create the application objects and open ports
    icom = ICOM(root,commCAT)
    icom.load()
    commCAT.port = icom.commCAT
    commPT.port = icom.commPT
    commCAT.open()
    commPT.open()

	# List of all radion controls
    c = []
	# Create all the radio controls
    c.append(Control(root, "Band", "ComboBox", (0x06,), (0x04,), (0,1,2,3,4,5,7,8,0x12,0x17,"LSB","USB","AM","CW","RTTY","FM","CW-R","RTTY-R","PSK","PSK=R"), icom, 10, 45))
    bandI = len(c) - 1
    c.append(Control(root, "Filter", "ComboBox", (0x06,), (0x04,), (1,2,3,"1","2","3"), icom, 10, 70))
    c[len(c)-1].index = 1
    c[len(c) - 1].callBackSendMessage = filterEntryChange
    c.append(Control(root, "BW", "LineEdit", (0x1A,0x03), (0x1A,0x03), (0,9,50,500), icom, 10, 95))
    c.append(Control(root, "Preamp", "ComboBox", (0x16,0x02), (0x16,0x02), (0,1,2,"Off","1","2"), icom, 10, 120))
    c.append(Control(root, "RX Ant", "ComboBox", (0x12,0x00), (0x12,), (0,1,"Off","On"), icom, 10, 145))
    c[len(c) - 1].index = 1
    c.append(Control(root, "Power",   "LineEdit", (0x14, 0x0A), (0x14, 0x0A), (0, 255, 0, 100), icom, 180, 45))
    c.append(Control(root, "RF gain", "LineEdit", (0x14, 0x02), (0x14, 0x02), (0, 255, 0, 100), icom, 180, 70))
    c.append(Control(root, "BK-IN", "ComboBox", (0x16, 0x47), (0x16, 0x47), (0,1,2,"Off","Semi","Full"), icom, 180, 95))
    c.append(Control(root, "APF", "ComboBox", (0x16, 0x32), (0x16, 0x32), (0,1,2,3,"Off","Wide","Mid","Nar"), icom, 180, 120))
	# Power on and off buttons and status display
    btPwrOn = ttk.Button(root, text="Power on", command=powerOnPressed)
    btPwrOn.place(x=10, y=10, width=100)
    btPwrOff = ttk.Button(root, text="Power off", command=powerOffPressed)
    btPwrOff.place(x=120, y=10, width=100)
    Status = tk.StringVar()
    Status.set("")
    lblStatus = tk.Label(root, textvariable=Status, anchor="w")
    lblStatus.place(x=230, y=15, width=100, height=15)

    poll()	# This is the polling loop for this app, runs very 2 secs
    echo()	# This is the passthrough processing funncion, echo all CAT traffic
	# Paint the UI and lets go!
    root.mainloop()

if __name__ == "__main__":
    main()
