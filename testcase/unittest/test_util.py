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
"""util functions for unittest"""

import leveldb
import logging
import multiprocessing
import os
import random
import time
from sys import platform

import grpc

import loopchain
import loopchain.utils as util
from loopchain import configure as conf
from loopchain.baseservice import ObjectManager, StubManager
from loopchain.baseservice.SingletonMetaClass import *
from loopchain.container import ScoreService
from loopchain.peer import PeerService
from loopchain.protos import loopchain_pb2, loopchain_pb2_grpc
from loopchain.radiostation import RadioStationService

util.set_log_level_debug()


def run_peer_server(port, radiostation_port=conf.PORT_RADIOSTATION, group_id=None, score=None):
    ObjectManager().peer_service = PeerService(group_id, conf.IP_RADIOSTATION, radiostation_port)

    if score is not None:
        ObjectManager().peer_service.set_chain_code(score)

    conf.DEFAULT_SCORE_REPOSITORY_PATH = \
        os.path.join(os.path.dirname(__file__), '..', '..', 'resources', 'test_score_repository')
    try:
        ObjectManager().peer_service.serve(port, conf.DEFAULT_SCORE_PACKAGE)
    except FileNotFoundError:
        logging.debug("Score Load Fail")
        # test 코드 실행 위치에 따라서(use IDE or use console) 경로 문제가 발생 할 수 있다.
        # ObjectManager().peer_service.serve(port, score_path)


def run_radio_station(port):
    server = RadioStationService()
    server.serve(port)


def run_score_server(port):
    ScoreService(port)


def run_peer_server_as_process(port, radiostation_port=conf.PORT_RADIOSTATION, group_id=None, score=None):
    process = multiprocessing.Process(target=run_peer_server, args=(port, radiostation_port, group_id, score,))
    process.start()
    time.sleep(1)
    return process


def run_peer_server_as_process_and_stub(port, radiostation_port=conf.PORT_RADIOSTATION, group_id=None, score=None):
    process = run_peer_server_as_process(port, radiostation_port, group_id, score)
    channel = grpc.insecure_channel('localhost:' + str(port))
    stub = loopchain_pb2_grpc.PeerServiceStub(channel)
    util.request_server_in_time(stub.GetStatus, loopchain_pb2.StatusRequest(request=""))
    return process, stub


def run_peer_server_as_process_and_stub_manager(
        port, radiostation_port=conf.PORT_RADIOSTATION, group_id=None, score=None):
    process = run_peer_server_as_process(port, radiostation_port, group_id, score)
    stub_manager = StubManager.get_stub_manager_to_server(
        'localhost:' + str(port), loopchain_pb2_grpc.PeerServiceStub)
    return process, stub_manager


def run_radio_station_as_process(port):
    process = multiprocessing.Process(target=run_radio_station, args=(port,))
    process.start()
    time.sleep(1)
    return process


def run_radio_station_as_process_and_stub_manager(port):
    process = run_radio_station_as_process(port)
    stub_manager = StubManager.get_stub_manager_to_server(
        'localhost:' + str(port), loopchain_pb2_grpc.RadioStationStub)
    util.request_server_in_time(stub_manager.stub.GetStatus, loopchain_pb2.StatusRequest(request=""))
    return process, stub_manager


def run_radio_station_as_process_and_stub(port):
    process = run_radio_station_as_process(port)
    channel = grpc.insecure_channel('localhost:' + str(port))
    stub = loopchain_pb2_grpc.RadioStationStub(channel)
    util.request_server_in_time(stub.GetStatus, loopchain_pb2.StatusRequest(request=""))
    return process, stub


def run_score_server_as_process(port):
    process = multiprocessing.Process(target=run_score_server, args=(port,))
    process.start()
    time.sleep(1)
    return process


def print_testname(testname):
    print("\n======================================================================")
    print("Test %s Start" % testname)
    print("======================================================================")


def make_level_db(db_name=""):
    db_default_path = './' + (db_name, "db_test")[db_name == ""]
    db_path = db_default_path
    blockchain_db = None
    retry_count = 0

    while blockchain_db is None and retry_count < conf.MAX_RETRY_CREATE_DB:
        try:
            blockchain_db = leveldb.LevelDB(db_path, create_if_missing=True)
            logging.debug("make level db path: " + db_path)
        except leveldb.LevelDBError:
            db_path = db_default_path + str(retry_count)
        retry_count += 1

    return blockchain_db


