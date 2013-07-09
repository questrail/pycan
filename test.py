import os
import unittest
from basedriver import *

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
        basedriver = os.path.abspath('drivers/basedriver.py')
        pep8_checker = pep8.Checker(basedriver)
        violation_count = pep8_checker.check_all()
        error_message = "PEP8 violations found: %d" % (violation_count)
        self.assertTrue(violation_count == 0, msg = error_message)


    def testAddReceiveHandler(self):
        self.driver = BaseDriver(max_in=500, max_out=500, loopback=False)

        def test_handler(message):
            pass

        self.driver.add_receive_handler(test_handler)

        self.assertIn(None, self.driver._receive_handlers,
                        msg="Unable to add a generic handler")

        can_id = 0x12345
        self.driver.add_receive_handler(test_handler, can_id)
        self.assertIn(can_id, self.driver._receive_handlers,
                        msg="Unable to add an ID specific handler")
        self.assertTrue(len(self.driver._receive_handlers[can_id]) == 1,
                    msg="Handler was added in the wrong place")

        self.driver.add_receive_handler(test_handler, can_id)
        self.assertTrue(len(self.driver._receive_handlers[can_id]) == 2,
                    msg="Unable to add matching ID's")

        can_id_2 = 0x123456
        self.driver.add_receive_handler(test_handler, can_id_2)
        self.assertIn(can_id_2, self.driver._receive_handlers,
                    msg="Unable to add multiple specific handlers")

        self.assertTrue(len(self.driver._receive_handlers[can_id_2]) == 1,
                    msg="Handler was added in the wrong place")

        self.assertTrue(len(self.driver._receive_handlers) == 3,
                    msg="Expected unique handlers did not match")


    def testMessageQueues(self):
        self.driver = BaseDriver(max_in=2, max_out=2, loopback=False)

        msg1 = CANMessage(0x123, 2, [1,2])
        msg2 = CANMessage(0x1234, 3, [1,2,3])

        self.assertTrue(self.driver.send(msg1))
        self.assertTrue(self.driver.send(msg2))
        self.assertTrue(self.driver.outbound.qsize() == 2, msg="Message not added to outbound queue")
        self.assertTrue(self.driver.inbound.qsize() == 0, msg="Loopback placed a message in the queue" )

        self.assertFalse(self.driver.send(msg1), msg="Max outbound queue size not honored")
        self.assertTrue(self.driver.outbound.qsize() == 2, msg="Max outbound queue size not honored")
        self.assertTrue(self.driver.inbound.qsize() == 0, msg="Loopback placed a message in the queue" )



    def testMessageLoopback(self):
        self.driver = BaseDriver(max_in=5, max_out=2, loopback=True)

        msg1 = CANMessage(0x123, 2, [1,2])
        msg2 = CANMessage(0x1234, 3, [1,2,3])

        self.assertTrue(self.driver.send(msg1))
        self.assertTrue(self.driver.send(msg2))
        self.assertTrue(self.driver.outbound.qsize() == 2,
                        msg="Message not added to outbound queue")

        self.assertTrue(self.driver.inbound.qsize() == 2,
                        msg="Loopback didn't add message to inbound: %d" %self.driver.inbound.qsize() )

        self.assertFalse(self.driver.send(msg1))
        self.assertTrue(self.driver.outbound.qsize() == 2,
                        msg="Max outbound queue size not honored")

        self.assertTrue(self.driver.inbound.qsize() == 2,
                        msg="Loopback still placed the message in the outbound: %d" % self.driver.inbound.qsize())



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

    def testCyclicAdd(self):
        self.driver = BaseDriver(max_in=500, max_out=500, loopback=False)

        msg1 = CANMessage(1, 1, [1])
        msg2 = CANMessage(2, 2, [2])

        # Add and start some cyclic messages
        self.assertTrue(self.driver.add_cyclic_message(msg1, .1), msg="Unable to add cyclic message")
        self.assertTrue(self.driver.add_cyclic_message(msg2, .1, "ETC2"), msg="Unable to add cyclic message")

        time.sleep(1) # allow time for the cyclic messages to send
        qsize = self.driver.outbound.qsize()
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
