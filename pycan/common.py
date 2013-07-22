# -*- coding: utf-8 -*-
# Copyright (c) 2013 The pycan developers. All rights reserved.
# Project site: https://github.com/questrail/pycan
# Use of this source code is governed by a MIT-style license that
# can be found in the LICENSE.txt file for the project.


class CANMessage(object):
    """Models the CAN message

    Attributes:
        id: An integer representing the raw CAN id
        dlc: An integer representing the total data length of the message
        payload:
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
        return "%s,%d : %s" % (hex(self.id), self.dlc, str(self.payload))



