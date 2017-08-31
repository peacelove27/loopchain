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

# Import the modules needed to run the script.
import sys
import os
import grpc
import json
import random
import requests
import datetime
import timeit
import coloredlogs
from sys import platform
from testcase.unittest.test_util import clean_up_temp_db_files
from loopchain.blockchain import *
from loopchain.protos import message_code

sys.path.append("loopchain/protos")
from loopchain.protos import loopchain_pb2, loopchain_pb2_grpc


# Main definition - constants
menu_actions = {}


def set_log_level(level):
    coloredlogs.install(level=level)
    logging.basicConfig(level=level)


# Main menu
def main_menu(show=True):
    if show:
        print("TheLoop LoopChain Project Command Tools\n")
        print("Choose menu number you want")
        print("---------------------")
        print("1. TEST")
        print("2. docker")
        print("3. Git Flow")
        print("4. PEER Client (TEST)")
        print("5. Clean Up TEST and Proto Gen")
        print("6. Check Python Process(ps -ef | grep python)")
        print("7. Kill All Python Process(pkill -fs python)")
        print("8. Clear __pycache__")
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
    print("\nTest Tools\n")
    print("1. All Test")
    print("2. test unittest")
    print("3. test integration")
    print("4. test performance")
    print("5. cat performance result")
    print("6. test integration AWS")
    print("0. Back")
    choice = input(" >>  ")
    exec_menu("1-" + choice)
    return


def menu1_1():
    os.system("./run_test.sh")
    print("Any key to continue integration test (0:cancel)")
    choice = input(" >>  ")
    if choice != '0':
        os.system("./run_test_integration.sh")
    print("Any key to continue performance test (0:cancel)")
    choice = input(" >>  ")
    if choice != '0':
        os.system("./run_test_performance.sh")
    menu1()


def menu1_2():
    os.system("./run_test.sh")
    menu1()


def menu1_3():
    os.system("./run_test_integration.sh")
    menu1()


def menu1_4():
    os.system("./run_test_performance.sh")
    menu1()


def menu1_5():
    os.system("cat ./test_performance_result.txt")
    menu1()


def menu1_6():
    os.system("./run_test_integration_aws.sh")
    menu1()


def menu2_1():
    os.system("docker images")
    menu2()


def menu2_2():
    os.system("docker ps -a")
    menu2()


def menu2_3():
    os.system('docker stop $(docker ps -aq)')
    menu2()


def menu2_4():
    os.system('docker rm $(docker ps -aq)')
    menu2()


def menu2_5():
    os.system('docker rmi $(docker images)')
    menu2()


def menu2_6():
    os.system('cd deploy; ./build_docker_image.sh dev; cd ..')
    menu2()


def menu2_7():
    os.system('cd deploy; ./launch_containers_in_local.sh dev; cd ..')
    menu2()


def menu2_8():
    os.system('cd deploy; ./remove_all_docker_containers.sh; cd ..')
    menu2()


def menu5():
    clean_up_temp_db_files()
    os.system("rm -rf *_profile.*")
    os.system("./generate_code.sh")
    main_menu()


def menu6():
    os.system("ps -ef | grep python")
    main_menu()


def menu7():
    if platform == "darwin":
        os.system("pkill -f python")
    else:
        os.system("pgrep -f python | tail -$((`pgrep -f python | wc -l` - 1)) | xargs kill -9")
    main_menu()


def menu8():
    os.system("""find . | grep -E "(__pycache__|\.pyc|\.pyo$)" | xargs rm -rf""")
    main_menu()


def menu2():
    print("\nDocker Tools")
    print("1. docker images")
    print("2. docker ps -a")
    print("3. docker stop $(docker ps -aq)")
    print("4. docker rm $(docker ps -aq)")
    print("5. docker rmi $(docker images)")
    print("6. docker build images (dev)")
    print("7. docker launch in local (dev)")
    print("8. docker remove all docker containers")
    print("0. Back")
    choice = input(" >>  ")
    exec_menu("2-" + choice)
    return


