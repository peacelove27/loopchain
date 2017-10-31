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
import getopt
import timeit
import grpc
import json
import loopchain.utils as util
from loopchain import configure as conf
from multiprocessing import Pool, current_process

sys.path.append("loopchain/protos")
import loopchain_pb2, loopchain_pb2_grpc


def client_process(argv):
    peer_target = argv[0]
    duration = argv[1]
    method_name = argv[2]

    count_tx = 0
    process_id = str(current_process())
    print("client process id: " + process_id)
    print("duration: " + str(duration))
    print("method_name: " + method_name)

    channel = grpc.insecure_channel(peer_target)
    peer_stub = loopchain_pb2_grpc.PeerServiceStub(channel)

    method = getattr(peer_stub, method_name)
    if method_name == "CreateTx":
        param = loopchain_pb2.CreateTxRequest(data="TEST transaction data by loadtool")
    elif method_name == "Query":
        query = {
            'param1': 1234,
            'param2': 'this is just sample',
            'param3': [
                {'date': '2015-03-11', 'item': 'iPhone'},
                {'date': '2016-02-23', 'item': 'Monitor'},
            ]
        }

        json_string = json.dumps(query)
        param = loopchain_pb2.QueryRequest(params=json_string)
    else:
        print(method_name + " is not suitable name")
        return

    start_time = timeit.default_timer()
    while duration > (timeit.default_timer() - start_time):
        # print(process_id + " try: " + peer_target)

        method(param, conf.GRPC_TIMEOUT)

        count_tx += 1
    duration_real = (timeit.default_timer() - start_time)

    # 테스트 측정을 위한 수행 시간 외의 프로그램 수행 시간을 보정한다.
    ops_times = count_tx
    start_time_ops = timeit.default_timer()
    while ops_times > 0:
        # 무조건 성공하는 조건문, while duration > (timeit.default_timer() - start_time): 의 실행 시간 대응
        if 0 < (timeit.default_timer() - start_time):
            ops_times -= 1  # count_tx += 1 실행 시간 대응

    duration_other_ops = timeit.default_timer() - start_time_ops

    print("duration_other_ops: " + str(duration_other_ops))
    duration_real -= duration_other_ops
    print("duration_real: " + str(duration_real))

    return count_tx, duration_real


def log_result(result):
    print("log_result: " + str(result))
    duration_total = 0

    total_tx = 0
    for count_tx, duration in result:
        total_tx += count_tx
        duration_total += duration

    duration_average = duration_total / float(len(result))
    tps_tx = float(total_tx) / duration_average

    # print("total_tx: " + str(total_tx))
    print(str(total_tx), ' transactions are created.')
    print('Creating TXs duration: ', duration_average)
    print('TPS to create Txs: ', tps_tx, 'number of transaction / sec')


def main(argv):
    logging.info("loadtest tool got argv(list): " + str(argv))

    try:
        opts, args = getopt.getopt(argv, "c:p:m:w:t:hd",
                                   ["client=",
                                    "peer=",
                                    "mins=",
                                    "help",
                                    "debug"
                                    ])
    except getopt.GetoptError as e:
        logging.error(e)
        usage()
        sys.exit(1)

    # default option values
    client = 1
    peer = "127.0.0.1:7100"
    duration = 10  # seconds, but param is mins
    test_way = 0

    # apply option values
    for opt, arg in opts:
        if (opt == "-c") or (opt == "--client"):
            client = int(arg)
        elif (opt == "-p") or (opt == "--peer"):
            peer = arg
        elif (opt == "-m") or (opt == "--mins"):
            duration = int(arg) * 60  # seconds, but param is mins
        elif opt == "-d":
            util.set_log_level_debug()
        elif opt == "-t":
            test_way = int(arg)
        elif (opt == "-h") or (opt == "--help"):
            usage()
            return

    method_name = ["CreateTx", "Query"][test_way]

    # run peer service with parameters
    logging.info("\nTry load test with: \nclient( " +
                 str(client) + " ) \npeer( " +
                 peer + " ) \nduration( " +
                 str(duration) + " seconds )\n")

    pool = Pool(processes=client)
    pool.map_async(client_process, (client*((peer, duration, method_name),)), callback=log_result)

    logging.debug("wait for duration")
    pool.close()
    pool.join()


def usage():
    print("\n====================================")
    print("USAGE: LoopChain Load Test Tool")
    print("python3 loadtool.py [option] [value] ...")
    print("------------------------------------")
    print("\noption list")
    print("------------------------------------")
    print("-d : set logging level to debug")
    print("-c or --client : num of dummy client")
    print("-p or --peer : peer target info (\"[IP]:[port]\")")
    print("-m or --mins : test duration (mins)")
    print("-t : test method (0:CreateTx, 1:Query)")
    print("-h or --help : show usage\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        usage()
    else:
        main(sys.argv[1:])
