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
    # logging.debug("Peer main got argv(list): " + str(argv))

    try:
        opts, args = getopt.getopt(argv, "dhr:p:c:o:a:",
                                   ["help",
                                    "radio_station_target=",
                                    "port=",
                                    "score=",
                                    "public=",
                                    "private=",
                                    "password=",
                                    "configure_file_path="
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
    port = conf.PORT_PEER
    radio_station_ip = conf.IP_RADIOSTATION
    radio_station_port = conf.PORT_RADIOSTATION
    radio_station_ip_sub = conf.IP_RADIOSTATION
    radio_station_port_sub = conf.PORT_RADIOSTATION
    score = conf.DEFAULT_SCORE_PACKAGE
    public = conf.PUBLIC_PATH
    private = conf.PRIVATE_PATH
    pw = conf.DEFAULT_PW

    # Parse command line arguments.
    for opt, arg in opts:
        if (opt == "-r") or (opt == "--radio_station_target"):
            try:
                if ':' in arg:
                    target_list = util.parse_target_list(arg)
                    if len(target_list) == 2:
                        radio_station_ip, radio_station_port = target_list[0]
                        radio_station_ip_sub, radio_station_port_sub = target_list[1]
                    else:
                        radio_station_ip, radio_station_port = target_list[0]
                    # util.logger.spam(f"peer "
                    #                  f"radio_station_ip({radio_station_ip}) "
                    #                  f"radio_station_port({radio_station_port}) "
                    #                  f"radio_station_ip_sub({radio_station_ip_sub}) "
                    #                  f"radio_station_port_sub({radio_station_port_sub})")
                elif len(arg.split('.')) == 4:
                    radio_station_ip = arg
                else:
                    raise Exception("Invalid IP format")
            except Exception as e:
                util.exit_and_msg(f"'-r' or '--radio_station_target' option requires "
                                  f"[IP Address of Radio Station]:[PORT number of Radio Station], "
                                  f"or just [IP Address of Radio Station] format. error({e})")
        elif (opt == "-p") or (opt == "--port"):
            port = arg
        elif (opt == "-c") or (opt == "--score"):
            score = arg
        elif (opt == "-a") or (opt == "--password"):
            pw = arg
        elif opt == "--public":
            public = arg
        elif opt == "--private":
            private = arg
        elif opt == "-d":
            util.set_log_level_debug()
        elif (opt == "-h") or (opt == "--help"):
            usage()
            return

    # run peer service with parameters
    logging.info(f"loopchain peer run with: port({port}) "
                 f"radio station({radio_station_ip}:{radio_station_port}) "
                 f"score({score})")

    # check Port Using
    if util.check_port_using(conf.IP_PEER, int(port)):
        util.exit_and_msg('Peer Service Port is Using '+str(port))

    # str password to bytes
    if isinstance(pw, str):
        pw = pw.encode()

    ObjectManager().peer_service = PeerService(radio_station_ip=radio_station_ip,
                                               radio_station_port=radio_station_port,
                                               public_path=public,
                                               private_path=private,
                                               cert_pass=pw)

    # logging.debug("loopchain peer_service is: " + str(ObjectManager().peer_service))
    ObjectManager().peer_service.serve(port, score)


def usage():
    print("USAGE: LoopChain Peer Service")
    print("python3 peer.py [option] [value] ...")
    print("-------------------------------")
    print("option list")
    print("-------------------------------")
    print("-o or --configure_file_path : json configure file path")
    print("-h or --help : print this usage")
    print("-r or --radio_station_target : [IP Address of Radio Station]:[PORT number of Radio Station],"
          "[IP Address of Sub Radio Station]:[PORT number of Sub Radio Station]"
          "or just [IP Address of Radio Station]")
    print("-p or --port : port of Peer Service itself")
    print("-c or --score : user score repository Path")
    print("-a or --password : private key password")
    print("--public : public file path")
    print("--private : private key file path")
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
