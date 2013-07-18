# -*- coding: utf-8 -*-
# Copyright (c) 2013 The pycan developers. All rights reserved.
# Project site: https://github.com/questrail/pycan
# Use of this source code is governed by a MIT-style license that
# can be found in the LICENSE.txt file for the project.
"""Fake CAN driver interface

This module extends the pycan.BaseDriver class from `basedriver.py` to provide an
interface to a fake CAN hardware interface.

External Python Dependancies:
Hardware Requirements:
Driver Requirements:
"""

# Test dependencies
import time
import unittest

# Driver dependencies
import Queue
import threading
import basedriver as pycan

QUEUE_DELAY = 1

class CANDriver(pycan.BaseDriver):
    def __init__(self, **kwargs):
        # Init the base driver
        super(CANDriver, self).__init__(kwargs.get("max_in", 500),
                                     kwargs.get("max_out", 500),
                                     kwargs.get("loopback", False))

        self.verbose = kwargs.get("verbose", False)
        self._running = threading.Event()
        self._running.set()

        self.inbound_index = 0
        self.known_msgs = []
        self.__generate_known_messages()

        self.ob_t = threading.Thread(target=self.__process_outbound_queue)
        self.ob_t.daemon = True
        self.ob_t.start()

        self.ib_t = threading.Thread(target=self.__process_inbound_queue)
        self.ib_t.daemon = True
        self.ib_t.start()

    def __generate_known_messages(self):
        # Create 8 CAN messages
        for x in range(1,9):
            self.known_msgs.append(pycan.CANMessage(x, x, range(0,x)))

    def __process_outbound_queue(self):
        while self._running.is_set():
            try:
                # Read the Queue - allow the timeout to throttle the thread
                can_msg = self.outbound.get(timeout=QUEUE_DELAY)
            except Queue.Empty:
                continue

            if self.verbose:
                print "\n", can_msg

    def __process_inbound_queue(self):
        while self._running.is_set():
            # Generate some known CAN traffic
            time.sleep(self.known_msgs[self.inbound_index].id * .01)

            try: # Push the message into the inbound queue
                self.inbound.put(self.known_msgs[self.inbound_index])
            except Queue.Full:
                # TODO (A. Lewis) Add logging warning
                pass

            self.inbound_index += 1
            self.inbound_index = self.inbound_index % 8

class MockTests(unittest.TestCase):
    KNOWN_ID_ON_BUS = 0x8
    def setUp(self):
        self.driver = None

    def tearDown(self):
        try:
            self.driver.shutdown()
            time.sleep(2)
        except:
            pass

    def testTransmit(self):
        self.driver = CANDriver(verbose=True)
        msg1 = pycan.CANMessage(0x123456, 3, [1,2,3])
        # Watch the CAN bus to ensure the message was sent
        self.assertTrue(self.driver.send(msg1))

    def testCyclicTransmit(self):
        self.driver = CANDriver(verbose=True)
        msg1 = pycan.CANMessage(0x123456, 3, [1,2,3])
        msg2 = pycan.CANMessage(0x123456, 4, [5,6,7,8])

        self.assertTrue(self.driver.add_cyclic_message(msg1, .1, "Sample"))
        time.sleep(3) # Watch the CAN bus to ensure the messages are being sent
        self.assertTrue(self.driver.update_cyclic_message(msg2, "Sample"))
        time.sleep(3) # Watch the CAN bus to ensure the messages changed and are being sent

    def testGenericReceive(self):
        required_rx_count = 10
        events = []
        for x in range(required_rx_count):
            events.append(threading.Event())
            events[-1].clear()

        self.driver = CANDriver()

        def gen_handler(msg):
            # Walk down the number of events marking them as
            # each new message is received
            for event in events:
                if not event.isSet():
                    event.set()
                    print "\n", msg
                    break;

        self.driver.add_receive_handler(gen_handler)

        for event in events:
            event.wait(1)# wait for at least 1 second for each message

        # Determine how many messages were in fact recorded
        rx_cnt = 0
        for event in events:
            self.assertTrue(event.isSet(),
                            msg="Expected %d messages, receved %d messages" % (required_rx_count, rx_cnt))
            rx_cnt += 1

    def testSpecificReceive(self):
        required_rx_count = 10
        events = []
        for x in range(required_rx_count):
            events.append(threading.Event())
            events[-1].clear()

        self.driver = CANDriver()

        def msg_handler(msg):
            # Walk down the number of events marking them as
            # each new message is received
            for event in events:
                if not event.isSet():
                    event.set()
                    print msg
                    break;

        # This test relies on using a known message on the bus.  IE: It may need
        # to be tweaked later
        # TODO: Look into using a message from a generic handler to pick a random one
        self.driver.add_receive_handler(msg_handler, self.KNOWN_ID_ON_BUS)

        # Wait for all of the messages to arrive
        for event in events:
            event.wait(1)# wait for at least 1 second for each message

        # Determine how many messages were in fact recorded
        rx_cnt = 0
        for event in events:
            self.assertTrue(event.isSet(),
                            msg="Expected %d messages, receved %d messages" % (required_rx_count, rx_cnt))
            rx_cnt += 1




if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(MockTests)
    unittest.TextTestRunner(verbosity=2).run(suite)

