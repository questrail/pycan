# -*- coding: utf-8 -*-
# Copyright (c) 2013 The pycan developers. All rights reserved.
# Project site: https://github.com/questrail/pycan
# Use of this source code is governed by a MIT-style license that
# can be found in the LICENSE.txt file for the project.
import os
import unittest
import time
import threading
from pycan.drivers.sim_can import SimCAN
from pycan.tools.cyclic_comm import CyclicComm
from pycan.common import CANMessage

def measure_performance(driver, rate, run_time=3.0):
    expected_counts = run_time / rate
    tic = time.time()
    t_stats = []
    obc = 0
    while driver.life_time_sent() < expected_counts:
        if obc != driver.life_time_sent():
            toc = time.time()
            t_stats.append(toc - tic)
            tic = toc
            obc = driver.life_time_sent()

    ret = (max(t_stats)*1000.0, min(t_stats)*1000.0, (sum(t_stats) / float(len(t_stats))) * 1000.0)
    print "\nTarget:%1.1f (ms)\nMax %1.1f\nMin %1.1f\nAvg %1.1f" % (rate*1000.0, ret[0], ret[1], ret[2])
    return ret

class CyclicCommTests(unittest.TestCase):
    def setUp(self):
        self.driver = None
        self.cyc = None

    def tearDown(self):
        try:
            self.driver.shutdown()
            time.sleep(1)
        except:
            pass
        try:
            self.cyc.shutdown()
            time.sleep(1)
        except:
            pass

    def testPEP8Compliance(self):
        # Ensure PEP8 is installed
        try:
            import pep8
        except ImportError:
            self.fail(msg="PEP8 not installed.")

        # Check the CAN driver
        source_file = os.path.abspath('pycan/tools/cyclic_comm.py')
        pep8_checker = pep8.Checker(source_file)
        violation_count = pep8_checker.check_all()
        error_message = "PEP8 violations found: %d" % (violation_count)
        self.assertTrue(violation_count == 0, msg = error_message)


    def testAddReceiveHandler(self):
        self.driver = SimCAN(max_in=500, max_out=500, loopback=False)
        self.cyc = CyclicComm(self.driver)

        def test_handler(message):
            pass

        self.assertTrue(self.cyc.add_receive_handler(test_handler),
                        msg="Unable to add a generic handler")

        can_id = 0x12345
        self.assertTrue(self.cyc.add_receive_handler(test_handler, can_id),
                        msg="Unable to add an ID specific handler")

        can_id_2 = 0x123456
        self.assertTrue(self.cyc.add_receive_handler(test_handler, can_id_2),
                    msg="Unable to add multiple specific handlers")

        can_id_3 = 0x123456
        self.assertTrue(self.cyc.add_receive_handler(test_handler, can_id_2, False),
                    msg="Unable to add multiple specific handlers")

    def testReceiveHandlers(self):
        self.driver = SimCAN(max_in=500, max_out=500, loopback=False)
        self.cyc = CyclicComm(self.driver)

        msg1 = CANMessage(0x123, [1,2])
        msg2 = CANMessage(0x1234, [1,2,3])
        msg3 = CANMessage(0x12345, [1,2,3,4])

        spec_event1 = threading.Event()
        spec_event1.clear()
        spec_event2 = threading.Event()
        spec_event2.clear()
        spec_event3 = threading.Event()
        spec_event3.clear()
        gen_event1 = threading.Event()
        gen_event1.clear()
        gen_event2 = threading.Event()
        gen_event2.clear()
        gen_event3 = threading.Event()
        gen_event3.clear()

        def msg1_handler(message):
            if msg1 is message:
                spec_event1.set()

        def msg2_handler(message):
            if msg2 is message:
                spec_event2.set()

        def msg3_handler(message):
            if msg3 is message:
                spec_event3.set()

        def gen_handler(message):
            if msg1 is message:
                gen_event1.set()

            if msg2 is message:
                gen_event2.set()

            if msg3 is message:
                gen_event3.set()

        # Add the handlers
        self.cyc.add_receive_handler(msg1_handler, msg1.id)
        self.cyc.add_receive_handler(msg2_handler, msg2.id)
        self.cyc.add_receive_handler(msg3_handler, msg3.id)
        self.cyc.add_receive_handler(gen_handler)

        # Force messages in the inbound queue
        self.driver.inbound.put(msg1)
        self.driver.inbound.put(msg2)
        self.driver.inbound.put(msg3)

        # Allow some time for the messages to be processed
        time.sleep(1)

        # Check the specific handlers
        self.assertTrue(spec_event1.isSet(), msg="Message 1 specific handler failed")
        self.assertTrue(spec_event2.isSet(), msg="Message 2 specific handler failed")
        self.assertTrue(spec_event3.isSet(), msg="Message 3 specific handler failed")

        # Check the generic handler
        self.assertTrue(gen_event1.isSet(), msg="Message 1 generic handler failed")
        self.assertTrue(gen_event2.isSet(), msg="Message 2 generic handler failed")
        self.assertTrue(gen_event3.isSet(), msg="Message 3 generic handler failed")

    def testCyclicPerformance_1000ms(self):
        self.driver = SimCAN(max_in=500, max_out=500, loopback=False)
        self.cyc = CyclicComm(self.driver)
        self.__performance_test(self.cyc, 1, 5.0, [1.75, 1.00, 1.5])

    def testCyclicPerformance_100ms(self):
        self.driver = SimCAN(max_in=500, max_out=500, loopback=False)
        self.cyc = CyclicComm(self.driver)
        self.__performance_test(self.cyc, .1, 5.0, [1.00, .1, .175])

    def testCyclicPerformance_10ms(self):
        self.driver = SimCAN(max_in=500, max_out=500, loopback=False)
        self.cyc = CyclicComm(self.driver)
        self.__performance_test(self.cyc, .01, 5.0, [.5, .01, .075])


    def testCyclicAdd(self):
        self.driver = SimCAN(max_in=500, max_out=500, loopback=False)
        self.cyc = CyclicComm(self.driver)

        msg1 = CANMessage(1, [1])
        msg2 = CANMessage(2, [1,2])

        # Add and start some cyclic messages
        self.assertTrue(self.cyc.add_cyclic_message(msg1, .1), msg="Unable to add cyclic message")
        self.assertTrue(self.cyc.add_cyclic_message(msg2, .1, "ETC2"), msg="Unable to add cyclic message")

        time.sleep(1) # allow time for the cyclic messages to send
        qsize = self.driver.life_time_sent()
        self.assertTrue(qsize > 10, msg="Q Size: %d" % qsize)

        self.assertTrue(self.cyc.stop_cyclic_message(msg1.id), msg="Unable to stop cyclic message")
        self.assertTrue(self.cyc.stop_cyclic_message("ETC2"), msg="Unable to stop cyclic message")

    def testCyclicOperation(self):
        self.driver = SimCAN(max_in=500, max_out=500, loopback=False)
        self.cyc = CyclicComm(self.driver)

        msg1_evt = threading.Event()
        msg1_evt.clear()

        msg2_evt = threading.Event()
        msg2_evt.clear()

        msg3_evt = threading.Event()
        msg3_evt.clear()


        msg1 = CANMessage(1, [1])
        msg2 = CANMessage(2, [1,2])
        msg3 = CANMessage(2, [3,4])

        def msg1_handler(message):
            if msg1 is message:
                msg1_evt.set()

        def msg2_handler(message):
            if msg2 is message:
                msg2_evt.set()
            elif msg3 is message:
                msg3_evt.set()

        # Add the message handlers
        self.driver.add_receive_handler(msg1_handler, msg1.id)
        self.driver.add_receive_handler(msg2_handler, msg2.id)

        # Add and start some cyclic messages
        self.assertTrue(self.driver.add_cyclic_message(msg1, .1, "Message 1"), msg="Unable to add cyclic message")
        self.assertTrue(self.driver.add_cyclic_message(msg2, .1, "Message 2"), msg="Unable to add cyclic message")

        # Wait for the cyclic messages to send
        msg1_evt.wait(5.0)
        msg2_evt.wait(5.0)

        # Update message 2 payload
        self.assertTrue(self.driver.update_cyclic_message(msg3, "Message 2"), msg="Unable to update cyclic message")

        # Wait for the cyclic messages to send
        msg3_evt.wait(5.0)

        # Ensure messages were sent out
        self.assertTrue(msg1_evt.isSet(), msg="Message 1 not received")
        self.assertTrue(msg2_evt.isSet(), msg="Message 2 not received")
        self.assertTrue(msg3_evt.isSet(), msg="Message 2 not updated")

        self.assertTrue(self.driver.stop_cyclic_message("Message 1"), msg="Unable to stop cyclic message")
        self.assertTrue(self.driver.stop_cyclic_message("Message 2"), msg="Unable to stop cyclic message")

    def __performance_test(self, driver, rate, run_time, tolerances):
        # Determine the upper and lower bounds based on the tolerance in seconds
        uTarget, lTarget, aTarget = tolerances

        # Scale the seconds to miliseconds
        uTarget *= 1000.0
        lTarget *= 1000.0
        aTarget *= 1000.0

        msg1 = CANMessage(1, [1])

        # Add and start some cyclic messages
        self.assertTrue(self.driver.add_cyclic_message(msg1, rate), msg="Unable to add cyclic message")

        max_t, min_t, avg_t = measure_performance(driver, rate, run_time)

        self.assertTrue(lTarget < avg_t < uTarget, msg="Avg time (%1.1f) expected to be between %1.1f and %1.1f" % (avg_t, uTarget, lTarget))
        self.assertTrue(max_t < uTarget, msg="Max time (%1.1f) expected to be less than %1.1f" % (max_t, uTarget))
        self.assertTrue(min_t > lTarget, msg="Min time (%1.1f) expected to be greater than %1.1f" % (min_t, lTarget))


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(CANDriverTests)
    unittest.TextTestRunner(verbosity=2).run(suite)

