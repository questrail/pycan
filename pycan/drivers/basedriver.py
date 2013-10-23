# -*- coding: utf-8 -*-
# Copyright (c) 2013 The pycan developers. All rights reserved.
# Project site: https://github.com/questrail/pycan
# Use of this source code is governed by a MIT-style license that
# can be found in the LICENSE.txt file for the project.
"""Provide base CAN driver functionality.

These base classes provide the common/base CAN functionality that is shared
among all CAN hardware interfaces.
"""
import threading


class BaseDriverAPI(object):
    def send(self, message):
        """Blocking call to put a CAN message onto the outbound buffer
        """
        raise NotImplementedError
        return True

    def next_message(self):
        """Blocking call to get the next CAN message from the inbound
        buffer
        """
        raise NotImplementedError
        return new_can_message

    def life_time_sent(self):
        """Should return the total number of messages sent via
        the send API
        """
        raise NotImplementedError
        return 0

    def life_time_received(self):
        """Should return the total number of messages received via
        the next_message API
        """
        raise NotImplementedError
        return 0

    def start_daemon(self, process):
        t = threading.Thread(target=process)
        t.daemon = True
        t.start()
        return t

