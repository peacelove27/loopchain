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
"""Send tx to leader. Store tx temporary while leader is broken"""

import logging
import json
import pickle
import queue
from enum import Enum

from loopchain.baseservice import ObjectManager, StubManager
from loopchain.container import Container
from loopchain.protos import loopchain_pb2, loopchain_pb2_grpc, message_code
from loopchain import configure as conf


class PeerProcessStatus(Enum):
    normal = 1
    leader_complained = 2


class TxService(Container, loopchain_pb2_grpc.ContainerServicer):

    def __init__(self, port):
        Container.__init__(self, port)
        self.__handler_map = {
            message_code.Request.status: self.__handler_status,
            message_code.Request.stop: self.__handler_stop,
            message_code.Request.tx_create: self.__handler_create_tx,
            message_code.Request.tx_connect_to_leader: self.__handler_connect_to_leader,
            message_code.Request.tx_connect_to_inner_peer: self.__handler_connect_to_inner_peer
        }
        self.__peer_id = None
        self.__stub_to_peer_service = None
        # ObjectManager().tx_service = self

        self.__stub_to_leader = None
        self.__stub_to_inner_peer = None
        self.__peer_status = PeerProcessStatus.normal
        self.__stored_tx = queue.Queue()

        self.start()

    def __create_tx_continue(self):
        # 저장된 작업이 있으면 전송한다.
        while not self.__stored_tx.empty():
            stored_tx_item = self.__stored_tx.get()
            result_add_tx = self.__stub_to_leader.call_in_times(
                "AddTx", loopchain_pb2.TxSend(tx=stored_tx_item), is_stub_reuse=True)
            if result_add_tx is None and result_add_tx.response_code != message_code.Response.success:
                self.__stored_tx.put(stored_tx_item)
                raise Exception(result_add_tx.message)

    def __handler_status(self, request, context):
        """Service Status

        """
        status = dict()
        status['status'] = message_code.Response.success
        status_json = json.dumps(status)
        logging.debug("TxService __handler_status %s : %s", request.message, status_json)

        return loopchain_pb2.Message(code=message_code.Response.success, meta=status_json)

    def __handler_stop(self, request, context):
        logging.debug("TxService handler stop...")
        self.stop()
        return loopchain_pb2.Message(code=message_code.Response.success)

    def __handler_create_tx(self, request, context):
        # logging.debug("TxService handler create tx")

        tx = request.object
        tx_object = pickle.loads(tx)

        # logging.debug(f"TxService got tx({tx_object.get_tx_hash()})")

        try:
            if self.__peer_status == PeerProcessStatus.leader_complained:
                self.__stored_tx.put(tx)
                logging.warning("Leader is complained your tx just stored in queue by temporally: "
                                + str(self.__stored_tx.qsize()))
            else:
                self.__create_tx_continue()
                result_add_tx = self.__stub_to_leader.call(
                    "AddTx", loopchain_pb2.TxSend(tx=tx), is_stub_reuse=True
                )
                if result_add_tx.response_code != message_code.Response.success:
                    raise Exception(result_add_tx.message)
        except Exception as e:
            logging.warning(f"in tx service create_tx target({self.__stub_to_leader.target}) Exception: " + str(e))
            self.__stored_tx.put(tx)
            self.__peer_status = PeerProcessStatus.leader_complained
            # TODO leader complain 방식 변경중 임시로 현재 트리거는 중단한다.
            # stub_to_self_peer.call_in_time(
            #     "NotifyLeaderBroken",
            #     loopchain_pb2.CommonRequest(request="Fail Add Tx to Leader")
            # )

        return loopchain_pb2.Message(code=message_code.Response.success)

    def __handler_connect_to_leader(self, request, context):
        logging.debug(f"TxService handler connect to leader({request.message})")

        leader_target = request.message
        self.__stub_to_leader = StubManager.get_stub_manager_to_server(
            leader_target, loopchain_pb2_grpc.PeerServiceStub,
            time_out_seconds=conf.CONNECTION_RETRY_TIMEOUT,
            is_allow_null_stub=True
        )

        self.__peer_status = PeerProcessStatus.normal

        # TODO block generator 연결 실패 조건 확인할 것
        if self.__stub_to_leader is None:
            return loopchain_pb2.Message(code=message_code.Response.fail_connect_to_leader)
        else:
            try:
                self.__create_tx_continue()
            except Exception as e:
                logging.warning("in tx service create tx continue() Exception: " + str(e))
                self.__peer_status = PeerProcessStatus.leader_complained
                return loopchain_pb2.Message(code=message_code.Response.fail_add_tx_to_leader)

        return loopchain_pb2.Message(code=message_code.Response.success)

    def __handler_connect_to_inner_peer(self, request, context):
        logging.debug(f"TxService handler connect to inner peer({request.message})")

        inner_peer_target = request.message
        # 자신을 생성한 부모 Peer 에 접속하기 위한 stub 을 만든다.
        # pipe 를 통한 return 은 pipe send 와 쌍이 맞지 않은 경우 오류를 발생시킬 수 있다.
        # 안전한 연결을 위하여 부모 프로세스와도 gRPC stub 을 이용하여 통신한다.
        self.__stub_to_inner_peer = StubManager.get_stub_manager_to_server(
            inner_peer_target, loopchain_pb2_grpc.InnerServiceStub,
            time_out_seconds=conf.CONNECTION_RETRY_TIMEOUT,
            is_allow_null_stub=True
        )
        logging.debug("try connect to inner peer: " + str(inner_peer_target))

        return loopchain_pb2.Message(code=message_code.Response.success)

    def Request(self, request, context):
        # logging.debug("TxService got request: " + str(request))

        if request.code in self.__handler_map.keys():
            return self.__handler_map[request.code](request, context)

        return loopchain_pb2.Message(code=message_code.Response.not_treat_message_code)
