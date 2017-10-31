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

import getpass
import logging
import os
import sys

import coloredlogs

from loopchain.baseservice.ca_service import CAService


def set_log_level(level):
    coloredlogs.install(level=level)
    logging.basicConfig(level=level)

_DEFAULT_PATH = "resources/testcerts/"

# Main menu
def main_menu(show=True):
    if show:
        print("\nTheLoop LoopChain Certificate Authority Command Tools\n")
        print("Choose menu number you want")
        print("Default Directory : \"" + _DEFAULT_PATH + "\"")
        print("---------------------")
        print("1. Generate CA Certificate")
        print("2. Show CA Certificate")
        print("---------------------")
        print("3. Generate Peer Certificate")
        print("4. Show Peer Certificates")
        print("---------------------")
        print("0. Quit")

    choice = input(" >>  ")
    exec_menu(choice)

    return


# Excute menu
def exec_menu(choice):
    ch = choice.lower()
    if ch == '':
        main_menu(True)
    else:
        try:
            menu_actions[ch]()
        except KeyError:
            print("Invalid selection, please try again.\n")
            main_menu(True)


def menu1():
    print("\n##### CA 정보 #####")
    input = menu1_1()
    if input[0] == "Y" or input[0] == "y":
        print("[cn=" + input[1] + ", ou=" + input[2] + ", o=" + input[3] + ", c=kr]")
        period = int(menu1_2())

        ca = CAService(_DEFAULT_PATH, None)
        ca.generate_ca_cert(cn=input[1], ou=input[2], o=input[3], expire_period=period, password=None)

        print("\n----- CA 인증서 생성 완료 -----")
        main_menu(True)
    else:
        print("\n##### User Cancel #####")
        main_menu(True)


def menu1_1():
    print("\n----- 주체(subject) 정보 -----")
    print("Common Name(eg, your name) [Default Test CA] : ")
    cn = input(" >> ")
    if cn == "":
        cn = "Test CA"

    print("Organization Unit Name(eg, section) [Default DEV] : ")
    ou = input(" >> ")
    if ou == "":
        ou = "DEV"

    print("Organization Name(eg, company) [Default TheLoop] : ")
    o = input(" >> ")
    if o == "":
        o = "THeLoop"

    print("[cn=" + cn + ", ou=" + ou + ", o=" + o + ", c=kr] OK? (Y/N) : ")
    ok = input(" >> ")
    return [ok, cn, ou, o]


def menu1_2():
    print("\n----- 인증서 유효기간 -----")
    print("Expire Period(eg, 1years) [Default 5] : ")
    period = input(" >> ")
    if period == "":
        period = 5
    return period


def menu2():
    print("\n##### CA 인증서 #####")
    ca = CAService(_DEFAULT_PATH, None)
    ca.show_ca_certificate()
    main_menu(True)


def menu3():
    print("\n##### CA 인증서/개인키 로딩 #####")
    ca = CAService(_DEFAULT_PATH, None)
    if ca.is_secure is False:
        print("CA 인증서 로딩 실패")
        return

    print("\n##### Peer 인증서/개인키 #####")
    input = menu3_2()
    if input[0] == "Y" or input[0] == "y":
        ca = CAService(_DEFAULT_PATH, None)
        ca.generate_peer_cert(cn=input[1], password=None)

        print("\n----- Peer 인증서/개인키 생성 완료 -----")
        main_menu(True)
    else:
        print("\n##### User Cancel #####")
        main_menu(True)


def menu3_1():
    print("\n----- CA 개인키 비밀번호 -----")
    return getpass.getpass()


def menu3_2():
    print("\n----- 주체(subject) 정보 -----")
    print("Common Name(eg, your name) [Default TestPeer1] : ")
    cn = input(" >> ")
    if cn == "":
        cn = "TestPeer1"

    print("[cn=" + cn + "] OK? (Y/N) : ")
    ok = input(" >> ")
    return [ok, cn]


def menu4():
    print("\n##### Peer 인증서 목록 #####")
    ca = CAService()
    if ca.is_secure is False:
        ca = CAService(_DEFAULT_PATH, None)

    ca.show_peer_list()
    main_menu(True)


# Exit program
def tool_exit():
    sys.exit()

# Menu definition
menu_actions = {
    'main_menu': main_menu,
    '1': menu1,
    '2': menu2,
    '3': menu3,
    '4': menu4,
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