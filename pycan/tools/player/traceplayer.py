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
import threading


class TracePlayer(object):
    PLAYING = "Playing"
    STOPPED = "Stopped"
    PAUSED = "Paused"

    def __init__(self, driver, parser, files=[]):
        self.driver = driver
        self.parser = parser
        self.next_message = None
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
                self.state = self.PAUSE

    def __file_player(self):
        while not self.shutdown.is_set():
            # Protect CPU against missing files / stopped state
            time.sleep(1)

            # Do not even try to load the files if we are stopped
            if not self.playing.is_set():
                continue

            # We should be playing the given files
            with files_lock:
                for f in self.files:
                    # Don't start the next file if we are stopped
                    if not self.playing.is_set():
                        break

                    # Load the file using buffered IO to protect against
                    # large files
                    try:
                        with open(f, 'r') as fid:
                            for line in fid:
                                # Support real time pausing
                                while self.paused_is_set():
                                    time.sleep(.5)

                                # Check to see if we should still be running
                                if self.playing.is_set():
                                    # Do something special with the line
                                    self.__process_line()
                                else:
                                    # Bail out
                                    break
                    except IOError:
                        # TODO: Useing logging
                        print "Error running file: {f}".format(f)

    def __process_line(self, line):
        # Note the order of the calls (send then parse) allows the
        # parser to throttle the messages being sent.  This is needed to
        # support real time message delays

        # Send the next available message
        if self.next_message:
            self.driver.send(self.next_message)

        # Parse the line and wait
        self.next_message = self.parser.parse_line(line)