def menu3():
    print("\nGit Flow Tools")
    print("1. git feature start")
    print("2. git feature finish")
    print("3. remove remote-tracking branch")
    print("0. Back")
    choice = input(" >>  ")
    exec_menu("3-" + choice)
    return


def show_git_branch(option = ""):
    print("-----git branch list-----")
    os.system("git branch" + " " + option)


def menu3_1():
    show_git_branch()
    print("Add New Feature Num (prefix: LOOP-00)")
    choice = input(" >>  ")
    if choice != "":
        command = "git flow feature start LOOP-" + str(choice)
        os.system(command)
        command = "git push --set-upstream origin feature/LOOP-" + str(choice)
        os.system(command)
    menu3()


def menu3_2():
    show_git_branch()
    print("Choose branch number you want to finish (prefix: LOOP-00)")
    choice = input(" >>  ")
    if choice != "":
        command = "git flow feature finish LOOP-" + str(choice)
        os.system(command)
    menu3()


def menu3_3():
    show_git_branch("-a")
    print("Choose branch number you want to remove (prefix: LOOP-00)")
    choice = input(" >>  ")
    if choice != "":
        command = "git branch -d -r origin/feature/LOOP-" + str(choice)
        os.system(command)
    menu3()


def stopwatch():
    # Calculate TPS to create block
    duration = timeit.default_timer() - stopwatch.start
    tps_tx = float(stopwatch.num_created_tx) / duration

    # Display
    print('')
    print('=============================')
    print('')
    print('=============================')
    print('')
    print(stopwatch.num_created_tx, ' transactions are created.')
    print('Creating TXs duration: ', duration)
    print('TPS to create Txs: ', tps_tx, 'number of transaction / sec')
    print('')
    print('=============================')
    print('')
    print('=============================')
    print('')


def menu4(peer_stub=None, tx_hash=""):
    print("\nPeer Client (TEST)")
    print("peer_stub: " + str(peer_stub))
    print("1. Connect to Peer")
    print("2. Create Transaction(tx)")
    print("3. Find Transaction(tx)")
    print("4. Get Status")
    print("5. Query (SCORE TEST)")
    print("6. All Block List")
    print("7. Monitoring")
    print("8. Random Test (repeat create tx random times, and sleep random seconds)")
    print("9. Set Log Level")
    print("10. Stop Servers")
    print("11. Echo Test")
    print("12. Get Peer List")
    print("13. Create tx and Find tx repeat")
    print("0. Back")
    choice = input(" >>  ")

    params = peer_stub, tx_hash
    if choice == "0":
        main_menu()
    else:
        globals()["menu4_" + choice](params)

    return


def menu4_13(params):
    peer_stub = params[0]

    print("Input Repeat Times: default 100000")
    repeat_times = input(" >>  ")
    if repeat_times == "":
        repeat_times = 100000
    repeat_times = int(repeat_times)

    print("Input Test Interval Seconds: default 10")
    test_interval = input(" >>  ")
    if test_interval == "":
        test_interval = 10
    test_interval = int(test_interval)

    print("Allow fail times during test: default 3 (immediately stop)")
    allow_fails = input(" >>  ")
    if allow_fails == "":
        allow_fails = 3
    allow_fails_reset = int(allow_fails)
    allow_fails = allow_fails_reset
    test_times = 0
    fail_times = 0

    while repeat_times > 0:
        response = peer_stub.CreateTx(
            loopchain_pb2.CreateTxRequest(data="TEST transaction data by demotool"))
        tx_hash = response.tx_hash
        print(f"Create Tx({tx_hash}) remain times({repeat_times})")
        time.sleep(test_interval)
        response = peer_stub.GetTx(loopchain_pb2.GetTxRequest(tx_hash=tx_hash), conf.GRPC_TIMEOUT)
        if response.response_code != message_code.Response.success:
            allow_fails -= 1
            fail_times += 1
        else:
            allow_fails = allow_fails_reset
        print("Find Tx: " + str(response))
        print(f"({test_times}) test times, ({allow_fails}) allow fails, ({fail_times}) fail times")

        time.sleep(test_interval)
        test_times += 1

        if allow_fails <= 0:
            response = requests.get("http://127.0.0.1:9002" + "/api/v1/peer/status-list")
            print("Radio Station Last Status List: ")
            print(util.pretty_json(response.text))
            menu7()

        repeat_times -= 1


