# -*- coding: utf-8 -*-
# Copyright (c) 2013 The pycan developers. All rights reserved.
# Project site: https://github.com/questrail/pycan
# Use of this source code is governed by a MIT-style license that
# can be found in the LICENSE.txt file for the project.


class CANMessage(object):
    """Models the CAN message

    Attributes:
        id: An integer representing the raw CAN id
        payload: Message payload to be transmitted
        extended: A boolean indicating if the message is a 29 bit message
        ts: An integer representing the time stamp
    """
    def __init__(self, id, payload, extended=True, ts=0):
        """Inits CANMesagge."""
        self.id = id
        self.dlc = len(payload)
        self.payload = payload
        self.extended = extended
        self.time_stamp = ts

    def __str__(self):
        return "%s,%d : %s" % (hex(self.id), self.dlc, [hex(x) for x in self.payload])


class IDMaskFilter(object):
    """CAN ID Mask Filter

    Attributes:
        mask: An integer representing the bit fields required to match
        code: An integer representing the id to apply the mask against
        extended: A boolean indicating if the message is a 29 bit message
    """
    def __init__(self, mask, code, extended=True):
        """Inits Mask Filter."""
        self.mask = mask
        self.code = code
        self.extended = extended

    def filter_match(self, msg):
        """Tests if the given CAN message should pass through the filter"""
        # Check the extended bit
        if msg.extended != self.extended:
            return False

        # Check the mask / code combo
        target = self.mask & self.code
        if (msg.id & self.mask) == target:
            return True
        else:
            return False


class CANTimeoutWarning(UserWarning):
    def __unicode__(self):
        return "Warning: pyCAN Timeout Detected"
