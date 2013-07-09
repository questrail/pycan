'''
External Python Dependancies:
Hardware Requirements:
Driver Requirements:
'''

# Test dependencies
import time
import unittest
import threading

# Driver dependencies
import Queue
from basedriver import *
from ctypes import *

CAN_TX_TIMEOUT = 100 # ms
CAN_RX_TIMEOUT = 100 # ms

class KvaserDriver(BaseDriver):
    def __init__(self, **kwargs):
        # Init the base driver
        super(KvaserDriver, self).__init__(max_in=500, max_out=500, loopback=False)

        # Init the Leaf Light HS DLL
        windll.canlib32.canInitializeLibrary()

        # Open a CAN communication channel
        self._can_channel = windll.canlib32.canOpenChannel(c_int(0), c_int8(0))
        # todo: print out error text if can_channel < 0

        # Bus on and clear the hardware queues
        windll.canlib32.canBusOn(c_int(self._can_channel))
        windll.canlib32.canFlushReceiveQueue(c_int(self._can_channel))
        windll.canlib32.canFlushTransmitQueue(c_int(self._can_channel))

        # Set the default paramters
        self.update_bus_parameters()

        # Add the inbound and outbound processes to the BaseDriver's scheduler
        self.scheduler.add_operation(self.__process_outbound_queue, 0)
        self.scheduler.add_operation(self.__process_inbound_queue, 0)

    def update_bus_parameters(self, **kwargs):
        # Default values are setup for a 250k connetion with a 75% sample point
        # Set up the timing parameters for the CAN controller
        windll.canlib32.canSetBusParams( c_int(self._can_channel),    # handle
                                c_int(kwargs.get("baud", 250000)),     # freq
                                c_uint(kwargs.get("tseg1", 5)),        # tseg1
                                c_uint(kwargs.get("tseg2", 2)),        # tseg2
                                c_uint(kwargs.get("sjw", 2)),          # sjw
                                c_uint(kwargs.get("sample_count", 1)), # noSamp
                                c_uint(0))

    def __process_outbound_queue(self):
        try:
            # Read the Queue - allow the timeout to throttle the thread
            can_msg = self.outbound.get(timeout=QUEUE_DELAY)
        except Queue.Empty:
            # Kick out and wait for the next call from the scheduler
            return

        tx_data = (c_uint8 * can_msg.dlc)()
        for x in range(can_msg.dlc):
            tx_data[x] = can_msg.payload[x]

        if can_msg.extended: ext = 4
        else: ext = 2

        status = windll.canlib32.canWriteWait( c_int(self._can_channel),
                                      c_uint32(can_msg.id),
                                      pointer(tx_data),
                                      c_int(can_msg.dlc),# dlc
                                      c_int(ext),        # ext
                                      c_uint32(CAN_TX_TIMEOUT))
        # TODO: Flag error status

    def __process_inbound_queue(self):
        rx_id = c_uint(0)
        rx_dlc = c_uint(0)
        rx_flags = c_uint(0)
        rx_time = c_uint(0)
        rx_msg = (c_uint8 * 8)()

        status = windll.canlib32.canReadWait( c_int(self._can_channel),
                                     pointer(rx_id),
                                     pointer(rx_msg),
                                     pointer(rx_dlc),
                                     pointer(rx_flags),
                                     pointer(rx_time),
                                     c_uint32(CAN_RX_TIMEOUT))

        if status < 0:
            pass
            #TODO: Flag error

        else:
            # Build the message
            new_msg = CANMessage(rx_id.value, rx_dlc.value, rx_msg)

            try: # Push the message into the inbound queue
                self.inbound.put(new_msg, timeout=QUEUE_DELAY)
            except Queue.Full:
                # TODO: flag error
                pass


class KvaserTests(unittest.TestCase):
    KNOWN_ID_ON_BUS = 0x18F00506
    def setUp(self):
        self.driver = None

    def tearDown(self):
        try:
            self.driver.shutdown()
            time.sleep(2)
        except:
            pass

    def testTransmit(self):
        self.driver = KvaserDriver()
        msg1 = CANMessage(0x123456, 3, [1,2,3])
        # Watch the CAN bus to ensure the message was sent
        self.assertTrue(self.driver.send(msg1))

    def testCyclicTransmit(self):
        self.driver = KvaserDriver()
        msg1 = CANMessage(0x123456, 3, [1,2,3])
        msg2 = CANMessage(0x123456, 4, [5,6,7,8])

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

        self.driver = KvaserDriver()
        print ''

        def gen_handler(msg):
            # Walk down the number of events marking them as
            # each new message is received
            for event in events:
                if not event.isSet():
                    event.set()
                    print msg
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

        self.driver = KvaserDriver()
        print ''

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
    suite = unittest.TestLoader().loadTestsFromTestCase(KvaserTests)
    unittest.TextTestRunner(verbosity=2).run(suite)

