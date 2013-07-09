import unittest
import Queue
import thread
import threading
import time

QUEUE_DELAY = .005

'''
TODO List:
    1) Add Alarm flags
    2) Add Logger

'''


class Operation(threading._Timer):
    def __init__(self, *args, **kwargs):
        threading._Timer.__init__(self, *args, **kwargs)
        self.setDaemon(True)

    def run(self):
        while True:
            self.finished.clear()
            self.finished.wait(self.interval)
            if not self.finished.isSet():
                self.function(*self.args, **self.kwargs)
            else:
                return
            self.finished.set()


class Manager(object):
    ops = {}

    def add_operation(self, operation, interval, args=[], kwargs={}):
        op = Operation(interval, operation, args, kwargs)
        new_id = thread.start_new_thread(op.run, ())
        self.ops[new_id] = op
        return new_id

    def stop(self, op_id=None):
        if op_id is None:
            # Stop them all
            for op_id, op in self.ops.items():
                op.cancel()
                while op.isAlive():
                    time.sleep(.05)

            self.ops.clear()
        else:
            if op_id in self.ops:
                op = self.ops.pop(op_id)
                op.cancel()
                while op.isAlive():
                    time.sleep(.05)


class CANMessage():
    def __init__(self, id, dlc, payload, extended=True, ts=0):
        self.id = id
        self.dlc = dlc
        self.payload = payload
        self.extended = extended
        self.time_stamp = ts

    def __str__(self):
        return "%s,%d : %s" % (hex(self.id), self.dlc, str(self.payload))


class BaseDriver(object):
    def __init__(self, max_in=500, max_out=500, loopback=False):
        self.total_inbound_count = 0
        self.inbound = Queue.Queue(max_in)
        self.total_outbound_count = 0
        self.outbound = Queue.Queue(max_out)
        self.loopback = loopback

        self._msg_lock = threading.Lock()
        self._handle_lock = threading.Lock()
        self._receive_handlers = {}
        self._running = threading.Event()

        self._cyclic_messages = {}
        self._cyclic_rates = {}
        self._cyclic_events = {}

        self.scheduler = Manager()
        self.scheduler.add_operation(self.__monitor, 0)

    def wait_for_message(self, can_id, timeout=None, ext=True):
        pass
        # Blocking call to wait for a specific message

    def add_receive_handler(self, handler, can_id=None, ext=True):
        with self._handle_lock:
            self._receive_handlers[handler] = (can_id, ext)

        return True

    def remove_receive_handler(self, handler):
        with self._handle_lock:
            self._receive_handlers.pop(handler)

        return True

    def add_cyclic_message(self, message, rate, desc=None):
        with self._msg_lock:
            if desc is None:
                desc = message.id

            try:
                # Update / Add new messages
                self._cyclic_messages[desc] = message
                self._cyclic_rates[desc] = rate
                event = self.scheduler.add_operation(self.__send_cyclic,
                                                     self._cyclic_rates[desc],
                                                     [desc])

                self._cyclic_events[desc] = event

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
                self._cyclic_messages[desc] = message

                return True
            else:
                return False

    def stop_cyclic_message(self, desc):
        with self._msg_lock:
            if desc in self._cyclic_messages:
                scheduled_event = self._cyclic_events.pop(desc)
                self.scheduler.stop(scheduled_event)

                self._cyclic_messages.pop(desc)
                self._cyclic_rates.pop(desc)
                return True
            else:
                return False

    def send(self, message):
        with self._msg_lock:
            try:
                # Attempt to push the message onto the queue
                self.outbound.put(message, timeout=QUEUE_DELAY)
                self.total_outbound_count += 1
                # Push the message onto the inbound queue
                if self.loopback:
                    try:
                        self.inbound.put(message, timeout=QUEUE_DELAY)
                    except Queue.Full:
                        # TODO: Should this report a true failure?
                        return False
                        pass

                return True

            except Queue.Full:
                return False

    def shutdown(self):
        self.scheduler.stop()

    def __send_cyclic(self, id_to_use):
        self.send(self._cyclic_messages[id_to_use])

    def __monitor(self):
        try:
            # Check the Queue for a new message, throttled by timeout
            new_msg = self.inbound.get(timeout=QUEUE_DELAY)
            self.total_inbound_count += 1
        except Queue.Empty:
            # Keep waiting
            return

        # Inform the ID specific handlers
        for handler, key in self._receive_handlers.items():
            can_id, ext = key

            if new_msg.id == can_id or can_id is None:
                if new_msg.extended == ext:
                    handler(new_msg)