def menu4_8(params):
    peer_stub = params[0]
    test_start_time = datetime.datetime.now()

    print("Input Maximum Create Tx Random Times: default 1000")
    max_times = input(" >>  ")
    if max_times == "":
        max_times = 1000

    print("Input Maximum Sleep Seconds Random: default 10")
    max_sleep = input(" >>  ")
    if max_sleep == "":
        max_sleep = 10

    while True:
        random_times = random.randrange(0, int(max_times))
        random_sleep = random.randrange(0, int(max_sleep))
        print(f"Random Test try: {random_times} times and {random_sleep} seconds sleep, "
              f"total test mins({util.datetime_diff_in_mins(test_start_time)})")
        try:
            for i in range(random_times):
                peer_stub.CreateTx(loopchain_pb2.CreateTxRequest(data=f"TEST transaction data by demotool {i}"))
            time.sleep(random_sleep)
        except KeyboardInterrupt:
            break


def grpc_performance_test(peer_stub, method_name, param):
    method = getattr(peer_stub, method_name)

    print("Input Repeat Times: default 1")
    choice = input(" >>  ")
    if choice == "":
        choice = 1

    # Init stopwatch(monitoring) Data
    stopwatch.start = timeit.default_timer()
    stopwatch.num_created_tx = 0

    response = None
    if peer_stub is not None:
        for i in range(int(choice)):
            response = method(param, conf.GRPC_TIMEOUT)
            stopwatch.num_created_tx += 1

    stopwatch()

    print("run " + str(choice) + " times complete")

    try:
        menu4(peer_stub, response.tx_hash)  # response is not None and has tx_hash
    except Exception:
        menu4(peer_stub, "")  # or not


def menu4_5(params=None):
    peer_stub = params[0]
    print("Query SCORE Performance Test")

    query = {
        'param1': 1234,
        'param2': 'this is just sample',
        'param3': [
            {'date': '2015-03-11', 'item': 'iPhone'},
            {'date': '2016-02-23', 'item': 'Monitor'},
        ]
    }

    json_string = json.dumps(query)
    grpc_performance_test(peer_stub,
                          "Query",
                          loopchain_pb2.QueryRequest(params=json_string))


def menu4_6(params):
    print("Print all [Block - hash], (tx - hash)")
    peer_stub = params[0]

    response = peer_stub.GetLastBlockHash(loopchain_pb2.CommonRequest(request=""), conf.GRPC_TIMEOUT)
    print("\nlast block hash: " + str(response.block_hash) + "\n")

    block_hash = response.block_hash
    total_tx = 0
    total_height = -1

    while block_hash is not None:
        response = peer_stub.GetBlock(loopchain_pb2.GetBlockRequest(block_hash=block_hash,
                                                                    block_data_filter="prev_block_hash, "
                                                                                      "height, block_hash",
                                                                    tx_data_filter="tx_hash"))
        # print("[block: " + str(response) + "]")
        if len(response.block_data_json) > 0:
            block_data = json.loads(response.block_data_json)
            print("[block height: " + str(block_data["height"]) + ", hash: " + str(block_data["block_hash"]) + "]")

            if len(response.tx_data_json) == 1:
                tx_data = json.loads(response.tx_data_json[0])
                print("has tx: " + str(tx_data["tx_hash"]))
            else:
                print("has tx: " + str(len(response.tx_data_json)))

            total_height += 1
            total_tx += len(response.tx_data_json)
            block_hash = block_data["prev_block_hash"]
            if int(block_data["height"]) == 0:
                block_hash = None
        else:
            block_hash = None

    print("\nblock chain height: " + str(total_height) + ", total tx: " + str(total_tx))

    menu4(peer_stub)


def menu4_7(params):

    print("Input monitoring interval seconds (default: 1)")
    choice = input(" >>  ")
    if choice == "":
        choice = 1

    try:
        while True:
            peer_stub = params[0]
            response = peer_stub.GetStatus(loopchain_pb2.StatusRequest(request="GetStatus"), conf.GRPC_TIMEOUT)
            print("Peer Status: " + str(response))
            print("this is monitoring loop (if you want exit make KeyboardInterrupt(ctrl+c)...)")
            time.sleep(int(choice))
    except KeyboardInterrupt:
        menu4(peer_stub)


