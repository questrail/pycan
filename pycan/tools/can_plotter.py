# -*- coding: utf-8 -*-
# Copyright (c) 2013 The pycan developers. All rights reserved.
# Project site: https://github.com/questrail/pycan
# Use of this source code is governed by a MIT-style license that
# can be found in the LICENSE.txt file for the project.
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
    def __init__(self, plots, title='CAN Plotter',
                       sub_title='CAN Message vs Trace Time', parent=None):
        if parent is None:
            self.fig = pylab.figure()
        else:
            self.fig = parent

        self.fig.canvas.set_window_title(title)
        self.fig.suptitle(sub_title)

        self.plots = plots

        self.linked_ax = pylab.subplot(len(self.plots)+1, 1, 1)
        self.last_time_stamp = 0

    def process_message(self, message):
        """
        Process the CAN message and store the data.
        """
        for can_plot in self.plots:
            can_plot.process_message(message)

        self.last_time_stamp = (message.time_stamp + 1) / message.time_scale

    def show(self):
        # Add a final data point to all of the series to ensure they all end
        # on the same data point
        plt_idx = 1
        for can_plot in self.plots:
            # Plot the data
            pylab.subplot(len(self.plots), 1, plt_idx, sharex=self.linked_ax)
            pylab.xlim((0,self.last_time_stamp))
            pylab.ylim(can_plot.ylim)
            pylab.scatter(can_plot.time_series, can_plot.data_series, label=can_plot.label)
            pylab.subplots_adjust(hspace=0)
            pylab.legend(bbox_to_anchor=(1, 1), loc=2, borderaxespad=0.)
            plt_idx += 1

        pylab.xlabel("Trace Time (seconds)")
        pylab.show()

