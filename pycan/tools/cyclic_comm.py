# -*- coding: utf-8 -*-
# Copyright (c) 2013 The pycan developers. All rights reserved.
# Project site: https://github.com/questrail/pycan
# Use of this source code is governed by a MIT-style license that
# can be found in the LICENSE.txt file for the project.
"""Provide cyclic transmit and receive functionality.

The cyclic communcation modlue is designed to add an additional
layer of functionality on top of the generic CAN drivers.
These additional features include cyclic transmissions as well
as generic receive handlers.  In general this should be the
base communication module for CAN device simulators
"""
import time
import Queue
import threading
import collections

# TODO(A. Lewis) Add Alarm flags.
# TODO(A. Lewis) Add logger.


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


class CyclicComm(object):
    def __init__(self, driver):
        """Inits CyclicComm."""
        self.driver = driver

        self._msg_lock = threading.Lock()
        self._handle_lock = threading.Lock()
        self._receive_handlers = collections.deque()
        self._running = threading.Event()
        self._running.set()

        self._cyclic_messages = {}
        self._cyclic_fastest_rate = 1.0

        self._cyclic_thread = self.start_daemon(self.__cyclic_monitor)
        self._inbound_thread = self.start_daemon(self.__inbound_monitor)

    def start_daemon(self, process):
        t = threading.Thread(target=process)
        t.daemon = True
        t.start()
        return t

    def add_receive_handler(self, handler, can_id=None, ext=True):
        with self._handle_lock:
            self._receive_handlers.append((can_id, ext, handler))

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
            return self.driver.send(message)

    def shutdown(self):
        self._running.clear()

    # TODO: Add a multi-step timer (sleep > 20ms, then busy loop)
    def __cyclic_monitor(self):
        while self._running.is_set():
            time.sleep(self._cyclic_fastest_rate/5.0)
            for cyclic in self._cyclic_messages.values():
                if cyclic.active:
                    if time.time() > cyclic.next_run:
                        self.send(cyclic.msg)
                        cyclic.determine_next_run()

    def __inbound_monitor(self):
        while self._running.is_set():
            # Check the Queue for a new message, throttled by driver
            new_msg = self.driver.next_message(timeout=1)

            # Inform the ID specific handlers
            for can_id, ext, handler in self._receive_handlers:

                if new_msg.id == can_id or can_id is None:
                    if new_msg.extended == ext:
                        handler(new_msg)

