# -*- coding: utf-8 -*-
# Copyright (c) 2013 The pycan developers. All rights reserved.
# Project site: https://github.com/questrail/pycan
# Use of this source code is governed by a MIT-style license that
# can be found in the LICENSE.txt file for the project.
"""CAN Playback Module

Module used to play back a given CAN file logged using various
off the shelf tools or pycan's logging module
"""
import time
import sys
import threading


class TracePlayer(object):
    PLAYING = "Playing"
    STOPPED = "Stopped"
    PAUSED = "Paused"

    def __init__(self, driver, parser, files=[], use_wall_time=True):
        self.use_wall_time = use_wall_time
        self.driver = driver
        self.parser = parser
        self.next_message = None
        self.last_stamp = 0
        self.play_time = 0
        self.files = files
        self.playing = threading.Event()
        self.paused = threading.Event()
        self.shutdown = threading.Event()

        self.files_lock = threading.Lock()
        self.state = self.STOPPED

        self._fp_thread = threading.Thread(target=self.__file_player)
        self._fp_thread.daemon = True
        self._fp_thread.start()

    def load_file(self, file_path):
        # Stop the player
        self.stop()

        # Add the new file
        with self.files_lock:
            self.files.append(file_path)

    def shutdown(self):
        self.stop()
        self.shutdown.set()

    def select_file(self):
        # TODO: Add a file selection GUI
        pass

    def play(self):
        self.playing.set()
        self.paused.clear()
        self.state = self.PLAYING

    def stop(self):
        self.playing.clear()
        self.paused.clear()
        self.state = self.STOPPED

    def pause(self):
        if self.playing.is_set():
            if self.paused.is_set():
                self.paused.clear()
                self.state = self.PLAYING
            else:
                self.paused.set()
                self.state = self.PAUSED

    def __file_player(self):
        while not self.shutdown.is_set():
            # Protect CPU against missing files / stopped state
            time.sleep(.5)

            # Do not even try to load the files if we are stopped
            if not self.playing.is_set():
                continue

            # We should be playing the given files
            with self.files_lock:
                for f in self.files:
                    # Don't start the next file if we are stopped
                    if not self.playing.is_set():
                        break

                    # Load the file using buffered IO to protect against
                    # large files
                    try:
                        with open(f, 'rb') as fid:
                            print("Playing File: {0}".format(f))
                            for line in fid:
                                # Support real time pausing
                                while self.paused.is_set():
                                    time.sleep(.5)

                                # Check to see if we should still be running
                                if self.playing.is_set():
                                    # Do something special with the line
                                    self.__process_line(line)
                                else:
                                    # Bail out
                                    break
                            print("\n")
                    except IOError:
                        # TODO: Useing logging
                        print "Error running file: {f}".format(f=f)

    def __process_line(self, line):
        # Note the order of the calls (send then parse) allows the
        # parser to throttle the messages being sent.  This is needed to
        # support real time message delays

        # Send the next available message
        if self.next_message:
            self.__print_elapsed_time(self.next_message.time_stamp)
            # Keep trying to send the message (do not throw any away)
            while(not self.driver.send(self.next_message)):
                time.sleep(.001)

            self.last_stamp = self.next_message.time_stamp

        # Parse the line and wait
        self.next_message = self.parser.parse_line(line)
        if self.use_wall_time and self.next_message:
            if self.last_stamp:
                delay = (self.next_message.time_stamp - self.last_stamp) / 1.0e6
                if delay < 3.0:
                    time.sleep(delay)
                else:
                    print("Skipping {0} second delay".format(delay))

    def __print_elapsed_time(self, stamp):
        sec = stamp / 1.0e6
        sys.stdout.write("\r\tElapsed Time (seconds): {0:1.3f}".format(sec))
        sys.stdout.flush()

