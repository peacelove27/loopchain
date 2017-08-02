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
"""A module for restful API server of Peer"""

import json
import grpc
import logging
import ssl
import _ssl

from loopchain.baseservice.SingletonMetaClass import *
from loopchain.baseservice import CommonThread
from flask import Flask, request
from flask_restful import reqparse, Api, Resource
from loopchain.protos import loopchain_pb2, loopchain_pb2_grpc, message_code
from loopchain import configure as conf


class ServerComponents(metaclass=SingletonMetaClass):
    def __init__(self):
        self.__app = Flask(__name__)
        self.__api = Api(self.__app)
        self.__parser = reqparse.RequestParser()
        self.__stub_to_peer_service = None

        # SSL 적용 여부에 따라 context 생성 여부를 결정한다.
        if conf.ENABLE_REST_SSL == 0:
            self.__ssl_context = None
        elif conf.ENABLE_REST_SSL == 1:
            self.__ssl_context = (conf.DEFAULT_SSL_CERT_PATH, conf.DEFAULT_SSL_KEY_PATH)
        else:
            self.__ssl_context = ssl.SSLContext(_ssl.PROTOCOL_SSLv23)

            self.__ssl_context.verify_mode = ssl.CERT_REQUIRED
            self.__ssl_context.check_hostname = False

            self.__ssl_context.load_verify_locations(cafile=conf.DEFAULT_SSL_TRUST_CERT_PATH)
            self.__ssl_context.load_cert_chain(conf.DEFAULT_SSL_CERT_PATH, conf.DEFAULT_SSL_KEY_PATH)

    @property
    def app(self):
        return self.__app

    @property
    def api(self):
        return self.__api

    @property
    def parser(self):
        return self.__parser

    @property
    def stub(self):
        return self.__stub_to_peer_service

    @property
    def ssl_context(self):
        return self.__ssl_context

    def set_stub_port(self, port):
        self.__stub_to_peer_service = loopchain_pb2_grpc.PeerServiceStub(grpc.insecure_channel(conf.IP_LOCAL + ':' + str(port)))

    def set_argument(self):
        self.__parser.add_argument('hash')

    def set_resource(self):
        self.__api.add_resource(Query, '/api/v1/query')
        self.__api.add_resource(Transaction, '/api/v1/transactions')
        self.__api.add_resource(Status, '/api/v1/status/peer')
        self.__api.add_resource(ScoreStatus, '/api/v1/status/score')
        self.__api.add_resource(Blocks, '/api/v1/blocks')
        self.__api.add_resource(InvokeResult, '/api/v1/transactions/result')

    def query(self, data):
        return self.__stub_to_peer_service.Query(loopchain_pb2.QueryRequest(params=data), conf.GRPC_TIMEOUT)

    def create_transaction(self, data):
        return self.__stub_to_peer_service.CreateTx(loopchain_pb2.CreateTxRequest(data=data), conf.GRPC_TIMEOUT)

    def get_transaction(self, tx_hash):
        return self.__stub_to_peer_service.GetTx(loopchain_pb2.GetTxRequest(tx_hash=tx_hash), conf.GRPC_TIMEOUT)

    def get_invoke_result(self, tx_hash):
        return self.__stub_to_peer_service.GetInvokeResult(loopchain_pb2.GetInvokeResultRequest(tx_hash=tx_hash),
                                                           conf.GRPC_TIMEOUT)

    def get_status(self):
        return self.__stub_to_peer_service.GetStatus(loopchain_pb2.StatusRequest(request=""), conf.GRPC_TIMEOUT)

    def get_score_status(self):
        return self.__stub_to_peer_service.GetScoreStatus(loopchain_pb2.StatusRequest(request=""), conf.GRPC_TIMEOUT)

    def get_block(self, block_hash="", block_height=-1,
                  block_data_filter="prev_block_hash, height, block_hash",
                  tx_data_filter="tx_hash"):

        response = self.__stub_to_peer_service.GetBlock(
            loopchain_pb2.GetBlockRequest(
                block_hash=block_hash,
                block_height=block_height,
                block_data_filter=block_data_filter,
                tx_data_filter=tx_data_filter))

        return response

    def get_last_block_hash(self):
        response = self.__stub_to_peer_service.GetLastBlockHash(
            loopchain_pb2.CommonRequest(request=""), conf.GRPC_TIMEOUT)
        return str(response.block_hash)

    def get_block_by_hash(self, block_hash="",
                          block_data_filter="prev_block_hash, merkle_tree_root_hash, \
                                            time_stamp, height, peer_id",
                          tx_data_filter="tx_hash, timestamp, data_string, peer_id"):
        return self.get_block(block_hash, -1, block_data_filter, tx_data_filter)


