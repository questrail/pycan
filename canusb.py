# -*- coding: utf-8 -*-
# Copyright (c) 2013 The pycan developers. All rights reserved.
# Project site: https://github.com/questrail/pycan
# Use of this source code is governed by a MIT-style license that
# can be found in the LICENSE.txt file for the project.
"""LAWICEL CANUSB CAN driver interface

This moduel extends the BaseDriver class from `basedriver.py` to provide an
interface to the LAWICEL AB CANUSB CAN module.

External Python Dependancies:
    * pySerial - tested v2.6
Hardware Requirements:
    * CANUSB (http://www.can232.com)
Driver Requirements:
    * FTDI D2XX Driver / Support
        - See http://www.can232.com/docs/canusb_drinst_d2xx.pdf
"""

# Test dependencies
import time
import unittest
import threading

# Driver dependencies
import re
import Queue
from basedriver import *
import serial

CAN_TX_TIMEOUT = 100 # ms
CAN_RX_TIMEOUT = 100 # ms
COMMAND_TIMEOUT = 1 # seconds
TERMINATORS = ['\r', '\x07']
STD_MSG_HEADERS = ['t', 'T']
REM_MSG_HEADERS = ['r', 'R']

BIT_RATE_CMD = {}
BIT_RATE_CMD['10K'] = 'S0\r'
BIT_RATE_CMD['20K'] = 'S1\r'
BIT_RATE_CMD['50K'] = 'S2\r'
BIT_RATE_CMD['100K'] = 'S3\r'
BIT_RATE_CMD['125K'] = 'S4\r'
BIT_RATE_CMD['250K'] = 'S5\r'
BIT_RATE_CMD['500K'] = 'S6\r'
BIT_RATE_CMD['800K'] = 'S7\r'
BIT_RATE_CMD['1M'] = 'S8\r'

OPEN_CMD = 'O\r'
CLOSE_CMD = 'C\r'
TIME_STAMP_CMD = 'Z1\r'

class CANUSB(BaseDriver):
    def __init__(self, **kwargs):
        # Init the base driver
        super(CANUSB, self).__init__(max_in=500, max_out=500, loopback=False)

        # Open the COM port
        port = kwargs['com_port'] # Throws key error
        baud = kwargs.get('com_baud', 115200)
        self.port = serial.Serial(port=port, baudrate=baud, timeout=.5)
        self.rx_buffer = ''
        self.response = ''

        self.bus_off()

        # Clear out the rx/tx buffers per manual
        for x in range(5):
            self.port.write('\r')

        self.port.flushInput()

        # Turn on the time stamps
        self.__send_command(TIME_STAMP_CMD)

        # Set the default paramters
        self.update_bus_parameters()

        # Add the inbound and outbound processes to the BaseDriver's scheduler
        self.scheduler.add_operation(self.__process_outbound_queue, 0)
        self.scheduler.add_operation(self.__process_inbound_queue, 0)

        # Go on bus
        self.bus_on()

    def bus_on(self):
        return (self.__send_command(OPEN_CMD) == '\r')

    def bus_off(self):
       return (self.__send_command(CLOSE_CMD) == '\r')

    def __send_command(self, cmd, timeout=COMMAND_TIMEOUT):
        # Clear the response buffer
        self.response = ''

        # Send the command
        self.port.write(cmd)

        # Wait for a response
        tic = time.time()
        while (time.time() - tic) < timeout :
            if self.response:
                return self.response
            #time.sleep(.000001)

        return ''

    def update_bus_parameters(self, **kwargs):
        # Default values are setup for a 250k connetion
        br = kwargs.get('bit_rate', '250K')
        br_cmd = BIT_RATE_CMD.get(br, None)
        if br_cmd:
            return (self.__send_command(br_cmd) == '\r')

        return False

    def __process_outbound_queue(self):
        try:
            # Read the Queue - allow the timeout to throttle the thread
            can_msg = self.outbound.get(timeout=QUEUE_DELAY)
        except Queue.Empty:
            # Kick out and wait for the next call from the scheduler
            return

        outbound_msg = ''
        if can_msg.extended:
            id_str = "T%08X" % (can_msg.id)
            ack = 'Z\r'
        else:
            id_str = "t%03X" % (can_msg.id & 0x7FF)
            ack = 'z\r'

        outbound_msg += id_str
        outbound_msg += "%X" % (can_msg.dlc)

        for x in range(can_msg.dlc):
            outbound_msg += "%02X" % (can_msg.payload[x])

        outbound_msg += "\r"

        resp = self.__send_command(outbound_msg)
        #if resp != ack:
        #    print resp

        return (resp == ack)

    def __process_inbound_queue(self):
        # Grab all of the data from the serial port
        try:
            bytes_to_read = self.port.inWaiting()
            if bytes_to_read > 0:
                self.rx_buffer += self.port.read(bytes_to_read)
            else:
                # Read one -- uses the serial port timeout for throttling
                self.rx_buffer += self.port.read()

        except serial.SerialException:
            pass

        msg = ''
        for term in TERMINATORS:
            # Look for the 1st command
            if term in self.rx_buffer:
                idx = self.rx_buffer.find(term) + 1

                if idx:
                    # Get the message and remove it from the buffer
                    msg = self.rx_buffer[:idx]
                    self.rx_buffer = self.rx_buffer[idx:]
                    break

        if msg:
            hdr = msg[0]

            if hdr in STD_MSG_HEADERS:
                if hdr == 'T': # 29 bit message
                    e_id = 9 # ending can_id index
                    ext = True
                else: # hdr == 't' # 11 bit message
                    e_id = 4
                    ext = False
                # Get the CAN ID
                can_id = int(msg[1:e_id], 16)

                # Get the DLC (data length)
                s_dlc = e_id
                e_dlc = s_dlc + 1
                dlc = int(msg[s_dlc:e_dlc])

                # Get the payload
                s_payload = e_dlc
                e_payload = s_payload + dlc*2
                payload = []
                for x in range(s_payload, e_payload ,2):
                    val = int(msg[x:x+2],16)
                    payload.append(val)

                # Get the timestamp (if any)
                timestamp = 0
                if len(msg[e_payload:-1]) == 4:
                    timestamp = int(msg[e_payload+1:-1], 16)

                # Build the message
                new_msg = CANMessage(can_id, dlc, payload, ext, timestamp)

                try: # Push the message into the inbound queue
                    self.inbound.put(new_msg, timeout=QUEUE_DELAY)
                except Queue.Full:
                    # TODO: flag error
                    pass

            elif hdr in REM_MSG_HEADERS:
                pass # Not supported
            else:
                # Unknown type --> assume it's a command response
                self.response = msg

