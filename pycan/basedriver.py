# -*- coding: utf-8 -*-
# Copyright (c) 2013 The pycan developers. All rights reserved.
# Project site: https://github.com/questrail/pycan
# Use of this source code is governed by a MIT-style license that
# can be found in the LICENSE.txt file for the project.
"""Provide base CAN driver functionality.

These base classes provide the common/base CAN functionality that is shared
among all CAN hardware interfaces.
"""
import unittest
import Queue
import thread
import threading
import time

QUEUE_DELAY = 1

# TODO(A. Lewis) Add Alarm flags.
# TODO(A. Lewis) Add logger.
# TODO(A. Lewis) Look into removing the datalengh from the CAN message init


class CANMessage(object):
    """Models the CAN message

    Attributes:
        id: An integer representing the raw CAN id
        dlc: An integer representing the total data length of the message
        payload:
        extended: A boolean indicating if the message is a 29 bit message
        ts: An integer representing the time stamp
    """
    def __init__(self, id, dlc, payload, extended=True, ts=0):
        """Inits CANMesagge."""
        self.id = id
        self.dlc = dlc
        self.payload = payload
        self.extended = extended
        self.time_stamp = ts

    def __str__(self):
        return "%s,%d : %s" % (hex(self.id), self.dlc, str(self.payload))


class CyclicMessage(object):
    """Wraps the CAN message model to hold timing information

    Attributes:
        msg: The CANMessage to be sent
        rate: A float representing the expected transmission rate (seconds)
    """
    def __init__(self, msg, rate):
        self.msg = msg
        self.rate = rate
        self.next_run = time.time() + rate  # Now
        self.active = True

    def determine_next_run(self):
        if self.active:
            self.next_run = time.time() + self.rate
        else:
            self.next_run = None


class BaseDriver(object):
    def __init__(self, max_in=500, max_out=500, loopback=False):
        """Inits BaseDriver."""
        self.total_inbound_count = 0
        self.inbound = Queue.Queue(max_in)
        self.total_outbound_count = 0
        self.outbound = Queue.Queue(max_out)
        self.loopback = loopback

        self._msg_lock = threading.Lock()
        self._handle_lock = threading.Lock()
        self._receive_handlers = {}
        self._running = threading.Event()
        self._running.set()

        self._cyclic_messages = {}
        self._cyclic_fastest_rate = 1.0

        self._cyclic_thread = threading.Thread(target=self.__cyclic_monitor)
        self._cyclic_thread.daemon = True
        self._cyclic_thread.start()

        self._inbound_thread = threading.Thread(target=self.__inbound_monitor)
        self._inbound_thread.daemon = True
        self._inbound_thread.start()

    def wait_for_message(self, can_id, timeout=None, ext=True):
        pass
        # Blocking call to wait for a specific message

    def add_receive_handler(self, handler, can_id=None, ext=True):
        with self._handle_lock:
            self._receive_handlers[handler] = (can_id, ext)

        return True

    def remove_receive_handler(self, handler):
        with self._handle_lock:
            self._receive_handlers.pop(handler)

        return True

    def add_cyclic_message(self, message, rate, desc=None):
        with self._msg_lock:
            if desc is None:
                desc = message.id

            try:
                # Update / Add new messages
                self._cyclic_messages[desc] = CyclicMessage(message, rate)

                # Determine the CPU delay based off of fasest rate
                if rate < self._cyclic_fastest_rate:
                    self._cyclic_fastest_rate = rate

                return True
            except:
                return False

    def update_cyclic_message(self, message, desc=None):
        with self._msg_lock:
            if desc is None:
                desc = message.id

            # Ensure the message exsits
            if desc in self._cyclic_messages:
                # Update message
                self._cyclic_messages[desc].msg = message

                return True
            else:
                return False

    def stop_cyclic_message(self, desc):
        with self._msg_lock:
            if desc in self._cyclic_messages:
                self._cyclic_messages[desc].active = False
                return True
            else:
                return False

    def send(self, message):
        with self._msg_lock:
            try:
                # Attempt to push the message onto the queue
                self.outbound.put(message, timeout=QUEUE_DELAY)
                self.total_outbound_count += 1

                # Push the message onto the inbound queue
                if self.loopback:
                    try:
                        self.inbound.put(message, timeout=QUEUE_DELAY)
                    except Queue.Full:
                        # TODO: Add a log message showing the loopback failed
                        return False

                return True

            except Queue.Full:
                return False

    def shutdown(self):
        self.scheduler.stop()
        self._running.clear()

    def __send_cyclic(self, id_to_use):
        self.send(self._cyclic_messages[id_to_use])

    def __cyclic_monitor(self):
        while self._running.is_set():
            time.sleep(self._cyclic_fastest_rate/3.0)
            for cyclic in self._cyclic_messages.values():
                if time.time() > cyclic.next_run:
                    self.send(cyclic.msg)
                    cyclic.determine_next_run()

    def __inbound_monitor(self):
        while self._running.is_set():
            try:
                # Check the Queue for a new message, throttled by timeout
                new_msg = self.inbound.get(timeout=QUEUE_DELAY)
                self.total_inbound_count += 1
            except Queue.Empty:
                # Keep waiting
                continue

            # Inform the ID specific handlers
            for handler, key in self._receive_handlers.items():
                can_id, ext = key

                if new_msg.id == can_id or can_id is None:
                    if new_msg.extended == ext:
                        handler(new_msg)