class Query(Resource):
    def post(self):
        request_body = json.dumps(request.get_json())
        response = ServerComponents().query(request_body)

        query_data = json.loads('{}')
        query_data['response_code'] = str(response.response_code)
        try:
            query_data['response'] = json.loads(response.response)
        except json.JSONDecodeError as e:
            logging.warning("your response is not json, your response(" + str(response.response) + ")")
            query_data['response'] = response.response

        return query_data


class Transaction(Resource):
    def get(self):
        args = ServerComponents().parser.parse_args()
        response = ServerComponents().get_transaction(args['hash'])
        tx_data = json.loads('{}')
        tx_data['response_code'] = str(response.response_code)
        tx_data['data'] = ""
        if len(response.data) is not 0:
            try:
                tx_data['data'] = json.loads(response.data)
            except json.JSONDecodeError as e:
                logging.warning("your data is not json, your data(" + str(response.data) + ")")
                tx_data['data'] = response.data

        tx_data['meta'] = ""
        if len(response.meta) is not 0:
            tx_data['meta'] = json.loads(response.meta)

        tx_data['more_info'] = response.more_info

        return tx_data

    def post(self):
        request_body = json.dumps(request.get_json())
        response = ServerComponents().create_transaction(request_body)

        tx_data = json.loads('{}')
        tx_data['response_code'] = str(response.response_code)
        tx_data['tx_hash'] = response.tx_hash
        tx_data['more_info'] = response.more_info

        return tx_data


class InvokeResult(Resource):
    def get(self):
        logging.debug('transaction result')
        args = ServerComponents().parser.parse_args()
        logging.debug('tx_hash : ' + args['hash'])
        response = ServerComponents().get_invoke_result(args['hash'])
        verify_result = dict()
        verify_result['response_code'] = str(response.response_code)
        if len(response.result) is not 0:
            try:
                result = json.loads(response.result)
                result['jsonrpc'] = '2.0'
                verify_result['response'] = result
            except json.JSONDecodeError as e:
                logging.warning("your data is not json, your data(" + str(response.data) + ")")
                verify_result['response_code'] = message_code.Response.fail
        else :
            verify_result['response_code'] = str(message_code.Response.fail)
        return verify_result


class Status(Resource):
    def get(self):
        response = ServerComponents().get_status()
        status_json_data = json.loads(response.status)
        return status_json_data


class ScoreStatus(Resource):
    def get(self):
        response = ServerComponents().get_score_status()
        status_json_data = json.loads(response.status)
        return status_json_data


class Blocks(Resource):
    def get(self):
        args = ServerComponents().parser.parse_args()

        if not args['hash'] is None:
            block_hash = args['hash']
            response = ServerComponents().get_block_by_hash(block_hash)
            block_data = json.loads('{}')
            block_data['block_hash'] = response.block_hash
            block_data['block_data_json'] = json.loads(response.block_data_json)

            if len(response.tx_data_json) < 1:
                block_data['tx_data_json'] = ''
            else:
                tx_data = json.loads('[]')
                tx_json_data = response.tx_data_json

                for i in range(0, len(tx_json_data)):
                    tx_data.append(json.loads(tx_json_data[i]))

                block_data['tx_data_json'] = json.loads(json.dumps(tx_data))

        else:
            block_hash = ServerComponents().get_last_block_hash()
            response = ServerComponents().get_block_by_hash(block_hash)
            block_data = json.loads('{}')
            block_data['response_code'] = response.response_code
            block_data['block_hash'] = response.block_hash
            block_data['block_data_json'] = json.loads(response.block_data_json)

        return block_data


class RestServer(CommonThread):
    def __init__(self, peer_port):
        CommonThread.__init__(self)
        self.__peer_port = peer_port
        ServerComponents().set_argument()
        ServerComponents().set_resource()

    def run(self):
        ServerComponents().set_stub_port(self.__peer_port)
        api_port = self.__peer_port + conf.PORT_DIFF_REST_SERVICE_CONTAINER
        logging.debug("RestServer run... %s", str(api_port))
        ServerComponents().app.run(port=api_port, host='0.0.0.0',
                                   debug=False, ssl_context=ServerComponents().ssl_context)
