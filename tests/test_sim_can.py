# -*- coding: utf-8 -*-
# Copyright (c) 2013 The pycan developers. All rights reserved.
# Project site: https://github.com/questrail/pycan
# Use of this source code is governed by a MIT-style license that
# can be found in the LICENSE.txt file for the project.
import os
import random
import unittest
import pycan.drivers.sim_can as driver
from pycan.common import CANMessage

class SimCANTests(unittest.TestCase):
    def tearDown(self):
        try:
            self.driver.shutdown()
            time.sleep(2)
        except:
            pass

    def testPEP8Compliance(self):
        # Ensure PEP8 is installed
        try:
            import pep8
        except ImportError:
            self.fail(msg="PEP8 not installed.")

        # Check the CAN driver
        driver_path = os.path.dirname(driver.__file__)
        driver_file = os.path.abspath(os.path.join(driver_path, 'sim_can.py'))
        pep8_checker = pep8.Checker(driver_file)
        violation_count = pep8_checker.check_all()
        error_message = "PEP8 violations found: %d" % (violation_count)
        self.assertTrue(violation_count == 0, msg = error_message)

    def testDriver(self):
        # Setup the driver
        self.driver = driver.SimCAN(verbose=False)

        # Run the driver specific tests if and only if the driver was setup
        self.Transmit()
        self.Receive()

    def Transmit(self):
        messages_to_send = int(random.random() * 1000) + 1

        msg1 = CANMessage(0x123456, [1,2,3])
        for x in range(messages_to_send):
            msg = "Failed to send message {x}".format(x=x)
            self.assertTrue(self.driver.send(msg1), msg)

        self.assertEqual(self.driver.life_time_sent(), messages_to_send)

    def Receive(self):
        messages_to_receive = int(random.random() * 100) + 1

        # Check that the life time received hasn't been updated yet
        self.assertEqual(self.driver.life_time_received(), 0)

        # Read back the random number of messages and check that the lifetime
        # values track the next_message call
        read_messages = 0
        for x in range(messages_to_receive):
            if self.driver.next_message():
                self.assertEqual((x+1), self.driver.life_time_received())


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(SimCANTests)
    unittest.TextTestRunner(verbosity=2).run(suite)
