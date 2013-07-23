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

import time
import Queue
import threading
import basedriver
from common import CANMessage

QUEUE_DELAY = 1


class SimCAN(basedriver.BaseDriver):
    def __init__(self, **kwargs):
        # Init the base driver
        super(SimCAN, self).__init__(kwargs.get("max_in", 500),
                                     kwargs.get("max_out", 500),
                                     kwargs.get("loopback", False))

        self.verbose = kwargs.get("verbose", False)

        self.inbound_index = 0
        self.known_msgs = []
        self.__generate_known_messages()

        self._running = threading.Event()
        self._running.set()
        self.ob_t = self.start_daemon(self.__process_outbound_queue)
        self.ib_t = self.start_daemon(self.__process_inbound_queue)

    def __generate_known_messages(self):
        # Create fake CAN traffic
        for x in range(1, 9):
            self.known_msgs.append(CANMessage(x, range(0, x)))

    def __process_outbound_queue(self):
        while self._running.is_set():
            try:
                can_msg = self.outbound.get(timeout=QUEUE_DELAY)
                time.sleep(.0005)
            except Queue.Empty:
                continue

            if self.verbose:
                print "\n", can_msg

    def __process_inbound_queue(self):
        while self._running.is_set():
            # Generate some known CAN traffic
            time.sleep(self.known_msgs[self.inbound_index].id * .01)

            try:
                self.inbound.put(self.known_msgs[self.inbound_index])
            except Queue.Full:
                # TODO (A. Lewis) Add logging warning
                pass

            self.inbound_index += 1
            self.inbound_index = self.inbound_index % 8
