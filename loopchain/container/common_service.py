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
"""Class for managing Peer and Radio station """

import leveldb
import logging
import os.path as osp
import pickle
import queue
import shutil
import time
import uuid
from concurrent import futures

import grpc

import loopchain.utils as util
from loopchain import configure as conf
from loopchain.baseservice import BroadcastProcess, CommonThread, ObjectManager, PeerManager
from loopchain.protos import loopchain_pb2, message_code


class CommonService(CommonThread):
    """Manage common part of 'Peer' and 'Radio station' especially broadcast service

    """

    def __init__(self, gRPC_module, level_db_identity="station",
                 inner_service_port=conf.PORT_PEER + conf.PORT_DIFF_INNER_SERVICE):
        # members for public (we don't use getter/setter but you can use @property for that)
        self.peer_id = ""
        self.inner_server = grpc.server(futures.ThreadPoolExecutor(max_workers=conf.MAX_WORKERS))
        self.outer_server = grpc.server(futures.ThreadPoolExecutor(max_workers=conf.MAX_WORKERS))

        # members for private, It helps simplicity of code intelligence
        self.__gRPC_module = gRPC_module
        self.__port = 0
        self.__inner_service_port = inner_service_port
        self.__peer_port = inner_service_port - conf.PORT_DIFF_INNER_SERVICE
        self.__subscriptions = queue.Queue()
        self.__peer_type = loopchain_pb2.PEER
        self.__peer_target = ""
        self.__stub_to_blockgenerator = None

        self.__group_id = ""
        self.__audience = {}  # { peer_id : peer_info(SubscribeRequest of gRPC) }

        # broadcast process
        self.__broadcast_process = self.__run_broadcast_process()
        self.__init_level_db(level_db_identity)

        self.__loop_functions = []

    def __init_level_db(self, level_db_identity):
        """init Level Db

        :param level_db_identity: identity for leveldb
        :return:
        """
        level_db = None

        db_default_path = osp.join(conf.DEFAULT_STORAGE_PATH, 'db_' + level_db_identity)
        db_path = db_default_path

        retry_count = 0
        while level_db is None and retry_count < conf.MAX_RETRY_CREATE_DB:
            try:
                level_db = leveldb.LevelDB(db_path, create_if_missing=True)
            except leveldb.LevelDBError:
                db_path = db_default_path + str(retry_count)
            retry_count += 1

        if level_db is None:
            logging.error("Common Service Create LevelDB if Fail ")
            raise leveldb.LevelDBError("Fail To Create Level DB(path): " + db_path)

        self.__level_db = level_db
        self.__level_db_path = db_path

    def get_peer_id(self):
        """네트워크에서 Peer 를 식별하기 위한 UUID를 level db 에 생성한다.
        """
        try:
            uuid_bytes = bytes(self.__level_db.Get(conf.LEVEL_DB_KEY_FOR_PEER_ID))
            peer_id = uuid.UUID(bytes=uuid_bytes)
        except KeyError:  # It's first Run
            peer_id = None

        if peer_id is None:
            peer_id = uuid.uuid1()
            logging.info("make new peer_id: " + str(peer_id))
            self.__level_db.Put(conf.LEVEL_DB_KEY_FOR_PEER_ID, peer_id.bytes)

        return str(peer_id)

    def clear_level_db(self):
        logging.debug(f"clear level db({self.__level_db_path})")
        shutil.rmtree(self.__level_db_path)

    def get_level_db(self):
        return self.__level_db

    def set_peer_type(self, peer_type):
        self.__peer_type = peer_type

    def save_peer_list(self, peer_list):
        """peer_list 를 leveldb 에 저장한다.

        :param peer_list:
        """
        try:
            dump = peer_list.dump()
            self.__level_db.Put(conf.LEVEL_DB_KEY_FOR_PEER_LIST, dump)
        except AttributeError as e:
            logging.warning("Fail Save Peer_list: " + str(e))

    def load_peer_manager(self):
        """leveldb 로 부터 peer_manager 를 가져온다.

        :return: peer_manager
        """
        peer_manager = PeerManager()

        try:
            peer_list_data = pickle.loads(self.__level_db.Get(conf.LEVEL_DB_KEY_FOR_PEER_LIST))
            peer_manager.load(peer_list_data)
            logging.debug("load peer_list_data on yours: " + peer_manager.get_peers_for_debug())
        except KeyError:
            logging.warning("There is no peer_list_data on yours")

        return peer_manager

    def getstatus(self, block_manager):
        """
        블럭체인의 상태 조회

        :param request: 상태조회
        :param context:
        :param block_manager: 블럭매니저
        :param score: 체인코드
        :return:
        """
        logging.debug("CommonService.getstatus")

        block_height = 0
        total_tx = 0

        status_data = dict()

        if block_manager is not None:
            status_data["made_block_count"] = block_manager.get_blockchain().made_block_count
            if block_manager.get_blockchain().last_block is not None:
                block_height = block_manager.get_blockchain().last_block.height
                logging.debug("getstatus block hash(block_manager.get_blockchain().last_block.block_hash): "
                              + str(block_manager.get_blockchain().last_block.block_hash))
                logging.debug("getstatus block hash(block_manager.get_blockchain().block_height): "
                              + str(block_manager.get_blockchain().block_height))
                logging.debug("getstatus block height: " + str(block_height))
                # Score와 상관없이 TransactionTx는 블럭매니저가 관리 합니다.
                total_tx = block_manager.get_total_tx()

        status_data["status"] = "Service is online: " + str(self.__peer_type)
        status_data["audience_count"] = self.__count_audience()
        status_data["consensus"] = str(conf.CONSENSUS_ALGORITHM.name)
        status_data["peer_id"] = str(self.get_peer_id())
        status_data["peer_type"] = str(self.__peer_type)
        status_data["block_height"] = block_height
        status_data["total_tx"] = total_tx
        status_data["peer_target"] = self.__peer_target

        return status_data

    def __run_broadcast_process(self):
        broadcast_process = BroadcastProcess()
        broadcast_process.start()
        broadcast_process.send_to_process(("status", ""))

        wait_times = 0
        wait_for_process_start = None

        while wait_for_process_start is None:
            time.sleep(conf.SLEEP_SECONDS_FOR_SUB_PROCESS_START)
            logging.debug(f"wait start broadcast process....")
            wait_for_process_start = broadcast_process.get_receive("status")

            if wait_for_process_start is None and wait_times > conf.WAIT_SUB_PROCESS_RETRY_TIMES:
                util.exit_and_msg("Broadcast Process start Fail!")

        logging.debug(f"Broadcast Process start({wait_for_process_start})")

        return broadcast_process

    def __stop_broadcast_process(self):
        self.__broadcast_process.stop()
        self.__broadcast_process.wait()

    def __subscribe(self, port, subscribe_stub, is_unsubscribe=False):
        self.__peer_target = util.get_private_ip() + ":" + str(port)
        # logging.info("peer_info: " + peer_target)
        # logging.info("subscribe_stub type: " + str(subscribe_stub.stub.__module__))

        try:
            if is_unsubscribe:
                subscribe_stub.call(
                    "UnSubscribe",
                    self.__gRPC_module.SubscribeRequest(
                        peer_target=self.__peer_target, peer_type=self.__peer_type,
                        peer_id=self.peer_id, group_id=self.__group_id
                    ),
                    is_stub_reuse=False
                )
            else:
                subscribe_stub.call(
                    "Subscribe",
                    self.__gRPC_module.SubscribeRequest(
                        peer_target=self.__peer_target, peer_type=self.__peer_type,
                        peer_id=self.peer_id, group_id=self.__group_id
                    ),
                    is_stub_reuse=False
                )

            logging.info(("Subscribe", "UnSubscribe")[is_unsubscribe])
        except Exception as e:
            logging.info("gRPC Exception: " + type(e).__name__)
            logging.error("Fail " + ("Subscribe", "UnSubscribe")[is_unsubscribe])

    def __un_subscribe(self, port, subscribe_stub):
        self.__subscribe(port, subscribe_stub, True)

    def __count_audience(self):
        return self.__audience.__len__()

    def get_voter_count(self):
        # TODO Check this if can remove?
        # peer_list 의 count 로 변경할 것
        return self.__count_audience() + 1  # leader 자신을 투표자 수에 포함한다.

    def add_audience(self, peer_info):
        """broadcast 를 수신 받을 peer 를 등록한다.
        :param peer_info: SubscribeRequest
        """
        logging.info("Try add audience: " + str(peer_info))
        self.__broadcast_process.send_to_process(("subscribe", peer_info.peer_target))
        self.__audience[peer_info.peer_id] = peer_info

    def remove_audience(self, peer_id, peer_target):
        logging.debug("Try remove audience: " + str(peer_target))
        self.__broadcast_process.send_to_process(("unsubscribe", peer_target))

        try:
            del self.__audience[peer_id]
        except KeyError:
            logging.warning("Already deleted peer: " + str(peer_id))

    def broadcast(self, method_name, method_param, response_handler=None):
        """등록된 모든 Peer 의 동일한 gRPC method 를 같은 파라미터로 호출한다.
        """
        logging.warning("broadcast in process ==========================")
        # logging.debug("pickle method_param: " + str(pickle.dumps(method_param)))
        self.__broadcast_process.send_to_process(("broadcast", (method_name, method_param)))

    def broadcast_audience_set(self):
        self.__broadcast_process.send_to_process(("status", "audience set"))

    def start(self, port, peer_id="", group_id=""):
        self.__port = port
        self.peer_id = peer_id
        self.__group_id = group_id
        CommonThread.start(self)
        self.__broadcast_process.set_to_process(BroadcastProcess.PROCESS_INFO_KEY, f"peer_id({self.get_peer_id()})")

    def subscribe(self, subscribe_stub, type=None):
        self.__subscribe(self.__port, subscribe_stub)
        self.__subscriptions.put(subscribe_stub)

        if type == loopchain_pb2.BLOCK_GENERATOR:
            self.__stub_to_blockgenerator = subscribe_stub

    def vote_unconfirmed_block(self, block_hash, is_validated):
        logging.debug("vote_unconfirmed_block ....")
        if is_validated:
            vote_code, message = message_code.get_response(message_code.Response.success_validate_block)
        else:
            vote_code, message = message_code.get_response(message_code.Response.fail_validate_block)

        if self.__stub_to_blockgenerator is not None:
            self.__stub_to_blockgenerator.call(
                "VoteUnconfirmedBlock",
                loopchain_pb2.BlockVote(
                    vote_code=vote_code,
                    message=message,
                    block_hash=block_hash,
                    peer_id=ObjectManager().peer_service.peer_id,
                    group_id=ObjectManager().peer_service.group_id)
            )
        else:
            logging.error("No block generator stub!")

    def start_server(self, server, listen_address):
        server.add_insecure_port(listen_address)
        server.start()
        logging.info("Server now listen: " + listen_address)

    def add_loop(self, loop_function):
        self.__loop_functions.append(loop_function)

    def __run_loop_functions(self):
        for loop_function in self.__loop_functions:
            loop_function()

    def run(self):
        self.start_server(self.outer_server, '[::]:' + str(self.__port))
        if self.__inner_service_port is not None:
            # Bind Only loopback address (ip4) - TODO IP6
            self.start_server(self.inner_server, conf.INNER_SERVER_BIND_IP + ':' + str(self.__inner_service_port))

        # Block Generator 에 subscribe 하게 되면 Block Generator 는 peer 에 channel 생성을 요청한다.
        # 따라서 peer 의 gRPC 서버가 완전히 시작된 후 Block Generator 로 subscribe 요청을 하여야 한다.
        time.sleep(conf.WAIT_GRPC_SERVICE_START)

        try:
            while self.is_run():
                self.__run_loop_functions()
                time.sleep(conf.SLEEP_SECONDS_IN_SERVICE_NONE)
        except KeyboardInterrupt:
            logging.info("Server Stop by KeyboardInterrupt")
        finally:
            while not self.__subscriptions.empty():
                logging.info("Un subscribe to server...")
                subscribe_stub = self.__subscriptions.get()
                self.__un_subscribe(self.__port, subscribe_stub)

            self.__stop_broadcast_process()

            if self.__inner_service_port is not None:
                self.inner_server.stop(0)
            self.outer_server.stop(0)

        logging.info("Server thread Ended.")
