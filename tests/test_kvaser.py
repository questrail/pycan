# -*- coding: utf-8 -*-
# Copyright (c) 2013 The pycan developers. All rights reserved.
# Project site: https://github.com/questrail/pycan
# Use of this source code is governed by a MIT-style license that
# can be found in the LICENSE.txt file for the project.
import os
import time
import threading
import unittest
import ConfigParser
import pycan.drivers.kvaser as driver
from pycan.common import CANMessage


class KvaserTests(unittest.TestCase):
    def tearDown(self):
        try:
            self.driver.bus_off()
            self.driver.shutdown()
            time.sleep(2)
        except:
            pass

    def __load_test_config(self):
        test_path = os.path.dirname(os.path.abspath(__file__))
        config = ConfigParser.ConfigParser()
        config.read(os.path.join(test_path, 'test.cfg'))

        self.known_can_id = int(config.get('COMMON', 'Known_ID_On_Bus'), 16)

    def testPEP8Compliance(self):
        # Ensure PEP8 is installed
        try:
            import pep8
        except ImportError:
            self.fail(msg="PEP8 not installed.")

        # Check the CAN driver
        driver_path = os.path.dirname(driver.__file__)
        driver_file = os.path.abspath(os.path.join(driver_path, 'kvaser.py'))
        pep8_checker = pep8.Checker(driver_file)
        violation_count = pep8_checker.check_all()
        error_message = "PEP8 violations found: %d" % (violation_count)
        self.assertTrue(violation_count == 0, msg = error_message)

    def testDriver(self):
        # Load the real time test configuration
        self.__load_test_config()

        # Setup the driver
        self.driver = driver.Kvaser()

        # Run the driver specific tests if and only if the driver was setup
        self.Transmit()
        self.Receive()
        self.SpecificReceive()

    def Transmit(self):
        # Note you must also check that the CAN message is being placed
        # on the wire at 100ms intervals
        messages_to_send = 50

        msg1 = CANMessage(0x123456, [1,2,3])
        for x in range(messages_to_send):
            time.sleep(0.1)
            msg = "Failed to send message {x}".format(x=x)
            self.assertTrue(self.driver.send(msg1), msg)

        self.assertEqual(self.driver.life_time_sent(), messages_to_send)

    def Receive(self):
        messages_to_receive = 25

        # Check that the life time received hasn't been updated yet
        self.assertEqual(self.driver.life_time_received(), 0)

        # Read back a fixed number of messages and check that the lifetime
        # values track the next_message call
        read_messages = 0
        for x in range(messages_to_receive):
            if self.driver.next_message():
                self.assertEqual((x+1), self.driver.life_time_received())

    def SpecificReceive(self):
        messages_to_receive = 10
        actual_messaged_received = 0
        max_specific_attempts = 1000

        # Keep reading from the bus until we find the required messages
        read_messages = 0
        for x in range(max_specific_attempts):
            msg = self.driver.next_message()
            if msg.id == self.known_can_id:
                actual_messaged_received += 1

                if actual_messaged_received == messages_to_receive:
                    break;

        self.assertEqual(actual_messaged_received, messages_to_receive)
