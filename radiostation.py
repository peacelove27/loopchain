#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2017 theloop, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import getopt
import logging
import sys

import yappi

import loopchain.utils as util
from loopchain import configure as conf
from loopchain.radiostation import RadioStationService


def main(argv):
    logging.info("RadioStation main got argv(list): " + str(argv))

    try:
        opts, args = getopt.getopt(argv, "dhp:o:s:",
                                   ["help",
                                    "port=",
                                    "cert=",
                                    "configure_file_path=",
                                    "seed="
                                    ])
    except getopt.GetoptError as e:
        logging.error(e)
        usage()
        sys.exit(1)

    # apply json configure values
    for opt, arg in opts:
        if (opt == "-o") or (opt == "--configure_file_path"):
            conf.Configure().load_configure_json(arg)

    # apply default configure values
    port = conf.PORT_RADIOSTATION
    cert = None
    pw = None
    seed = None

    # apply option values
    for opt, arg in opts:
        if opt == "-d":
            util.set_log_level_debug()
        elif (opt == "-p") or (opt == "--port"):
            port = arg
        elif opt == "--cert":
            cert = arg
        elif (opt == "-s") or (opt == "--seed"):
            try:
                seed = int(arg)
            except ValueError as e:
                util.exit_and_msg(f"seed or s opt must be int \n"
                                  f"intput value : {arg}")
        elif (opt == "-h") or (opt == "--help"):
            usage()
            return

    # Check Port is Using
    if util.check_port_using(conf.IP_RADIOSTATION, int(port)):
        logging.error('RadioStation Service Port is Using '+str(port))
        return

    RadioStationService(conf.IP_RADIOSTATION, cert, pw, seed).serve(port)


def usage():
    print("USAGE: python3 radiostation.py [option] [value].... ")
    print("-------------------------------")
    print("option list")
    print("-------------------------------")
    print("-p or --port : port of RadioStation Service itself")
    print("-d : Display colored log.")
    print("-s or --seed : create random table seed for kms")
    print("--cert : certificate directory path")


# Run grpc server as a RadioStation
if __name__ == "__main__":
    try:
        util.create_default_pki()

        if conf.ENABLE_PROFILING:
            yappi.start()
            main(sys.argv[1:])
            yappi.stop()
        else:
            main(sys.argv[1:])
    except KeyboardInterrupt:
        if conf.ENABLE_PROFILING:
            yappi.stop()
            print('Yappi result (func stats) ======================')
            yappi.get_func_stats().print_all()
            print('Yappi result (thread stats) ======================')
            yappi.get_thread_stats().print_all()
