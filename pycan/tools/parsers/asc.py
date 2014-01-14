# -*- coding: utf-8 -*-
# Copyright (c) 2013 The pycan developers. All rights reserved.
# Project site: https://github.com/questrail/pycan
# Use of this source code is governed by a MIT-style license that
# can be found in the LICENSE.txt file for the project.
"""CANalyzer ASC File / Line Parser

Module used to parse ASC files and conforms to the trace player's
API requirements.
"""
import os
import time
import threading

from pycan.common import CANMessage

DIRTY_WORDS = ['Statistic:', 'date', 'base', 'events', 'version', 'Begin']
ABS = 'absolute'
DELTA = 'deltas'
MIN_DELAY = 0


class ASCParser(object):
    def __init__(self, asc_file='', include_filters=None, exclude_filters=None):
        self.include_filters = include_filters if include_filters else []
        self.exclude_filters = exclude_filters if exclude_filters else []
        self.last_ts = None
        self.micro_second_tick = 0
        self.next_message = None
        self.trace_fid = None

        if self.__valid_file(asc_file):
            self.trace_file = asc_file
        else:
            self.trace_file = None

        self.settings = {}
        self.settings['timestamps'] = ABS
        self.settings['base'] = 10

    def __valid_file(self, file_path):
        if os.path.isfile(file_path):
            fileName, fileExt = os.path.splitext(file_path)
            if fileExt == '.asc':
                return True

        return False

    def shutdown(self):
        try:
            self.trace_fid.close()
        except:
            pass

        self.trace_fid = None

    def message_generator(self):
        # Check to see if the file is open yet
        if self.trace_fid is None and self.trace_file is not None:
            self.trace_fid = open(self.trace_file, 'rb')

        # Parse the file until we get a valid line to return
        try:
            while 1:
                line = self.trace_fid.readline()
                if not line:
                    #EOF
                    self.trace_fid.close()
                    break;

                new_msg = self.parse_line(line)
                if new_msg:
                    # Return the next message
                    yield new_msg

        except:
            # Make sure to close the file if something fails
            self.shutdown()
            # Re-reraise the exception
            raise

    def parse_line(self, line):
        self.next_message = None

        # Compress all of the white space
        line = ' '.join(line.split())

        # Split the line prior to parsing
        split_line = line.strip(' ').split(' ')

        # Check for ASC settings
        self.__lookup_asc_settings(split_line)

        # Check to see if the line is a valid line
        for word in DIRTY_WORDS:
            if word in split_line:
                return self.next_message

        # Check that the line has all the common line items
        if len(split_line) < 5:
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

            try:
                can_id = int(can_id, self.settings['base'])
            except ValueError:
                # Just use the string value in the case of a label
                pass

            # Build the real CAN message
            msg = CANMessage(can_id, payload, ext)

        elif can_id == "ErrorFrame":
            msg = CANMessage(-1, [], False)

        else:
            msg = None


        # Determine the timestamp of the message
        if msg:
            msg.time_stamp = self.__determine_time_stamp(ts)

        if not self.include_filters:
            # Include them all
            self.next_message = msg
        else:
            # Determine if the message should be included
            for mask in self.include_filters:
                if mask.filter_match(msg):
                    self.next_message = msg
                    break

        # Determine if the message is explicity excluded
        for mask in self.exclude_filters:
            if mask.filter_match(msg):
                self.next_message = None
                break

        return self.next_message

    def __determine_time_stamp(self, ts):

        if self.last_ts is None:
            stamp = 0
        elif self.settings['timestamps'] == DELTA:
            stamp = (ts + self.last_ts)
        else:
            stamp = ts

        self.last_ts = ts

        new_us_tick = stamp * 1e6

        # Make sure no messages are at the exact same time
        if new_us_tick == self.micro_second_tick:
            self.micro_second_tick = new_us_tick + 1
        else:
            self.micro_second_tick = new_us_tick

        return self.micro_second_tick

    def __lookup_asc_settings(self, split_line):
        keyword = 'base'
        if keyword in split_line:
            idx = split_line.index(keyword)
            if split_line[idx + 1].strip().lower() == 'hex':
                self.settings[keyword] = 16
            else:
                self.settings[keyword] = 10

        keyword = 'timestamps'
        if keyword in split_line:
            idx = split_line.index(keyword)
            if split_line[idx + 1].strip().lower() == ABS:
                self.settings[keyword] = ABS
            else:
                self.settings[keyword] = DELTA