def menu4_1(params=None):
    print("Input Peer Target [IP]:[port] (default '' -> 127.0.0.1:7100, [port] -> 127.0.0.1:[port])")
    choice = input(" >>  ")
    if choice == "":
        choice = "127.0.0.1:7100"
    elif choice.find(':') == -1:
        choice = "127.0.0.1:" + choice

    print("your input: " + choice)
    channel = grpc.insecure_channel(choice)
    peer_stub = loopchain_pb2_grpc.PeerServiceStub(channel)
    response = peer_stub.GetStatus(loopchain_pb2.StatusRequest(request="hello"), conf.GRPC_TIMEOUT)
    print("Peer Status: " + str(response))
    menu4(peer_stub)


def menu4_2(params):
    peer_stub = params[0]
    print("Create Tx Performance Test")
    grpc_performance_test(peer_stub,
                          "CreateTx",
                          loopchain_pb2.CreateTxRequest(data="TEST transaction data by demotool"))


def menu4_3(params):
    peer_stub = params[0]
    tx_hash = params[1]
    print("Input tx_hash you want to find default:" + tx_hash)
    choice = input(" >>  ")
    if choice == "":
        choice = tx_hash
    print("your input: " + choice)
    response = peer_stub.GetTx(loopchain_pb2.GetTxRequest(tx_hash=choice), conf.GRPC_TIMEOUT)
    print("Find Tx: " + str(response))
    menu4(peer_stub, tx_hash)


def menu4_4(params):
    peer_stub = params[0]
    response = peer_stub.GetStatus(loopchain_pb2.StatusRequest(request="GetStatus"), conf.GRPC_TIMEOUT)
    print("Peer Status: " + str(response))
    menu4(peer_stub)


def menu4_9(params):
    peer_stub = params[0]
    print("Set Log level input 1 is debug On, others are debug Off(set INFO)")
    choice = input(" >> ")

    if choice == "1":
        set_log_level(logging.DEBUG)
    else:
        set_log_level(logging.INFO)
    menu4(peer_stub)


def menu4_10(params):
    peer_stub = params[0]
    print("Stop Servers...")
    peer_stub.Stop(loopchain_pb2.StopRequest(reason="No Reason"), conf.GRPC_TIMEOUT)
    menu4()


def menu4_11(params):
    peer_stub = params[0]
    print("Input Repeat Times: default 1")
    choice = input(" >>  ")
    if choice == "":
        choice = 1

    # Init stopwatch(monitoring) Data
    stopwatch.start = timeit.default_timer()
    stopwatch.num_created_tx = 0

    dummy_data = "TEST transaction data by demotool"
    if peer_stub is not None:
        for i in range(int(choice)):
            peer_stub.Echo(
                loopchain_pb2.CommonRequest(request=dummy_data))
            stopwatch.num_created_tx += 1

    stopwatch()

    print("run " + str(choice) + " times complete")

    menu4(peer_stub, "")


def menu4_12(params):
    peer_stub = params[0]
    response = peer_stub.Request(loopchain_pb2.Message(code=message_code.Request.peer_peer_list), conf.GRPC_TIMEOUT)
    print("Peer Status: " + str(response))
    menu4(peer_stub)


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
    '1-4': menu1_4,
    '1-5': menu1_5,
    '1-6': menu1_6,
    '2': menu2,
    '2-1': menu2_1,
    '2-2': menu2_2,
    '2-3': menu2_3,
    '2-4': menu2_4,
    '2-5': menu2_5,
    '2-6': menu2_6,
    '2-7': menu2_7,
    '2-8': menu2_8,
    '3': menu3,
    '3-1': menu3_1,
    '3-2': menu3_2,
    '3-3': menu3_3,
    '4': menu4,
    '4-1': menu4_1,
    '5': menu5,
    '6': menu6,
    '7': menu7,
    '8': menu8,
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
