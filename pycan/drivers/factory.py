# -*- coding: utf-8 -*-
# Copyright (c) 2013 The pycan developers. All rights reserved.
# Project site: https://github.com/questrail/pycan
# Use of this source code is governed by a MIT-style license that
# can be found in the LICENSE.txt file for the project.
"""CAN Driver Factory

This module is responsible to returning initialized CAN drivers
based on the supplied setup file.  This is implemented using
the factory design pattern.

For more details on OS / hardware requirements please see the
individual driver files

"""
import os
import ConfigParser

import kvaser
import canusb
import sim_can

drivers = {"Kvaser" : kvaser.Kvaser,
           "CANUSB" : canusb.CANUSB,
           "SIM_CAN" : sim_can.SimCAN,
          }

def get_driver(config_file):
    # Load the config file
    config = ConfigParser.ConfigParser()
    config.read(os.path.abspath(config_file))

    # Determine what type driver should be used
    selection = config.get('defaults', 'selection')

    if selection not in drivers:
        #TODO: Add a logging error here
        print("Unknown driver selection {sel}!".format(sel=selection))
        return None


    # Build the keyword arguments to pass to the driver
    kwargs = {}
    defaults = config.items('defaults')
    driver_vals = config.items(selection)

    for key, val in defaults:
        kwargs[key] = val

    for key, val in driver_vals:
        kwargs[key] = val

    # Initilize the driver
    return drivers[selection](**kwargs)


if __name__ == "__main__":
    d = get_driver('setup.cfg')

