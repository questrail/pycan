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
import pycan.canusb
from pycan.common import CANMessage

class CANUSBTests(unittest.TestCase):
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
        self.com_port = config.get('CANUSB', 'Comm_Port')

    def testPEP8Compliance(self):
        # Ensure PEP8 is installed
        try:
            import pep8
        except ImportError:
            self.fail(msg="PEP8 not installed.")

        # Check the CAN driver
        driver_path = os.path.dirname(pycan.canusb.__file__)
        driver_file = os.path.abspath(os.path.join(driver_path, 'canusb.py'))
        pep8_checker = pep8.Checker(driver_file)
        violation_count = pep8_checker.check_all()
        error_message = "PEP8 violations found: %d" % (violation_count)
        self.assertTrue(violation_count == 0, msg = error_message)

    def testDriver(self):
        # Load the real time test configuration
        self.__load_test_config()

        # Setup the driver
        self.driver = pycan.canusb.CANUSB(com_port=self.com_port)

        # Run the driver specific tests if and only if the driver was setup
        self.Transmit()
        self.CyclicTransmit()
        self.GenericReceive()
        self.SpecificReceive()


    def Transmit(self):
        msg1 = CANMessage(0x123456, [1,2,3], False)
        self.assertTrue(self.driver.send(msg1))
        self.assertEqual(self.driver.total_outbound_count, 1)

    def CyclicTransmit(self):
        msg1 = CANMessage(0x123456, [1,2,3], False)
        msg2 = CANMessage(0x123456, [5,6,7,8], False)

        self.assertTrue(self.driver.add_cyclic_message(msg1, .1, "Sample"))
        time.sleep(5) # Watch the CAN bus to ensure the messages are being sent
        self.assertTrue(self.driver.update_cyclic_message(msg2, "Sample"))
        time.sleep(5) # Watch the CAN bus to ensure the messages changed and are being sent
        self.assertTrue(self.driver.update_cyclic_message(msg1, "Sample"))
        time.sleep(5)

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

    def SpecificReceive(self):
        expected = 10
        events = []
        for x in range(expected):
            events.append(threading.Event())
            events[-1].clear()

        def msg_handler(msg):
            # Walk down the number of events marking them as
            # each new message is received
            for event in events:
                if not event.isSet():
                    event.set()
                    print msg
                    break;

        self.driver.add_receive_handler(msg_handler, self.known_can_id)

        # Wait for all of the messages to arrive
        for event in events:
            event.wait(1)

        # Determine how many messages were in fact recorded
        actual = 0
        for event in events:
            msg="Expected %d, receved %d" % (expected, actual)
            self.assertTrue(event.isSet(), msg)
            actual += 1

if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(CANUSBTests)
    unittest.TextTestRunner(verbosity=2).run(suite)

