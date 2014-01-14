# -*- coding: utf-8 -*-
# Copyright (c) 2013 The pycan developers. All rights reserved.
# Project site: https://github.com/questrail/pycan
# Use of this source code is governed by a MIT-style license that
# can be found in the LICENSE.txt file for the project.
"""LAWICEL CANUSB CAN driver interface

This moduel extends the basedriver.BaseDriver class from `basedriver.py`
to provide an interface to the LAWICEL AB CANUSB CAN module.

Operating System:
    * Independant
Hardware Requirements:
    * CANUSB (http://www.can232.com)
Driver Requirements:
    * FTDI D2XX Driver / Support
        - See http://www.can232.com/docs/canusb_drinst_d2xx.pdf
"""
import time
import sys
import threading
import Queue
import basedriver
from pycan.common import CANMessage
import serial

QUEUE_DELAY = .1
CAN_TX_TIMEOUT = 100  # ms
CAN_RX_TIMEOUT = 100  # ms
MAX_BUFFER_SIZE = 1000
COMMAND_TIMEOUT = 1.0  # seconds
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


class CANUSB(basedriver.BaseDriverAPI):
    def __init__(self, **kwargs):
        # Open the COM port
        port = kwargs['com_port']  # Throws key error
        baud = int(kwargs.get('com_baud', 115200))
        self.port = serial.Serial(port=port, baudrate=baud,
                                  timeout=0.001, writeTimeout=5)
        self.port.flushInput()
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

        # Go on bus
        self.bus_on()

        # Build the inbound and output buffers
        self.inbound = Queue.Queue(MAX_BUFFER_SIZE)
        self.inbound_count = 0
        self.outbound = Queue.Queue(MAX_BUFFER_SIZE)
        self.outbound_count = 0

        # Tell python to check for signals less often (default 1000)
        #   - This yeilds better threading performance for timing
        #     accuracy
        sys.setcheckinterval(10000)

        self._running = threading.Event()
        self._running.set()
        self.ob_t = self.start_daemon(self.__process_outbound_queue)
        self.ib_t = self.start_daemon(self.__process_inbound_queue)

    def shutdown(self):
        self._running.clear()
        time.sleep(1)

    def bus_on(self):
        return self.__send_command(OPEN_CMD)

    def bus_off(self):
        return self.__send_command(CLOSE_CMD)

    def send(self, message):
        while 1:
            try:
                self.outbound.put(message, timeout=QUEUE_DELAY)
                self.outbound_count += 1
                return True
            except Queue.Full:
                pass

    def next_message(self, timeout=None):
        if timeout is not None:
            stop = time.time() + timeout
        while 1:
            if timeout is not None:
                if time.time() > stop:
                    return None
            try:
                new_msg = self.inbound.get(timeout=QUEUE_DELAY)
                self.inbound_count += 1
                return new_msg
            except Queue.Empty:
                pass

    def life_time_sent(self):
        return self.outbound_count

    def life_time_received(self):
        return self.inbound_count

    def __send_command(self, cmd, timeout=COMMAND_TIMEOUT):
        # Due to the CANUSB driver not sending confirmation during moderate
        # bus loads, waiting for any amount of will likely be useless.

        # Send the command
        try:
            bytes_sent = self.port.write(cmd)
        except serial.SerialTimeoutException:
            pass

        return (bytes_sent == len(cmd))

    def update_bus_parameters(self, **kwargs):
        # Default values are setup for a 250k connetion
        br = kwargs.get('bit_rate', '250K')
        br_cmd = BIT_RATE_CMD.get(br, None)
        if br_cmd:
            return self.__send_command(br_cmd)

        return False

    def __process_outbound_queue(self):
        while self._running.is_set():
            try:
                # Read the Queue - allow the timeout to throttle the thread
                can_msg = self.outbound.get(timeout=QUEUE_DELAY)
            except Queue.Empty:
                continue

            outbound_msg = ''
            if can_msg.extended:
                id_str = "T%08X" % (can_msg.id & 0x1FFFFFFF)
                ack = 'Z\r'
            else:
                id_str = "t%03X" % (can_msg.id & 0x7FF)
                ack = 'z\r'

            outbound_msg += id_str
            outbound_msg += "%X" % (can_msg.dlc)

            for x in range(can_msg.dlc):
                outbound_msg += "%02X" % (can_msg.payload[x])

            outbound_msg += "\r"

            self.__send_command(outbound_msg)

    def __process_inbound_queue(self):
        while self._running.is_set():
            # Grab all of the data from the serial port
            bytes_to_read = self.port.inWaiting()
            if bytes_to_read > 0:
                self.rx_buffer += self.port.read(bytes_to_read)
            elif self.rx_buffer != '':
                pass  # There is buffered data to process
            else:
                # There is no pending data - use the serial port to
                # throttle the thread
                self.rx_buffer += self.port.read()

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
                    try:
                        if hdr == 'T':  # 29 bit message
                            e_id = 9  # ending can_id index
                            ext = True
                        else:  # hdr == 't' # 11 bit message
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
                        for x in range(s_payload, e_payload, 2):
                            val = int(msg[x:x+2], 16)
                            payload.append(val)

                        # Get the timestamp (if any)
                        timestamp = 0
                        if len(msg[e_payload:-1]) == 4:
                            timestamp = int(msg[e_payload+1:-1], 16)

                        # Build the message
                        new_msg = CANMessage(can_id, payload, ext, timestamp)

                        try:
                            self.inbound.put(new_msg, timeout=QUEUE_DELAY)
                        except Queue.Full:
                            # TODO: flag error
                            pass

                    except IndexError:
                        # TODO (A. Lewis) Log the bad message from the comport
                        # Chuck partial messages
                        pass
                    except ValueError:
                        # Chuck malformed messages
                        pass

                elif hdr in REM_MSG_HEADERS:
                    pass  # Not supported
                else:
                    # Unknown type --> assume it's a command response
                    # TODO: Log an alarm on any <BELL> responses found
                    self.response = msg
