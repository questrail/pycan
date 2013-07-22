# -*- coding: utf-8 -*-
# Copyright (c) 2013 The pycan developers. All rights reserved.
# Project site: https://github.com/questrail/pycan
# Use of this source code is governed by a MIT-style license that
# can be found in the LICENSE.txt file for the project.
"""CANalyzer ASC File / Line Parser

Module used to parse ASC files and conforms to the trace player's
API requirements.
"""
import time
import threading
from pycan.common import CANMessage

DIRTY_WORDS = ['Statistic:', 'date', 'base', 'events', 'version']
ABS = 'absolute'
DELTA = 'deltas'
MIN_DELAY = .0001


class ASCParser(object):
    def __init__(self, exclude_filters=[], use_wall=True):
        self.exclude_filters = exclude_filters
        self.use_wall = use_wall
        self.last_ts = None
        self.next_message = None

        self.settings = {}
        self.settings['timestamps'] = ABS
        self.settings['base'] = 10

    def parse_line(self, line):
        self.next_message = None

        # Split the line prior to parsing
        split_line = line.strip(' ').split(' ')

        # Check for ASC settings
        self.__lookup_asc_settings(split_line)

        # Check to see if the line is a valid line
        for word in DIRTY_WORDS:
            if word in split_line:
                return self.next_message

        # Determine and remove the common line items
        ts = float(split_line.pop(0))
        chan = split_line.pop(0).strip(' ')
        can_id = split_line.pop(0).strip(' ')
        direction = split_line.pop(0).strip(' ')
        rd_flag = split_line.pop(0).strip(' ')

        # Build valid messages
        if rd_flag is 'd':
            # Extract the payload
            dlc = int(split_line.pop(0))

            payload = []
            for b in range(dlc):
                payload.append(int(split_line.pop(0), self.settings['base']))

            # Build the can message and extended flag
            if can_id[-1] is 'x':
                can_id = can_id[:-1]
                ext = True
            else:
                ext = False

            can_id = int(can_id, self.settings['base'])

            # Build the real CAN message
            self.next_message = CANMessage(can_id, payload, ext)

        # Determine how long to delay (applies to data and remote frames)
        delay = self.__determine_delay(ts)

        # Add any required delay
        self.__apply_delay(delay)

        return self.next_message

    def __determine_delay(self, ts):
        if self.use_wall:
            if self.last_ts is None:
                delay = None
            elif self.settings['timestamps'] == DELTA:
                delay = ts
            else:
                delay = ts - self.last_ts

            self.last_ts = ts

        else:
            # Apply a minimum delay as the CAN bus is limited to how fast it
            # can actually put messages on the wire
            delay = MIN_DELAY

    def __apply_delay(self, delay):
        if delay:
            evt = threading.Event()
            evt.wait(delay)

    def __lookup_asc_settings(self, split_line):
        keyword = 'base'
        if keyword in split_line:
            idx = split_line.index(keyword)
            if split_line[idx + 1] is 'hex':
                self.settings[keyword] = 16
            else:
                self.settings[keyword] = 10

        keyword = 'timestamps'
        if keyword in split_line:
            idx = split_line.index(keyword)
            if split_line[idx + 1] is ABS:
                self.settings[keyword] = ABS
            else:
                self.settings[keyword] = DELTA
