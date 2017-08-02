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

import sys
import os
import logging
import getopt
import yappi
import loopchain.utils as util
from loopchain import configure as conf
from loopchain.peer import PeerService
from loopchain.baseservice import ObjectManager


def main(argv):
    logging.info("Peer main got argv(list): " + str(argv))

    try:
        opts, args = getopt.getopt(argv, "dhr:p:c:",
                                   ["help",
                                    "radio_station_ip=",
                                    "radio_station_port=",
                                    "port=",
                                    "score=",
                                    "cert="
                                    ])
    except getopt.GetoptError as e:
        logging.error(e)
        usage()
        sys.exit(1)

    # default option values
    port = conf.PORT_PEER
    radio_station_ip = conf.IP_RADIOSTATION
    radio_station_port = conf.PORT_RADIOSTATION
    score = conf.DEFAULT_SCORE_PACKAGE
    cert = None
    pw = None

    # apply option values
    for opt, arg in opts:
        if (opt == "-r") or (opt == "--radio_station_ip"):
            radio_station_ip = arg
        elif (opt == "-p") or (opt == "--port"):
            port = arg
        elif (opt == "-c") or (opt == "--score"):
            score = arg
        elif opt == "--cert":
            cert = arg
        elif opt == "-d":
            util.set_log_level_debug()
        elif (opt == "-h") or (opt == "--help"):
            usage()
            return

    # run peer service with parameters
    logging.info("\nTry Peer Service run with: \nport(" +
                 str(port) + ") \nRadio Station(" +
                 radio_station_ip + ":" +
                 str(radio_station_port) + ") \nScore(" +
                 score + ") \n")
    # check Port Using
    if util.check_port_using(conf.IP_PEER, int(port)):
        logging.error('Peer Service Port is Using '+str(port))
        return

    ObjectManager().peer_service = PeerService(None, radio_station_ip, radio_station_port, cert, pw)
    logging.info("loopchain peer_service is: " + str(ObjectManager().peer_service))
    ObjectManager().peer_service.serve(port, score)


def usage():
    print("USAGE: LoopChain Peer Service")
    print("python3 peer.py [option] [value] ...")
    print("-------------------------------")
    print("option list")
    print("-------------------------------")
    print("-h or --help : print this usage")
    print("-r or --radio_station_ip : IP Address of Radio Station.")
    print("-p or --port : port of Peer Service itself")
    print("-c or --score : user score repository Path")
    print("--cert : certificate directory path")
    print("-d : Display colored log.")


# Run grpc server as a Peer
if __name__ == "__main__":
    try:
        if os.getenv('DEFAULT_SCORE_HOST') is not None:
            os.system("ssh-keyscan "+os.getenv('DEFAULT_SCORE_HOST')+" >> /root/.ssh/known_hosts")

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