def close_open_python_process():
    # ubuntu patch
    if platform == "darwin":
        os.system("pkill -f python")
    else:
        os.system("pgrep -f python | tail -$((`pgrep -f python | wc -l` - 1)) | xargs kill -9")


def clean_up_temp_db_files(kill_process=True):
    module_root_path = os.path.dirname(loopchain.__file__) + "/.."
    if kill_process:
        close_open_python_process()

    os.system(f'rm -rf $(find {module_root_path} -name db_*)')
    os.system(f'rm -rf $(find {module_root_path} -name *test_db*)')
    os.system(f'rm -rf $(find {module_root_path} -name *_block)')
    os.system("rm -rf ./testcase/db_*")
    os.system("rm -rf chaindb_*")
    os.system("rm -rf ./blockchain_db*")
    os.system("rm -rf ./testcase/chaindb_*")
    os.system("rm -rf sample_score")
    os.system("rm -rf ./testcase/sample_score")
    os.system("rm -rf certificate_db")
    os.system("rm -rf ./resources/test_score_deploy")
    os.system("rm -rf ./resources/test_score_repository/loopchain")
    time.sleep(1)


class TestServerManager(metaclass=SingletonMetaClass):
    """

    """

    def __init__(self):
        self.__test_port_diff = random.randrange(1, 30) * -50
        self.__radiostation_port = conf.PORT_RADIOSTATION + self.__test_port_diff

        # rs and peer info is tuple (process, stub_manager, port)
        self.__rs_info = ()
        self.__peer_info = {}  # {num:peer_info}
        self.__score = None

    def start_servers(self, peer_count, score=None):
        """Start BlockChain network rs and peer

        :param peer_count: num of peers but 0 means start only RS.
        :return:
        """
        logging.debug("TestServerManager start servers")
        self.__score = score

        # run radio station
        process, stub_manager = run_radio_station_as_process_and_stub_manager(self.__radiostation_port)
        self.__rs_info = (process, stub_manager, self.__radiostation_port)
        time.sleep(2)

        for i in range(peer_count):
            peer_port = conf.PORT_PEER + (i * 7) + self.__test_port_diff
            process, stub_manager = run_peer_server_as_process_and_stub_manager(
                peer_port, self.__radiostation_port, score=score)
            self.__peer_info[i] = (process, stub_manager, peer_port)
            time.sleep(2)

    def stop_all_server(self):
        for i in self.__peer_info:
            self.__peer_info[i][1].call_in_times(
                "Stop",
                loopchain_pb2.StopRequest(reason="TestServerManager"), conf.GRPC_TIMEOUT)
        self.__rs_info[1].call_in_times(
            "Stop",
            loopchain_pb2.StopRequest(reason="TestServerManager"), conf.GRPC_TIMEOUT)

        time.sleep(2)

        for i in self.__peer_info:
            self.__peer_info[i][0].join()
        self.__rs_info[0].join()

    def stop_peer(self, num):
        self.__peer_info[num][1].call_in_times(
            "Stop",
            loopchain_pb2.StopRequest(reason="TestServerManager"), conf.GRPC_TIMEOUT)
        time.sleep(2)
        self.__peer_info[num][0].join()

    def start_peer(self, num):
        peer_port = conf.PORT_PEER + (num * 7) + self.__test_port_diff
        process, stub_manager = run_peer_server_as_process_and_stub_manager(
            peer_port, self.__radiostation_port, score=self.__score)
        self.__peer_info[num] = (process, stub_manager, peer_port)
        time.sleep(1)

    def start_black_peers(self, peer_count):
        pass

    def add_peer(self):
        num = 0
        return num

    def add_black_peer(self):
        num = 0
        return num

    def get_stub_rs(self):
        return self.__rs_info[1].stub

    def get_stub_peer(self, num=0):
        return self.__peer_info[num][1].stub

    def get_port_rs(self):
        return self.__radiostation_port

    def get_port_peer(self, num):
        return self.__peer_info[num][2]

    def status(self):
        """

        :return: json object for ServerManager status
        """
        pass
