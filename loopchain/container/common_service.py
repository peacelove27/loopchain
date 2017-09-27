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

import logging
import queue
import time
from concurrent import futures

import grpc

import loopchain.utils as util
from loopchain import configure as conf
from loopchain.baseservice import BroadcastProcess, CommonThread, ObjectManager
from loopchain.protos import loopchain_pb2, message_code

# loopchain_pb2 를 아래와 같이 import 하지 않으면 broadcast 시도시 pickle 오류가 발생함
import loopchain_pb2


class CommonService(CommonThread):
    """Manage common part of 'Peer' and 'Radio station' especially broadcast service

    """

    def __init__(self, gRPC_module, inner_service_port=conf.PORT_PEER + conf.PORT_DIFF_INNER_SERVICE):
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
        self.__peer_target = util.get_private_ip() + ":" + str(self.__peer_port)
        self.__stub_to_blockgenerator = None
        self.__group_id = ""

        # broadcast process
        self.__broadcast_process = self.__run_broadcast_process()

        self.__loop_functions = []

    @property
    def broadcast_process(self):
        return self.__broadcast_process

    def set_peer_id(self, peer_id):
        """set peer id

        """
        self.peer_id = peer_id

    def get_peer_id(self):
        return self.peer_id

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

        status_data["status"] = "Service is online: " + str(block_manager.peer_type)

        # TODO 더이상 사용하지 않는다. REST API 업데이트 후 제거할 것
        status_data["audience_count"] = "0"

        status_data["consensus"] = str(conf.CONSENSUS_ALGORITHM.name)
        status_data["peer_id"] = str(self.get_peer_id())
        status_data["peer_type"] = str(block_manager.peer_type)
        status_data["block_height"] = block_height
        status_data["total_tx"] = total_tx
        status_data["peer_target"] = self.__peer_target
        if ObjectManager().peer_service is not None:
            # TODO tx service 는 더이상 사용되지 않는다. 아래 코드는 의도에 맞게 다시 작성되어야 한다.
            # status_data["leader_complaint"] = ObjectManager().peer_service.tx_service.peer_status.value
            status_data["leader_complaint"] = 1

        return status_data

    def __run_broadcast_process(self):
        broadcast_process = BroadcastProcess()
        broadcast_process.start()
        broadcast_process.send_to_process(("status", ""))

        wait_times = 0
        wait_for_process_start = None

        # TODO process wait loop 를 살리고 시간을 조정하였음, 이 상태에서 tx process 가 AWS infra 에서 시작되는지 확인 필요.
        # time.sleep(conf.WAIT_SECONDS_FOR_SUB_PROCESS_START)

        while wait_for_process_start is None:
            time.sleep(conf.SLEEP_SECONDS_FOR_SUB_PROCESS_START)
            logging.debug(f"wait start broadcast process....")
            wait_for_process_start = broadcast_process.get_receive("status")

            if wait_for_process_start is None and wait_times > conf.WAIT_SUB_PROCESS_RETRY_TIMES:
                util.exit_and_msg("Broadcast Process start Fail!")

        logging.debug(f"Broadcast Process start({wait_for_process_start})")
        broadcast_process.send_to_process((BroadcastProcess.MAKE_SELF_PEER_CONNECTION_COMMAND, self.__peer_target))

        return broadcast_process

    def __stop_broadcast_process(self):
        self.__broadcast_process.stop()
        self.__broadcast_process.wait()

    def __subscribe(self, port, subscribe_stub, is_unsubscribe=False, channel_name=conf.LOOPCHAIN_DEFAULT_CHANNEL):
        # self.__peer_target = util.get_private_ip() + ":" + str(port)
        # logging.debug("peer_info: " + self.__peer_target)
        # logging.debug("subscribe_stub type: " + str(subscribe_stub.stub.__module__))

        # Subscribe 는 peer 의 type 정보를 사용하지 않지만, PeerRequest 의 required 값이라 임의의 type 정보를 할당한다.
        subscribe_peer_type = loopchain_pb2.PEER

        try:
            if is_unsubscribe:
                subscribe_stub.call(
                    "UnSubscribe",
                    self.__gRPC_module.PeerRequest(
                        channel=channel_name,
                        peer_target=self.__peer_target, peer_type=subscribe_peer_type,
                        peer_id=self.peer_id, group_id=self.__group_id
                    ),
                    is_stub_reuse=False
                )
            else:
                subscribe_stub.call(
                    "Subscribe",
                    self.__gRPC_module.PeerRequest(
                        channel=channel_name,
                        peer_target=self.__peer_target, peer_type=subscribe_peer_type,
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

    def add_audience(self, peer_info):
        """broadcast 를 수신 받을 peer 를 등록한다.
        :param peer_info: SubscribeRequest
        """
        # prevent to show certificate content
        # logging.debug("Try add audience: " + str(peer_info))
        if ObjectManager().peer_service is not None:
            ObjectManager().peer_service.tx_process.send_to_process(
                (BroadcastProcess.SUBSCRIBE_COMMAND, peer_info.peer_target))
        self.__broadcast_process.send_to_process((BroadcastProcess.SUBSCRIBE_COMMAND, peer_info.peer_target))

    def remove_audience(self, peer_id, peer_target):
        logging.debug("Try remove audience: " + str(peer_target))
        if ObjectManager().peer_service is not None:
            ObjectManager().peer_service.tx_process.send_to_process((BroadcastProcess.UNSUBSCRIBE_COMMAND, peer_target))
        self.__broadcast_process.send_to_process((BroadcastProcess.UNSUBSCRIBE_COMMAND, peer_target))

    def update_audience(self, peer_manager_dump):
        self.__broadcast_process.send_to_process((BroadcastProcess.UPDATE_AUDIENCE_COMMAND, peer_manager_dump))

    def broadcast(self, method_name, method_param, response_handler=None):
        """등록된 모든 Peer 의 동일한 gRPC method 를 같은 파라미터로 호출한다.
        """
        # logging.warning("broadcast in process ==========================")
        # logging.debug("pickle method_param: " + str(pickle.dumps(method_param)))
        self.__broadcast_process.send_to_process((BroadcastProcess.BROADCAST_COMMAND, (method_name, method_param)))

    def broadcast_audience_set(self):
        self.__broadcast_process.send_to_process((BroadcastProcess.STATUS_COMMAND, "audience set"))

    def start(self, port, peer_id="", group_id=""):
        self.__port = port
        self.peer_id = peer_id
        self.__group_id = group_id
        CommonThread.start(self)
        self.__broadcast_process.set_to_process(BroadcastProcess.PROCESS_INFO_KEY, f"peer_id({self.get_peer_id()})")

    def subscribe(self, subscribe_stub, type=None, channel_name=conf.LOOPCHAIN_DEFAULT_CHANNEL):
        self.__subscribe(port=self.__port, subscribe_stub=subscribe_stub, channel_name=channel_name)
        self.__subscriptions.put(subscribe_stub)

        if type == loopchain_pb2.BLOCK_GENERATOR or type == loopchain_pb2.PEER:
            # tx broadcast 를 위해서 leader 인 경우 자신의 audience 에 같이 추가를 한다.
            self.__broadcast_process.send_to_process((BroadcastProcess.SUBSCRIBE_COMMAND, subscribe_stub.target))
            self.__stub_to_blockgenerator = subscribe_stub

    def vote_unconfirmed_block(self, block_hash, is_validated, channel_name=conf.LOOPCHAIN_DEFAULT_CHANNEL):
        logging.debug("vote_unconfirmed_block ....")
        if is_validated:
            vote_code, message = message_code.get_response(message_code.Response.success_validate_block)
        else:
            vote_code, message = message_code.get_response(message_code.Response.fail_validate_block)

        if self.__stub_to_blockgenerator is not None:
            block_vote = loopchain_pb2.BlockVote(
                vote_code=vote_code,
                channel=channel_name,
                message=message,
                block_hash=block_hash,
                peer_id=ObjectManager().peer_service.peer_id,
                group_id=ObjectManager().peer_service.group_id)

            if conf.CONSENSUS_ALGORITHM == conf.ConsensusAlgorithm.lft:
                self.broadcast("VoteUnconfirmedBlock", block_vote)
            else:
                self.__stub_to_blockgenerator.call("VoteUnconfirmedBlock", block_vote)
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
