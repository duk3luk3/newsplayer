import ICOM
import time

commCAT = ICOM.Comm()
commCAT.findPorts()
commCAT.port = '/dev/ttyUSB0'
icom = ICOM.ICOM(commCAT)
icom.transAddr=0xA2
icom.controlAddr=0xE0
icom.cp.baudrate = 19200
icom.cp.open()
print(f'open: {icom.cp.isOpen}')
icom.sendMessage((0x18,0x00))
time.sleep(3)
commCAT.open()
message = (icom.preamble,)*150 + (icom.transAddr, icom.controlAddr, 0x18, 0x01, icom.endOfMess)
print(message)
icom.cp.sendMessage(message)
