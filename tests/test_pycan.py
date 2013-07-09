import os
import unittest
from pycan.basedriver import *

def measure_performance(driver, rate, run_time=3.0):
    expected_counts = run_time / rate
    tic = time.time()
    t_stats = []
    obc = 0
    while driver.total_outbound_count < expected_counts:
        if obc != driver.total_outbound_count:
            toc = time.time()
            t_stats.append(toc - tic)
            tic = toc
            obc = driver.total_outbound_count

    ret = (max(t_stats)*1000.0, min(t_stats)*1000.0, (sum(t_stats) / float(len(t_stats))) * 1000.0)
    print "\nTarget:%1.1f (ms)\nMax %1.1f\nMin %1.1f\nAvg %1.1f" % (rate*1000.0, ret[0], ret[1], ret[2])
    return ret


class CANDriverTests(unittest.TestCase):
    def setUp(self):
        self.driver = None

    def tearDown(self):
        try:
            self.driver.shutdown()
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
        basedriver = os.path.abspath('basedriver.py')
        pep8_checker = pep8.Checker(basedriver)
        violation_count = pep8_checker.check_all()
        error_message = "PEP8 violations found: %d" % (violation_count)
        self.assertTrue(violation_count == 0, msg = error_message)


    def testAddReceiveHandler(self):
        self.driver = BaseDriver(max_in=500, max_out=500, loopback=False)

        def test_handler(message):
            pass

        self.assertTrue(self.driver.add_receive_handler(test_handler),
                        msg="Unable to add a generic handler")

        can_id = 0x12345
        self.assertTrue(self.driver.add_receive_handler(test_handler, can_id),
                        msg="Unable to add an ID specific handler")

        can_id_2 = 0x123456
        self.assertTrue(self.driver.add_receive_handler(test_handler, can_id_2),
                    msg="Unable to add multiple specific handlers")

    def testMessageQueues(self):
        self.driver = BaseDriver(max_in=2, max_out=2, loopback=False)

        msg1 = CANMessage(0x123, 2, [1,2])
        msg2 = CANMessage(0x1234, 3, [1,2,3])

        self.assertTrue(self.driver.send(msg1))
        self.assertTrue(self.driver.send(msg2))
        time.sleep(.5)  # Allow time for the queue to be processed
        self.assertTrue(self.driver.total_outbound_count == 2, msg="Message not added to outbound queue")
        self.assertTrue(self.driver.total_inbound_count == 0, msg="Loopback placed a message in the queue" )

        self.assertFalse(self.driver.send(msg1), msg="Max outbound queue size not honored")
        time.sleep(.5)  # Allow time for the queue to be processed
        self.assertTrue(self.driver.total_outbound_count == 2, msg="Max outbound queue size not honored")
        self.assertTrue(self.driver.total_inbound_count == 0, msg="Loopback placed a message in the queue" )

    def testMessageLoopback(self):
        self.driver = BaseDriver(max_in=5, max_out=2, loopback=True)

        msg1 = CANMessage(0x123, 2, [1,2])
        msg2 = CANMessage(0x1234, 3, [1,2,3])

        self.assertTrue(self.driver.send(msg1))
        self.assertTrue(self.driver.send(msg2))
        self.assertTrue(self.driver.total_outbound_count == 2,
                        msg="Message not added to outbound queue")

        time.sleep(.5)  # Allow time for the queue to be processed

        self.assertTrue(self.driver.total_inbound_count == 2,
                        msg="Loopback didn't add message to inbound: %d" %self.driver.total_inbound_count )

        self.assertFalse(self.driver.send(msg1))
        self.assertTrue(self.driver.total_outbound_count == 2,
                        msg="Max outbound queue size not honored")

        time.sleep(.5)  # Allow time for the queue to be processed

        self.assertTrue(self.driver.total_inbound_count == 2,
                        msg="Loopback still placed the message in the outbound: %d" % self.driver.total_inbound_count)

    def testQueueMonitor(self):
        self.driver = BaseDriver(max_in=500, max_out=500, loopback=False)

        msg1 = CANMessage(0x123, 2, [1,2])
        msg2 = CANMessage(0x1234, 3, [1,2,3])
        msg3 = CANMessage(0x12345, 4, [1,2,3,4])

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
        self.driver.add_receive_handler(msg1_handler, msg1.id)
        self.driver.add_receive_handler(msg2_handler, msg2.id)
        self.driver.add_receive_handler(msg3_handler, msg3.id)
        self.driver.add_receive_handler(gen_handler)

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
        self.driver = BaseDriver(max_in=500, max_out=500, loopback=False)

        msg1 = CANMessage(1, 1, [1])

        # Add and start some cyclic messages
        rate = 1
        self.assertTrue(self.driver.add_cyclic_message(msg1, rate), msg="Unable to add cyclic message")

        max_t, min_t, avg_t = measure_performance(self.driver, rate, 10.0)

        uTarget = (rate * 1.02) * 1000.0
        lTarget = (rate * 0.98) * 1000.0
        self.assertTrue(lTarget < avg_t < uTarget, msg="Avg time (%1.1f) expected to be between %1.1f and %1.1f" % (avg_t, uTarget, lTarget))

        target = (rate * 1.05) * 1000.0
        self.assertTrue(max_t < target, msg="Max time (%1.1f) expected to be less than %1.1f" % (max_t, target))

        target = (rate * 0.95) * 1000.0
        self.assertTrue(max_t < target, msg="Min time (%1.1f) expected to be greater than %1.1f" % (min_t, target))

    def testCyclicPerformance_100ms(self):
        self.driver = BaseDriver(max_in=500, max_out=500, loopback=False)

        msg1 = CANMessage(1, 1, [1])

        # Add and start some cyclic messages
        rate = .1
        self.assertTrue(self.driver.add_cyclic_message(msg1, rate), msg="Unable to add cyclic message")

        max_t, min_t, avg_t = measure_performance(self.driver, rate, 2.0)

        uTarget = (rate * 1.02) * 1000.0
        lTarget = (rate * 0.98) * 1000.0
        self.assertTrue(lTarget < avg_t < uTarget, msg="Avg time (%1.1f) expected to be between %1.1f and %1.1f" % (avg_t, uTarget, lTarget))

        target = (rate * 1.05) * 1000.0
        self.assertTrue(max_t < target, msg="Max time (%1.1f) expected to be less than %1.1f" % (max_t, target))

        target = (rate * 0.95) * 1000.0
        self.assertTrue(max_t < target, msg="Min time (%1.1f) expected to be greater than %1.1f" % (min_t, target))


    def testCyclicPerformance_10ms(self):
        self.driver = BaseDriver(max_in=500, max_out=500, loopback=False)

        msg1 = CANMessage(1, 1, [1])

        # Add and start some cyclic messages
        rate = .01
        self.assertTrue(self.driver.add_cyclic_message(msg1, rate), msg="Unable to add cyclic message")

        max_t, min_t, avg_t = measure_performance(self.driver, rate, 2.0)

        uTarget = (rate * 1.02) * 1000.0
        lTarget = (rate * 0.98) * 1000.0
        self.assertTrue(lTarget < avg_t < uTarget, msg="Avg time (%1.1f) expected to be between %1.1f and %1.1f" % (avg_t, uTarget, lTarget))

        target = (rate * 1.05) * 1000.0
        self.assertTrue(max_t < target, msg="Max time (%1.1f) expected to be less than %1.1f" % (max_t, target))

        target = (rate * 0.95) * 1000.0
        self.assertTrue(max_t < target, msg="Min time (%1.1f) expected to be greater than %1.1f" % (min_t, target))


    def testCyclicAdd(self):
        self.driver = BaseDriver(max_in=500, max_out=500, loopback=False)

        msg1 = CANMessage(1, 1, [1])
        msg2 = CANMessage(2, 2, [2])

        # Add and start some cyclic messages
        self.assertTrue(self.driver.add_cyclic_message(msg1, .1), msg="Unable to add cyclic message")
        self.assertTrue(self.driver.add_cyclic_message(msg2, .1, "ETC2"), msg="Unable to add cyclic message")

        time.sleep(1) # allow time for the cyclic messages to send
        qsize = self.driver.total_outbound_count
        self.assertTrue(qsize > 17, msg="Q Size: %d" % qsize)

        self.assertTrue(self.driver.stop_cyclic_message(msg1.id), msg="Unable to stop cyclic message")
        self.assertTrue(self.driver.stop_cyclic_message("ETC2"), msg="Unable to stop cyclic message")
        time.sleep(2)

    def testCyclicOperation(self):
        self.driver = BaseDriver(max_in=500, max_out=500, loopback=True)

        msg1_evt = threading.Event()
        msg1_evt.clear()

        msg2_evt = threading.Event()
        msg2_evt.clear()

        msg3_evt = threading.Event()
        msg3_evt.clear()


        msg1 = CANMessage(1, 1, [1])
        msg2 = CANMessage(2, 2, [1,2])
        msg3 = CANMessage(2, 2, [3,4])

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

        time.sleep(.5) # allow time for the cyclic messages to send

        # Update message 2 payload
        self.assertTrue(self.driver.update_cyclic_message(msg3, "Message 2"), msg="Unable to update cyclic message")

        time.sleep(.5) # allow time for the cyclic messages to send

        # Ensure messages were sent out
        self.assertTrue(msg1_evt.isSet(), msg="Message 1 not received")
        self.assertTrue(msg2_evt.isSet(), msg="Message 2 not received")
        self.assertTrue(msg3_evt.isSet(), msg="Message 2 not updated")

        self.assertTrue(self.driver.stop_cyclic_message("Message 1"), msg="Unable to stop cyclic message")
        self.assertTrue(self.driver.stop_cyclic_message("Message 2"), msg="Unable to stop cyclic message")

        # Allow some time for the cyclic message to shut down
        time.sleep(2)

if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(CANDriverTests)
    unittest.TextTestRunner(verbosity=2).run(suite)

