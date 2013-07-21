# -*- coding: utf-8 -*-
# Copyright (c) 2013 The pycan developers. All rights reserved.
# Project site: https://github.com/questrail/pycan
# Use of this source code is governed by a MIT-style license that
# can be found in the LICENSE.txt file for the project.
import os
import time
import threading
import unittest
import pycan.sim_can
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
        driver_path = os.path.dirname(pycan.sim_can.__file__)
        driver_file = os.path.abspath(os.path.join(driver_path, 'sim_can.py'))
        pep8_checker = pep8.Checker(driver_file)
        violation_count = pep8_checker.check_all()
        error_message = "PEP8 violations found: %d" % (violation_count)
        self.assertTrue(violation_count == 0, msg = error_message)

    def testDriver(self):
        # Setup the driver
        self.driver = pycan.sim_can.SimCAN(verbose=False)

        # Run the driver specific tests if and only if the driver was setup
        self.Transmit()
        self.CyclicTransmit()
        self.GenericReceive()

    def Transmit(self):
        msg1 = CANMessage(0x123456, [1,2,3])
        self.assertTrue(self.driver.send(msg1))
        self.assertEqual(self.driver.total_outbound_count, 1)

    def CyclicTransmit(self):
        msg1 = CANMessage(0x123456, [1,2,3])
        msg2 = CANMessage(0x123456, [5,6,7,8])

        # Turn on verbose to make sure we see the messages
        self.driver.verbose = True
        self.assertTrue(self.driver.add_cyclic_message(msg1, .1, "Sample"))
        # Watch the CAN bus (screen) to ensure the messages are being sent
        time.sleep(3)
        self.assertTrue(self.driver.update_cyclic_message(msg2, "Sample"))
        # Watch the CAN bus (screen) to ensure the message change happened
        time.sleep(3)

    def GenericReceive(self):
        expected = 10
        events = []
        for x in range(expected):
            events.append(threading.Event())
            events[-1].clear()

        def gen_handler(msg):
            # Walk down the number of events marking them as
            # each new message is received
            for event in events:
                if not event.isSet():
                    event.set()
                    print msg
                    break;

        self.driver.add_receive_handler(gen_handler)

        # wait for at least 1 second for each message
        for event in events:
            event.wait(1)

        # Determine how many messages were in fact recorded
        actual = 0
        for event in events:
            msg="Expected %d, receved %d" % (expected, actual)
            self.assertTrue(event.isSet(), msg)
            actual += 1


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(SimCANTests)
    unittest.TextTestRunner(verbosity=2).run(suite)
