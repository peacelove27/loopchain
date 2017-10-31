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
import logging

import coloredlogs
import grpc
import os
import requests

from loopchain.radiostation import AdminManager
from loopchain import configure as conf

sys.path.append("loopchain/protos")
from loopchain.protos import loopchain_pb2, loopchain_pb2_grpc, message_code


# Main definition - constants
menu_actions = {}
tool_globals = {}


def set_log_level(level):
    coloredlogs.install(level=level)
    logging.basicConfig(level=level)


# Main menu
def main_menu(show=True):
    if show:
        print("TheLoop LoopChain Admin Command Tools\n")
        print("Choose menu number you want")
        print("---------------------")
        print("1. connect rs admin service")
        print("2. get rs admin status")
        print("3. Get all channel manage info")
        print("4. Add peer")
        print("5. Add channel")
        print("6. Dump current data to json")
        print("7. Send channel manage info to RS")
        print("0. Quit")

    choice = input(" >>  ")
    exec_menu(choice)

    return


# Execute menu
def exec_menu(choice):
    ch = choice.lower()
    if ch == '':
        menu_actions['main_menu'](True)
    else:
        try:
            menu_actions[ch]()
        except KeyError:
            print("Invalid selection, please try again.\n")
            menu_actions['main_menu'](True)
    return


def menu1():
    print("\nconnect rs admin service\n")
    print(f"\nInput RS Target [IP]:[port] "
          f"(default '' -> 127.0.0.1:{conf.PORT_RADIOSTATION + conf.PORT_DIFF_INNER_SERVICE}, "
          f"[port] -> 127.0.0.1:[port])")
    choice = input(" >>  ")
    if choice == "":
        choice = f"127.0.0.1:{conf.PORT_RADIOSTATION + conf.PORT_DIFF_INNER_SERVICE}"
    elif choice.find(':') == -1:
        choice = "127.0.0.1:" + choice

    channel = grpc.insecure_channel(choice)
    rs_stub = loopchain_pb2_grpc.AdminServiceStub(channel)
    tool_globals["rs_stub"] = rs_stub

    response = rs_stub.Request(loopchain_pb2.Message(
        code=message_code.Request.status,
        message="connect from gtool"
    ), conf.GRPC_TIMEOUT)
    print("RS Status: " + str(response))
    main_menu()


def menu1_1():
    # TODO 모든 peer 리스트를 띄운다.
    menu1()


def menu1_2():
    # TODO 모든 채널 리스트를 띄운다.
    menu1()


def menu1_3():
    # 한 단계 더
    # TODO 모든 채널을 넘버링 해서 띄우고, 로드할 채널 번호를 선택하게끔 한다.
    menu1()


def menu2():
    # TODO get rs admin status
    print("\nget rs admin status")
    print("0. Back")
    choice = input(" >>  ")
    exec_menu("2-" + choice)
    return


def menu3():
    print("\nGet all channel manage info")
    AdminManager("station").get_all_channel_info()
    print("0. Back")
    choice = input(" >>  ")

    if choice == '0':
        menu_actions['main_menu']()
    return


def menu4():
    print("\nAdd peer")
    print("Enter the peer target in the following format:")
    print("IP Address of Radio Station:PORT number of Radio Station")
    new_peer_target = input(" >>  ")
    AdminManager("station").ui_add_peer_target(new_peer_target)

    print("1. Add additional peer")
    print("0. Back")
    choice = input(" >>  ")

    if choice == '1':
        menu4()
    elif choice == '0':
        menu_actions['main_menu']()
    return


def menu5():
    print("\nAdd channel")
    print("Enter the new channel name:")
    new_channel = input(" >>  ")
    AdminManager("station").add_channel(new_channel)

    print("0. Back")
    choice = input(" >>  ")

    if choice == '0':
        menu_actions['main_menu']()
    return


def menu6():
    print("\ndump current data to json")
    current_data = AdminManager("station").json_data
    channel_manage_data_path = conf.CHANNEL_MANAGE_DATA_PATH

    AdminManager("station").save_channel_manage_data(current_data)
    print(f"current channel manage data is now up to date in {channel_manage_data_path}")

    print("0. Back")
    choice = input(" >>  ")

    if choice == '0':
        menu_actions['main_menu']()
    return


# Exit program
def tool_exit():
    sys.exit()


# Menu definition
menu_actions = {
    'main_menu': main_menu,
    '1': menu1,
    '1-1': menu1_1,
    '1-2': menu1_2,
    '1-3': menu1_3,
    '2': menu2,
    '3': menu3,
    '4': menu4,
    '5': menu5,
    '6': menu6,
    '0': tool_exit
}


# Main Program
if __name__ == "__main__":

    os.system("source bin/activate")
    set_log_level(logging.DEBUG)
    if len(sys.argv) > 1:
        # Run Menu
        print("Have a nice one~ with your number is " + sys.argv[1])
        menu_actions[sys.argv[1]]()
    else:
        # Launch main menu
        main_menu(True)