class CANUSBTests(unittest.TestCase):
    KNOWN_ID_ON_BUS = 0x0C010605
    TEST_PORT = '/dev/tty.usbserial-LWVU30AO'
    def setUp(self):
        self.driver = None

    def tearDown(self):
        try:
            self.driver.bus_off()
            self.driver.shutdown()
            time.sleep(2)
        except:
            pass

    def testTransmit(self):
        self.driver = CANUSB(com_port=self.TEST_PORT)
        msg1 = CANMessage(0x123456, 3, [1,2,3], False)
        # Watch the CAN bus to ensure the message was sent
        self.assertTrue(self.driver.send(msg1))

    def testCyclicTransmit(self):
        self.driver = CANUSB(com_port=self.TEST_PORT)
        msg1 = CANMessage(0x18F00503, 8, [0x7D, 0xFF, 0xFF, 0x7D, 0xFF, 0xFF, 0xFF, 0xFF], True)
        msg2 = CANMessage(0x18F00503, 8, [0x7D, 0xFF, 0xFF, 0x7D, 0xFF, 0xFF, 0xFF, 0xFF], False)

        self.assertTrue(self.driver.add_cyclic_message(msg1, .1, "Sample"))
        time.sleep(3) # Watch the CAN bus to ensure the messages are being sent
        self.assertTrue(self.driver.update_cyclic_message(msg2, "Sample"))
        time.sleep(3) # Watch the CAN bus to ensure the messages changed and are being sent
        self.assertTrue(self.driver.update_cyclic_message(msg1, "Sample"))
        time.sleep(3)

    def testGenericReceive(self):
        required_rx_count = 10
        events = []
        for x in range(required_rx_count):
            events.append(threading.Event())
            events[-1].clear()

        self.driver = CANUSB(com_port=self.TEST_PORT)
        print ''

        def gen_handler(msg):
            # Walk down the number of events marking them as
            # each new message is received
            for event in events:
                if not event.isSet():
                    event.set()
                    print msg
                    break;

        self.driver.add_receive_handler(gen_handler)

        for event in events:
            event.wait(1)# wait for at least 1 second for each message

        # Determine how many messages were in fact recorded
        rx_cnt = 0
        for event in events:
            if event.isSet():
                rx_cnt += 1
        self.assertEqual(rx_cnt, required_rx_count,
            msg="Expected %d messages, receved %d messages" % (required_rx_count, rx_cnt))

    def testSpecificReceive(self):
        required_rx_count = 10
        events = []
        for x in range(required_rx_count):
            events.append(threading.Event())
            events[-1].clear()

        self.driver = CANUSB(com_port=self.TEST_PORT)
        print ''

        def msg_handler(msg):
            # Walk down the number of events marking them as
            # each new message is received
            for event in events:
                if not event.isSet():
                    event.set()
                    print msg
                    break;

        # This test relies on using a known message on the bus.  IE: It may need
        # to be tweaked later
        # TODO: Look into using a message from a generic handler to pick a random one
        self.driver.add_receive_handler(msg_handler, self.KNOWN_ID_ON_BUS)

        # Wait for all of the messages to arrive
        for event in events:
            event.wait(1)# wait for at least 1 second for each message

        # Determine how many messages were in fact recorded
        rx_cnt = 0
        for event in events:
            if event.isSet():
                rx_cnt += 1
        self.assertEqual(rx_cnt, required_rx_count,
            msg="Expected %d messages, receved %d messages" % (required_rx_count, rx_cnt))

if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(CANUSBTests)
    unittest.TextTestRunner(verbosity=2).run(suite)

