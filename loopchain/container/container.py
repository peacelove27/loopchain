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
"""A module for containers on the loopchain """

import logging
import grpc
from enum import Enum
from concurrent import futures
from loopchain.rest_server import RestServer, RestServerRS
from loopchain import configure as conf
from loopchain.baseservice import CommonProcess

from loopchain.protos import loopchain_pb2_grpc


class ServerType(Enum):
    REST_RS = 1
    REST_PEER = 2
    GRPC = 3


class Container(CommonProcess):

    def __init__(self, port, type=ServerType.GRPC):
        CommonProcess.__init__(self)
        self._port = port
        self._type = type

    def run(self, conn):
        logging.debug("Container run...")

        if self._type == ServerType.GRPC:
            server = grpc.server(futures.ThreadPoolExecutor(max_workers=conf.MAX_WORKERS))
            loopchain_pb2_grpc.add_ContainerServicer_to_server(self, server)
            server.add_insecure_port('[::]:' + str(self._port))
        elif self._type == ServerType.REST_PEER:
            server = RestServer(self._port)
        else:
            server = RestServerRS(self._port)

        server.start()

        command = None
        while command != "quit":
            try:
                command, param = conn.recv()  # Queue 에 내용이 들어올 때까지 여기서 대기 된다. 따라서 Sleep 이 필요 없다.
                logging.debug("Container got: " + str(param))
            except Exception as e:
                logging.warning("Container conn.recv() error: " + str(e))

        if self._type == ServerType.GRPC:
            server.stop(0)
        else:
            server.stop()

        logging.info("Server Container Ended.")
