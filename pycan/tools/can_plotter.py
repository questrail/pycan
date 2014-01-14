# -*- coding: utf-8 -*-
# Copyright (c) 2013 The pycan developers. All rights reserved.
# Project site: https://github.com/questrail/pycan
# Use of this source code is governed by a MIT-style license that
# can be found in the LICENSE.txt file for the project.
import time
import threading
import matplotlib.pylab as pylab


class CANPlot(object):
    def __init__(self, label, ylim=None):
        self.label = label
        self.ylim = ylim
        self.data_series = []
        self.time_series = []

    def process_message(self, message):
        """
        Process a pyCAN message and store the resulting data.
        This function can / should be overwritten by the sub classes
        """
        time_stamp = message.time_stamp / message.time_scale
        self.store_data(1, time_stamp)

    def store_data(self, data, time_stamp):
        """
        Store the given data at the specified time
        """
        self.data_series.append(data)
        self.time_series.append(time_stamp)


class CANPlotter(object):
    def __init__(self, plots, title='CAN Plotter', parent=None):
        if parent is None:
            self.fig = pylab.figure()
        else:
            self.fig = parent

        self.fig.canvas.set_window_title(title)
        self.fig.suptitle(title)

        self.plots = plots

        self.linked_ax = pylab.subplot(len(self.plots)+1, 1, 1)
        self.first_time_stamp = 0
        self.last_time_stamp = 0

    def process_message(self, message):
        """
        Process the CAN message and store the data.
        """
        for can_plot in self.plots:
            can_plot.process_message(message)

        self.last_time_stamp = (message.time_stamp + 1) / message.time_scale

        if not self.first_time_stamp and self.last_time_stamp:
            self.first_time_stamp = self.last_time_stamp

    def show(self):
        # Add a final data point to all of the series to ensure they all end
        # on the same data point
        plt_idx = 1
        for can_plot in self.plots:
            # Plot the data
            pylab.subplot(len(self.plots), 1, plt_idx, sharex=self.linked_ax)
            pylab.xlim((self.first_time_stamp, self.last_time_stamp))
            pylab.ylim(can_plot.ylim)
            pylab.grid(True)
            pylab.scatter(can_plot.time_series, can_plot.data_series, label=can_plot.label)
            pylab.subplots_adjust(left=.05, right=.85, hspace=0)
            pylab.legend(bbox_to_anchor=(1, 1), loc=2, borderaxespad=0.)
            plt_idx += 1

        pylab.xlabel("Trace Time (seconds)")
        pylab.show()


class CANRealTimePlotter(object):
    REFRESH_RATE = 0.5  # Seconds
    def __init__(self, driver, plots, title='Real Time CAN Plotter', parent=None, window=10.0):
        self.plotter = CANPlotter(plots=plots, title=title, parent=parent)
        self.driver = driver
        self.window = window
        self.plot_handles = []

        ani = animation.FuncAnimation(self.plotter.fig, self.__update_plots, init_func=self.__figure_setup)

        self.__figure_setup()

        self.__msg_thread = threading.Thread(target=self.__message_processor)
        self.__msg_thread.daemon = True
        self.__msg_thread.start()

        self.__disp_thread = threading.Thread(target=self.__update_plots)
        self.__disp_thread.daemon = True
        self.__disp_thread.start()

    def __message_processor(self):
        while 1:
            # Add a message timeout to allow the loop to process signals
            msg = self.driver.next_message(timeout=3.0)
            print msg
            if msg:
                self.plotter.process_message(msg)

    def __figure_setup(self):
        #pylab.ion()
        plt_idx = 1
        for can_plot in self.plotter.plots:
            # Plot the data
            pylab.subplot(len(self.plotter.plots), 1, plt_idx, sharex=self.plotter.linked_ax)
            pylab.xlim((0, 1))
            pylab.ylim(can_plot.ylim)
            pylab.grid(True)
            self.plot_handles.append(pylab.scatter(can_plot.time_series, can_plot.data_series, label=can_plot.label))
            pylab.subplots_adjust(left=.05, right=.85, hspace=0)
            pylab.legend(bbox_to_anchor=(1, 1), loc=2, borderaxespad=0.)
            plt_idx += 1

        pylab.xlabel("Trace Time (seconds)")

        #pylab.show()

    def __update_plots(self):
        while 1:
            for idx, can_plot in enumerate(self.plotter.plots):
                self.plot_handles[idx].set_ydata(can_plot.data_series)
                self.plot_handles[idx].set_xdata(can_plot.time_series)

            pylab.draw()
            time.sleep(self.REFRESH_RATE)

    def menu(self):
        pylab.show()
        while 1:
            time.sleep(.5)


