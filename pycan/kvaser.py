# -*- coding: utf-8 -*-
# Copyright (c) 2013 The pycan developers. All rights reserved.
# Project site: https://github.com/questrail/pycan
# Use of this source code is governed by a MIT-style license that
# can be found in the LICENSE.txt file for the project.
"""Kvaser USB CAN driver interface

This moduel extends the basedriver.BaseDriver class from `basedriver.py`
to provide an interface to the Kvaser CAN USB products.

External Python Dependancies:
Hardware Requirements:
    * Kvaser (http://www.kvaser.com/en/products/can/usb.html)
Driver Requirements:
"""

import Queue
import threading
import basedriver
from common import CANMessage
from ctypes import *

CAN_TX_TIMEOUT = 100  # ms
CAN_RX_TIMEOUT = 100  # ms
QUEUE_DELAY = 1  # second


class Kvaser(basedriver.BaseDriver):
    def __init__(self, **kwargs):
        # Init the base driver
        super(Kvaser, self).__init__(max_in=500, max_out=500, loopback=False)

        # Init the Leaf Light HS DLL
        windll.canlib32.canInitializeLibrary()

        # Open a CAN communication channel
        # TODO: Add multi channel support
        self._can_channel = windll.canlib32.canOpenChannel(c_int(0), c_int8(0))

        # Bus on and clear the hardware queues
        windll.canlib32.canBusOn(c_int(self._can_channel))
        windll.canlib32.canFlushReceiveQueue(c_int(self._can_channel))
        windll.canlib32.canFlushTransmitQueue(c_int(self._can_channel))

        # Set the default paramters
        self.update_bus_parameters()

        self._running = threading.Event()
        self._running.set()
        self.ob_t = self.start_daemon(self.__process_outbound_queue)
        self.ib_t = self.start_daemon(self.__process_inbound_queue)

    def update_bus_parameters(self, **kwargs):
        # Default values are setup for a 250k baud and a 75% sample point
        # Set up the timing parameters for the CAN controller
        windll.canlib32.canSetBusParams(c_int(self._can_channel),
                                        c_int(kwargs.get("baud", 250000)),
                                        c_uint(kwargs.get("tseg1", 5)),
                                        c_uint(kwargs.get("tseg2", 2)),
                                        c_uint(kwargs.get("sjw", 2)),
                                        c_uint(kwargs.get("sample_count", 1)),
                                        c_uint(0))

    def __process_outbound_queue(self):
        while self._running.is_set():
            try:
                can_msg = self.outbound.get(timeout=QUEUE_DELAY)
            except Queue.Empty:
                continue

            tx_data = (c_uint8 * can_msg.dlc)()
            for x in range(can_msg.dlc):
                tx_data[x] = can_msg.payload[x]

            if can_msg.extended:
                ext = 4
            else:
                ext = 2

            status = windll.canlib32.canWriteWait(c_int(self._can_channel),
                                                  c_uint32(can_msg.id),
                                                  pointer(tx_data),
                                                  c_int(can_msg.dlc),
                                                  c_int(ext),
                                                  c_uint32(CAN_TX_TIMEOUT))
        # TODO: Flag error status

    def __process_inbound_queue(self):
        while self._running.is_set():
            rx_id = c_uint(0)
            rx_dlc = c_uint(0)
            rx_flags = c_uint(0)
            rx_time = c_uint(0)
            rx_msg = (c_uint8 * 8)()

            status = windll.canlib32.canReadWait(c_int(self._can_channel),
                                                 pointer(rx_id),
                                                 pointer(rx_msg),
                                                 pointer(rx_dlc),
                                                 pointer(rx_flags),
                                                 pointer(rx_time),
                                                 c_uint32(CAN_RX_TIMEOUT))

            if status < 0:
                pass
                #TODO: Flag error

            else:
                # Determine if it is 11bit or 29bit
                if (rx_flags.value >> 1) & 0x01:
                    rx_ext = False
                elif (rx_flags.value >> 2) & 0x01:
                    rx_ext = True
                else:
                    rx_ext = None

                if rx_ext is not None:
                    # Build the message
                    new_msg = CANMessage(rx_id.value, rx_msg)

                    try:
                        self.inbound.put(new_msg, timeout=QUEUE_DELAY)
                    except Queue.Full:
                        # TODO: flag error
                        pass
