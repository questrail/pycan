# -*- coding: utf-8 -*-
# Copyright (c) 2013 The pycan developers. All rights reserved.
# Project site: https://github.com/questrail/pycan
# Use of this source code is governed by a MIT-style license that
# can be found in the LICENSE.txt file for the project.
"""Simulated CAN driver interface

This module extends the basedriver.BaseDriver class from `basedriver.py`
to provide an interface to a fake CAN hardware interface.

Operating System:
    * Independant
Hardware Requirements:
    * None
Driver Requirements:
    * None
"""
import sys
import time
import Queue
import threading
import basedriver
from pycan.common import CANMessage

QUEUE_DELAY = 1
MAX_BUFFER_SIZE = 1000
CAN_TX_SEND_DELAY = 0.0005
UNIQUE_SIM_MESSAGES = 8
SIM_PAYLOAD_SIZE = 8
DEFAULT_SIM_RX_RATE = 0.010


class SimCAN(basedriver.BaseDriverAPI):
    def __init__(self, **kwargs):
        # Extract the keyword arguments
        self.verbose = kwargs.get("verbose", False)
        self.sim_delay = kwargs.get("inbound_time", DEFAULT_SIM_RX_RATE)

        # Build the inbound and output buffers
        self.inbound = Queue.Queue(MAX_BUFFER_SIZE)
        self.inbound_count = 0
        self.outbound = Queue.Queue(MAX_BUFFER_SIZE)
        self.outbound_count = 0

        # Setup the simulated traffic
        self.inbound_index = 0
        self.known_msgs = []
        self.__generate_known_messages()

        # Tell python to check for signals less often (default 1000)
        #   - This yeilds better threading performance for timing
        #     accuracy
        sys.setcheckinterval(10000)

        # Start the background processes
        self._running = threading.Event()
        self._running.set()
        self.ob_t = self.start_daemon(self.__process_outbound_queue)
        self.ib_t = self.start_daemon(self.__process_inbound_queue)

    def send(self, message):
        while 1:
            try:
                self.outbound.put(message, QUEUE_DELAY)
                self.outbound_count += 1
                return True
            except Queue.Full:
                pass

    def next_message(self, timeout=None):
        if timeout is not None:
            stop = time.time() + timeout
        while 1:
            try:
                new_msg = self.inbound.get(timeout=QUEUE_DELAY)
                self.inbound_count += 1
                return new_msg
            except Queue.Empty:
                pass

            if timeout is not None:
                if time.time() > stop:
                    return None

    def life_time_sent(self):
        return self.outbound_count

    def life_time_received(self):
        return self.inbound_count

    def __process_outbound_queue(self):
        while self._running.is_set():
            try:
                can_msg = self.outbound.get(timeout=QUEUE_DELAY)
                time.sleep(CAN_TX_SEND_DELAY)
            except Queue.Empty:
                continue

            if self.verbose:
                print "\n", can_msg

    def __process_inbound_queue(self):
        while self._running.is_set():
            # Generate some known CAN traffic
            time.sleep(self.sim_delay)

            try:
                self.inbound.put(self.known_msgs[self.inbound_index])
                self.inbound_index += 1
                self.inbound_index = self.inbound_index % 8
            except Queue.Full:
                # TODO (A. Lewis) Add logging warning
                pass

    def __generate_known_messages(self):
        # Create fake CAN traffic
        for x in range(UNIQUE_SIM_MESSAGES):
            self.known_msgs.append(CANMessage(x, range(SIM_PAYLOAD_SIZE)))
