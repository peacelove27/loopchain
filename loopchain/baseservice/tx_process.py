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

import json
import logging
import pickle
import queue
import time
from enum import Enum

from loopchain import configure as conf
from loopchain import utils as util
from loopchain.baseservice import ManageProcess, StubManager
from loopchain.protos import loopchain_pb2, loopchain_pb2_grpc, message_code


class PeerProcessStatus(Enum):
    normal = 1
    leader_complained = 2


class TxProcess(ManageProcess):
    """모든 Peer 로의 Broadcast 을 처리하는 Process
    등록된 Peer 들의 stub list 를 관리한다.
    """
    PROCESS_VARIABLE_STUB_TO_LEADER = "stub_to_leader"
    PROCESS_VARIABLE_STUB_TO_SELF_PEER = "stub_to_self_peer"
    PROCESS_VARIABLE_PEER_STATUS = "peer_status"

    def process_loop(self, manager_dic, manager_list):
        logging.info("Tx Process Start.")

        command = None
        stored_tx = queue.Queue()
        __process_variables = dict()
        __process_variables[self.PROCESS_VARIABLE_PEER_STATUS] = PeerProcessStatus.normal

        def create_tx_continue(stub_to_leader):
            # 저장된 작업이 있으면 전송한다.
            while not stored_tx.empty():
                stored_tx_item = stored_tx.get()
                result_add_tx = stub_to_leader.call_in_times(
                    "AddTx", loopchain_pb2.TxSend(tx=stored_tx_item), is_stub_reuse=True)
                if result_add_tx is None and result_add_tx.response_code != message_code.Response.success:
                    stored_tx.put(stored_tx_item)
                    raise Exception(result_add_tx.message)

        def __handler_create_tx(create_tx_param):
            stub_to_leader = __process_variables[self.PROCESS_VARIABLE_STUB_TO_LEADER]
            # logging.debug(f"TxProcess create_tx.... leader.target({stub_to_leader.target})")

            tx = pickle.dumps(create_tx_param)
            try:
                if __process_variables[self.PROCESS_VARIABLE_PEER_STATUS] == PeerProcessStatus.leader_complained:
                    stored_tx.put(tx)
                    logging.warning("Leader is complained your tx just stored in queue by temporally: "
                                    + str(stored_tx.qsize()))
                else:
                    create_tx_continue(stub_to_leader)
                    result_add_tx = stub_to_leader.call(
                        "AddTx", loopchain_pb2.TxSend(tx=tx), is_stub_reuse=True
                    )
                    if result_add_tx.response_code != message_code.Response.success:
                        raise Exception(result_add_tx.message)
            except Exception as e:
                logging.warning(
                    f"in peer_process::create_tx target({stub_to_leader.target}) Exception: " + str(e))
                stored_tx.put(tx)
                __process_variables[self.PROCESS_VARIABLE_PEER_STATUS] = PeerProcessStatus.leader_complained
                # TODO leader complain 방식 변경중 임시로 현재 트리거는 중단한다.
                # stub_to_self_peer.call_in_time(
                #     "NotifyLeaderBroken",
                #     loopchain_pb2.CommonRequest(request="Fail Add Tx to Leader")
                # )

        def __handler_connect_to_leader(connect_to_leader_param):
            # logging.debug("(tx process) try... connect to leader: " + str(connect_to_leader_param))
            stub_to_leader = StubManager.get_stub_manager_to_server(
                connect_to_leader_param, loopchain_pb2_grpc.PeerServiceStub,
                time_out_seconds=conf.CONNECTION_RETRY_TIMEOUT,
                is_allow_null_stub=True
            )
            __process_variables[self.PROCESS_VARIABLE_STUB_TO_LEADER] = stub_to_leader

            stub_to_self_peer = __process_variables[self.PROCESS_VARIABLE_STUB_TO_SELF_PEER]

            __process_variables[self.PROCESS_VARIABLE_PEER_STATUS] = PeerProcessStatus.normal
            # TODO block generator 연결 실패 조건 확인할 것
            if stub_to_leader is None:
                stub_to_self_peer.call(
                    "NotifyProcessError",
                    loopchain_pb2.CommonRequest(request="Connect to leader Fail!"))
            else:
                try:
                    create_tx_continue(stub_to_leader)
                except Exception as e:
                    logging.warning("in peer_process::connect_to_blockgenerator Exception: " + str(e))
                    __process_variables[self.PROCESS_VARIABLE_PEER_STATUS] = PeerProcessStatus.leader_complained
                    stub_to_self_peer.call(
                        "NotifyLeaderBroken",
                        loopchain_pb2.CommonRequest(request="Fail Add Tx to Leader")
                    )

        def __handler_connect_to_self_peer(connect_param):
            # 자신을 생성한 부모 Peer 에 접속하기 위한 stub 을 만든다.
            # pipe 를 통한 return 은 pipe send 와 쌍이 맞지 않은 경우 오류를 발생시킬 수 있다.
            # 안전한 연결을 위하여 부모 프로세스와도 gRPC stub 을 이용하여 통신한다.
            logging.debug("try connect to self peer: " + str(connect_param))

            stub_to_self_peer = StubManager.get_stub_manager_to_server(
                connect_param, loopchain_pb2_grpc.InnerServiceStub,
                time_out_seconds=conf.CONNECTION_RETRY_TIMEOUT,
                is_allow_null_stub=True
            )
            __process_variables[self.PROCESS_VARIABLE_STUB_TO_SELF_PEER] = stub_to_self_peer

            response = util.request_server_wait_response(
                stub_to_self_peer.stub.GetStatus,
                loopchain_pb2.StatusRequest(request="(tx process) connect to self peer"))
            logging.debug("connect to inner channel: " + str(response))

        def __handler_status(status_param):
            logging.debug("TxProcess Status, param: " + str(status_param))

            status = dict()
            status['result'] = message_code.get_response_msg(message_code.Response.success)
            status_json = json.dumps(status)

            # return way of manage_process
            manager_dic["status"] = status_json

        __handler_map = {
            "create_tx": __handler_create_tx,
            "connect_to_blockgenerator": __handler_connect_to_leader,
            "make_self_connection": __handler_connect_to_self_peer,
            "status": __handler_status
        }

        while command != ManageProcess.QUIT_COMMAND:
            # logging.debug(f"manager list: {manager_list}")
            try:
                if not manager_list:
                    time.sleep(conf.SLEEP_SECONDS_IN_SERVICE_LOOP)
                else:
                    # packet must be a tuple (command, param)
                    command, param = manager_list.pop()

                    if command in __handler_map.keys():
                        __handler_map[command](param)
                        continue

                    if command == ManageProcess.QUIT_COMMAND:
                        logging.debug(f"TxProcess peer({manager_dic[self.PROCESS_INFO_KEY]}) will quit soon.")
                    else:
                        logging.error("TxProcess received Unknown command: " +
                                      str(command) + " and param: " + str(param))
            except Exception as e:
                time.sleep(conf.SLEEP_SECONDS_IN_SERVICE_LOOP)
                logging.error(f"Tx process not available reason({e})")

        logging.info("Tx Process Ended.")
