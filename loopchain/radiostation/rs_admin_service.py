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
""" A class for gRPC service of Radio station """

import json
import logging
import pickle

import loopchain.utils as util
from loopchain import configure as conf
from loopchain.baseservice import PeerStatus, PeerInfo, ObjectManager
from loopchain.protos import loopchain_pb2_grpc, message_code

# loopchain_pb2 를 아래와 같이 import 하지 않으면 broadcast 시도시 pickle 오류가 발생함
import loopchain_pb2


class AdminService(loopchain_pb2_grpc.RadioStationServicer):
    """Radiostation의 gRPC service를 구동하는 Class.
    """

    def __init__(self):
        self.__handler_map = {
            message_code.Request.status: self.__handler_status,
            message_code.Request.rs_send_channel_manage_info_to_rs: self.__handler_rs_send_channel_manage_info_to_rs
        }

    def __handler_status(self, request: loopchain_pb2.Message, context):
        util.logger.spam(f"rs_admin_service:__handler_status ({request.message})")
        return loopchain_pb2.Message(code=message_code.Response.success)

    def __handler_rs_send_channel_manage_info_to_rs(self, request, context):
        """

        :param request.code: message_code.Request.rs_send_channel_manage_info_to_rs
        :param request.meta: channel_manage_info
        :param request.message: from gtool or another rs
        """
        util.logger.spam(f"rs_admin_service:__handler_rs_send_channel_manage_info_to_rs")

        # TODO rs 의 admin_manager 에 channel_manage_info 반영, 자신의 json 파일에도 반영

        # TODO 이 메시지가 gtool 에서 왔다면, 다른 rs 에도 전송한다.(rs 이중화 완료까지 보류) 이때는 메시지를 변경하여 출처를 gtool 이 아닌 rs 로 수정한다.

        return loopchain_pb2.Message(code=message_code.Response.success)

    def Request(self, request, context):
        logging.debug("RadioStationService got request: " + str(request))

        if request.code in self.__handler_map.keys():
            return self.__handler_map[request.code](request, context)

        return loopchain_pb2.Message(code=message_code.Response.not_treat_message_code)
