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
"""gRPC service for Peer Inner Service"""

import re

import grpc

from grpc._channel import _Rendezvous

from loopchain.baseservice import ObjectManager
from loopchain.blockchain import *
from loopchain.protos import loopchain_pb2_grpc, message_code

# loopchain_pb2 를 아래와 같이 import 하지 않으면 broadcast 시도시 pickle 오류가 발생함
import loopchain_pb2


class InnerService(loopchain_pb2_grpc.InnerServiceServicer):
    """insecure gRPC service for inner process modules.
    """

    def __init__(self):
        self.__handler_map = {
            message_code.Request.status: self.__handler_status,
            message_code.Request.peer_peer_list: self.__handler_peer_list
        }

    @property
    def peer_service(self):
        return ObjectManager().peer_service

    def __handler_status(self, request, context):
        return loopchain_pb2.Message(code=message_code.Response.success)

    def __handler_peer_list(self, request, context):
        channel_name = conf.LOOPCHAIN_DEFAULT_CHANNEL if request.channel == '' else request.channel
        peer_manager = self.peer_service.channel_manager.get_peer_manager(channel_name)
        message = "All Group Peers count: " + str(len(peer_manager.peer_list[conf.ALL_GROUP_ID]))

        return loopchain_pb2.Message(
            code=message_code.Response.success,
            message=message,
            meta=str(peer_manager.peer_list))

    def Request(self, request, context):
        logging.debug("Peer Service got request: " + str(request))

        if request.code in self.__handler_map.keys():
            return self.__handler_map[request.code](request, context)

        return loopchain_pb2.Message(code=message_code.Response.not_treat_message_code)

    def GetStatus(self, request, context):
        """Peer 의 현재 상태를 요청한다.

        :param request:
        :param context:
        :return:
        """
        channel_name = conf.LOOPCHAIN_DEFAULT_CHANNEL if request.channel == '' else request.channel
        logging.debug("Inner Channel::Peer GetStatus : %s", request)
        peer_status = self.peer_service.common_service.getstatus(
            self.peer_service.channel_manager.get_block_manager(channel_name))

        return loopchain_pb2.StatusReply(
            status=json.dumps(peer_status),
            block_height=peer_status["block_height"],
            total_tx=peer_status["total_tx"],
            is_leader_complaining=peer_status['leader_complaint'])

    def GetScoreStatus(self, request, context):
        """Score Service 의 현재 상태를 요청 한다

        :param request:
        :param context:
        :return:
        """
        logging.debug("Peer GetScoreStatus request : %s", request)
        score_status = json.loads("{}")
        try:
            score_status_response = self.peer_service.stub_to_score_service.call(
                "Request",
                loopchain_pb2.Message(code=message_code.Request.status)
            )
            logging.debug("Get Score Status : " + str(score_status_response))
            if score_status_response.code == message_code.Response.success:
                score_status = json.loads(score_status_response.meta)

        except Exception as e:
            logging.debug("Score Service Already stop by other reason. %s", e)

        return loopchain_pb2.StatusReply(
            status=json.dumps(score_status),
            block_height=0,
            total_tx=0)

    def Stop(self, request, context):
        """Peer를 중지시킨다

        :param request: 중지요청
        :param context:
        :return: 중지결과
        """
        if request is not None:
            logging.info('Peer will stop... by: ' + request.reason)

        try:
            response = self.peer_service.stub_to_score_service.call(
                "Request",
                loopchain_pb2.Message(code=message_code.Request.stop)
            )
            logging.debug("try stop score container: " + str(response))
        except Exception as e:
            logging.debug("Score Service Already stop by other reason. %s", e)

        self.peer_service.service_stop()
        return loopchain_pb2.StopReply(status="0")

    def Echo(self, request, context):
        """gRPC 기본 성능을 확인하기 위한 echo interface, loopchain 기능과는 무관하다.

        :return: request 를 message 되돌려 준다.
        """
        return loopchain_pb2.CommonReply(response_code=message_code.Response.success,
                                         message=request.request)

    def GetBlock(self, request, context):
        """Block 정보를 조회한다.

        :param request: loopchain.proto 의 GetBlockRequest 참고
         request.block_hash: 조회할 block 의 hash 값, "" 로 조회하면 마지막 block 의 hash 값을 리턴한다.
         request.block_data_filter: block 정보 중 조회하고 싶은 key 값 목록 "key1, key2, key3" 형식의 string
         request.tx_data_filter: block 에 포함된 transaction(tx) 중 조회하고 싶은 key 값 목록
        "key1, key2, key3" 형식의 string
        :param context:
        :return: loopchain.proto 의 GetBlockReply 참고,
        block_hash, block 정보 json, block 에 포함된 tx 정보의 json 리스트를 받는다.
        포함되는 정보는 param 의 filter 에 따른다.
        """
        # Peer To Client
        block_hash = request.block_hash
        block = None

        channel_name = conf.LOOPCHAIN_DEFAULT_CHANNEL if request.channel == '' else request.channel
        block_manager = self.peer_service.channel_manager.get_block_manager(channel_name)

        if request.block_hash == "" and request.block_height == -1:
            block_hash = block_manager.get_blockchain().last_block.block_hash

        block_filter = re.sub(r'\s', '', request.block_data_filter).split(",")
        tx_filter = re.sub(r'\s', '', request.tx_data_filter).split(",")
        logging.debug("block_filter: " + str(block_filter))
        logging.debug("tx_filter: " + str(tx_filter))

        block_data_json = json.loads("{}")

        if block_hash != "":
            block = block_manager.get_blockchain().find_block_by_hash(block_hash)
        elif request.block_height != -1:
            block = block_manager.get_blockchain().find_block_by_height(request.block_height)

        if block is None:
            return loopchain_pb2.GetBlockReply(response_code=message_code.Response.fail_wrong_block_hash,
                                               block_hash=block_hash,
                                               block_data_json="",
                                               tx_data_json="")

        for key in block_filter:
            try:
                block_data_json[key] = str(getattr(block, key))
            except AttributeError:
                try:
                    getter = getattr(block, "get_" + key)
                    block_data_json[key] = getter()
                except AttributeError:
                    block_data_json[key] = ""

        tx_data_json_list = []
        for tx in block.confirmed_transaction_list:
            tx_data_json = json.loads("{}")
            for key in tx_filter:
                try:
                    tx_data_json[key] = str(getattr(tx, key))
                except AttributeError:
                    try:
                        getter = getattr(tx, "get_" + key)
                        tx_data_json[key] = getter()
                    except AttributeError:
                        tx_data_json[key] = ""
            tx_data_json_list.append(json.dumps(tx_data_json))

        block_hash = block.block_hash
        block_data_json = json.dumps(block_data_json)

        return loopchain_pb2.GetBlockReply(response_code=message_code.Response.success,
                                           block_hash=block_hash,
                                           block_data_json=block_data_json,
                                           tx_data_json=tx_data_json_list)

    def Query(self, request, context):
        """Score 의 invoke 로 생성된 data 에 대한 query 를 수행한다.

        """
        # TODO 입력값 오류를 검사하는 방법을 고려해본다, 현재는 json string 여부만 확인
        if util.check_is_json_string(request.params):
            logging.debug(f'Query request with {request.params}')
            try:
                response_from_score_service = self.peer_service.stub_to_score_service.call(
                    method_name="Request",
                    message=loopchain_pb2.Message(code=message_code.Request.score_query, meta=request.params),
                    timeout=conf.SCORE_QUERY_TIMEOUT,
                    is_raise=True
                )
                response = response_from_score_service.meta
            except Exception as e:
                logging.error(f'Execute Query Error : {e}')
                if isinstance(e, _Rendezvous):
                    # timeout 일 경우
                    if e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                        return loopchain_pb2.QueryReply(response_code=message_code.Response.timeout_exceed,
                                                        response="")
                return loopchain_pb2.QueryReply(response_code=message_code.Response.fail,
                                                response="")
        else:
            return loopchain_pb2.QueryReply(response_code=message_code.Response.fail_validate_params,
                                            response="")

        if util.check_is_json_string(response):
            # TODO 응답값 오류를 검사하는 방법을 고려해본다, 현재는 json string 여부만 확인
            response_code = message_code.Response.success
        else:
            response_code = message_code.Response.fail

        return loopchain_pb2.QueryReply(response_code=response_code,
                                        response=response)

    def Subscribe(self, request, context):
        """BlockGenerator 가 broadcast(unconfirmed or confirmed block) 하는 채널에
        Peer 를 등록한다.

        :param request:
        :param context:
        :return:
        """
        if request.peer_id == "":
            return loopchain_pb2.CommonReply(
                response_code=message_code.get_response_code(message_code.Response.fail_wrong_subscribe_info),
                message=message_code.get_response_msg(message_code.Response.fail_wrong_subscribe_info)
            )
        else:
            self.peer_service.common_service.add_audience(request)

        return loopchain_pb2.CommonReply(response_code=message_code.get_response_code(message_code.Response.success),
                                         message=message_code.get_response_msg(message_code.Response.success))

    def UnSubscribe(self, request, context):
        """BlockGenerator 의 broadcast 채널에서 Peer 를 제외한다.

        :param request:
        :param context:
        :return:
        """
        self.peer_service.common_service.remove_audience(request.peer_id, request.peer_target)
        return loopchain_pb2.CommonReply(response_code=0, message="success")

    def NotifyLeaderBroken(self, request, context):
        channel_name = conf.LOOPCHAIN_DEFAULT_CHANNEL if request.channel == '' else request.channel
        logging.debug("NotifyLeaderBroken: " + request.request)

        ObjectManager().peer_service.rotate_next_leader(channel_name)
        return loopchain_pb2.CommonReply(response_code=message_code.Response.success, message="success")

        # # TODO leader complain 알고리즘 변경 예정
        # # send complain leader message to new leader candidate
        # leader_peer = self.peer_service.peer_manager.get_leader_peer()
        # next_leader_peer, next_leader_peer_stub = self.peer_service.peer_manager.get_next_leader_stub_manager()
        # if next_leader_peer_stub is not None:
        #     next_leader_peer_stub.call_in_time(
        #         "ComplainLeader",
        #         loopchain_pb2.ComplainLeaderRequest(
        #             complained_leader_id=leader_peer.peer_id,
        #             new_leader_id=next_leader_peer.peer_id,
        #             message="complain leader peer")
        #     )
        #     #
        #     # next_leader_peer_stub.ComplainLeader(loopchain_pb2.ComplainLeaderRequest(
        #     #     complained_leader_id=leader_peer.peer_id,
        #     #     new_leader_id=next_leader_peer.peer_id,
        #     #     message="complain leader peer"
        #     # ), conf.GRPC_TIMEOUT)
        #
        #     return loopchain_pb2.CommonReply(response_code=message_code.Response.success, message="success")
        # else:
        #     # TODO 아래 상황 처리 정책 필요
        #     logging.warning("There is no next leader candidate")
        #     return loopchain_pb2.CommonReply(response_code=message_code.Response.fail,
        #                                      message="fail found next leader stub")

    def NotifyProcessError(self, request, context):
        """Peer Stop by Process Error
        """
        util.exit_and_msg(request.request)
        return loopchain_pb2.CommonReply(response_code=message_code.Response.success, message="success")
