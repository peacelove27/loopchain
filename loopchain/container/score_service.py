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
"""A class for Score service"""

import logging
import grpc
import json
import pickle

import loopchain.utils as util
from loopchain.baseservice import ObjectManager, PeerScore
from loopchain.blockchain import Transaction, ScoreInvokeError
from loopchain.container import Container
from loopchain.protos import loopchain_pb2, loopchain_pb2_grpc, message_code
from loopchain import configure as conf
from loopchain.scoreservice import ScoreResponse


class ScoreService(Container, loopchain_pb2_grpc.ContainerServicer):

    def __init__(self, port):
        Container.__init__(self, port)
        self.__handler_map = {
            message_code.Request.status: self.__handler_status,
            message_code.Request.stop: self.__handler_stop,
            message_code.Request.score_load: self.__handler_score_load,
            message_code.Request.score_invoke: self.__handler_score_invoke,
            message_code.Request.score_query: self.__handler_score_query,
            message_code.Request.score_set: self.__handler_score_set,
            message_code.Request.score_connect: self.__handler_connect
        }
        self.__score = None
        self.__peer_id = None
        self.__stub_to_peer_service = None
        ObjectManager().score_service = self
        self.start()

    def get_last_block_hash(self):
        response = self.__stub_to_peer_service.GetLastBlockHash(
            loopchain_pb2.CommonRequest(request=""), conf.GRPC_TIMEOUT)
        return str(response.block_hash)

    def get_block_by_hash(self, block_hash="",
                          block_data_filter="prev_block_hash, height, block_hash",
                          tx_data_filter="tx_hash"):
        return self.get_block(block_hash, -1, block_data_filter, tx_data_filter)

    def get_block_by_height(self, block_height=-1,
                            block_data_filter="prev_block_hash, height, block_hash",
                            tx_data_filter="tx_hash"):
        return self.get_block("", block_height, block_data_filter, tx_data_filter)

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

    def get_peer_status(self):
        """
        Score 에서 peer의 정보를 요청 한다

        :return: peer의 정보
        """
        response = self.__stub_to_peer_service.GetStatus(
            loopchain_pb2.StatusRequest(request="ScoreService.get_peer_status"), conf.GRPC_TIMEOUT)
        logging.debug("GET PEER STATUS IN Score Service %s", response)
        return response

    def get_peer_id(self):
        return self.__peer_id

    def __handler_connect(self, request, context):
        """make stub to peer service
        
        :param request: message=target of peer_service
        :param context: 
        :return: 
        """
        logging.debug("__handler_connect %s", request.message)
        self.__stub_to_peer_service = loopchain_pb2_grpc.PeerServiceStub(grpc.insecure_channel(request.message))
        return_code = (message_code.Response.success, message_code.Response.fail)[self.__stub_to_peer_service is None]
        return loopchain_pb2.Message(code=return_code)

    def __handler_status(self, request, context):
        """Score Status
        스코어의 정보 확인
        + peer_service id
        + peer_service version
        + peer_service all_version
        + TODO last invoked block hash
        :param request:
        :param context:
        :return:
        """
        logging.debug("score_service handler_status")

        status = dict()
        if self.__score is not None:
            status['id'] = self.__score.id()
            status['version'] = self.__score.version()
            status['all_version'] = self.__score.all_version()
            # TODO 외부에서 보는 GetStatus, ScoreStatus 에 대한 Status 값은 별도 정의가 필요하다. 현재는 임시 사용.
            status['status'] = message_code.Response.success
        else:
            status['status'] = message_code.Response.fail
        status_json = json.dumps(status)
        logging.debug("ScoreService __handler_status %s : %s", request.message, status_json)

        return loopchain_pb2.Message(code=message_code.Response.success, meta=status_json)

    def __handler_stop(self, request, context):
        logging.debug("ScoreService handler stop...")
        self.stop()
        return loopchain_pb2.Message(code=message_code.Response.success)

    def __handler_score_load(self, request, context):
        logging.debug(f"ScoreService Score Load Request : {request}")
        try:
            params = json.loads(request.meta)
            self.__peer_id = params[message_code.MetaParams.ScoreLoad.peer_id]

            util.logger.spam(f"score_service:__handler_score_load try init PeerScore")
            self.__score = PeerScore(params[message_code.MetaParams.ScoreLoad.repository_path],
                                     params[message_code.MetaParams.ScoreLoad.score_package],
                                     params[message_code.MetaParams.ScoreLoad.base])
            util.logger.spam(f"score_service:__handler_score_load after init PeerScore")

            score_info = dict()
            score_info[message_code.MetaParams.ScoreInfo.score_id] = self.__score.id()
            score_info[message_code.MetaParams.ScoreInfo.score_version] = self.__score.version()
            meta = json.dumps(score_info)
            return loopchain_pb2.Message(code=message_code.Response.success, meta=meta)

        except Exception as e:
            logging.exception(f"score_service:__handler_score_load SCORE LOAD IS FAIL params({params}) error({e})")
            return loopchain_pb2.Message(code=message_code.Response.fail, message=str(e))

    def __handler_score_invoke(self, request, context):
        logging.debug("ScoreService handler invoke...")
        results = {}
        # dict key

        # TODO score invoke 관련 code, message 등을 별도의 파일로 정의하면 아래의 define 도 옮길것!
        code_key = 'code'
        error_message_key = 'message'

        if self.__score is None:
            logging.error("There is no score!!")
            return loopchain_pb2.Message(code=message_code.Response.fail)
        else:
            block = pickle.loads(request.object)
            logging.debug('tx_list_length : %d ', len(block.confirmed_transaction_list))
            for transaction in block.confirmed_transaction_list:
                if isinstance(transaction, Transaction) and transaction.get_tx_hash() is not None:
                    tx_hash = transaction.get_tx_hash()
                    results[tx_hash] = {}
                    # put score invoke result to results[tx_hash]
                    try:
                        invoke_result = self.__score.invoke(transaction, block)
                        if invoke_result is None:
                            results[tx_hash] = {'code': message_code.Response.success}
                            # logging.debug(f"handler_score_invoke: ({invoke_result})")
                        else:
                            if code_key not in invoke_result:
                                code_not_return = "Score not return code"
                                if error_message_key in invoke_result:
                                    raise ScoreInvokeError(code_not_return + ": " + invoke_result[error_message_key])
                                raise ScoreInvokeError(code_not_return)
                            elif error_message_key in invoke_result:
                                results[tx_hash][error_message_key] = invoke_result[error_message_key]
                            results[tx_hash][code_key] = invoke_result[code_key]

                    # if score raise exception result to fail and put error message
                    except Exception as e:
                        logging.exception("tx %s score invoke is fail!! : %s ", str(tx_hash), e)
                        results[tx_hash][code_key] = ScoreResponse.EXCEPTION
                        results[tx_hash][error_message_key] = str(e)
                        continue

            # logging.debug('results : %s', str(results))
            util.apm_event(self.__peer_id, {
                'event_type': 'InvokeResult',
                'peer_id': self.__peer_id,
                'data': {'invoke_result': invoke_result}})


            meta = json.dumps(results)
            return loopchain_pb2.Message(code=message_code.Response.success, meta=meta)

    def __handler_score_query(self, request, context):
        """ do query using request.meta and return json.dumps response
        :param request:
        :return: gRPC response
        """
        logging.debug("ScoreService handler query...")

        if self.__score is None:
            logging.error("There is no score!!")
            ret = ""
        else:
            try:
                ret = self.__score.query(request.meta)
            except Exception as e:
                logging.error(f'query {request.meta} raise exception {e}')
                exception_response = {'code': ScoreResponse.EXCEPTION, 'message': f'Query Raise Exception : {e}'}
                ret = json.dumps(exception_response)
                return loopchain_pb2.Message(code=message_code.Response.success, meta=ret)

        return loopchain_pb2.Message(code=message_code.Response.success, meta=ret)

    def __handler_score_set(self, request, context):
        self.__score = pickle.loads(request.object)
        return loopchain_pb2.Message(code=message_code.Response.success)

    def Request(self, request, context):
        if request.code in self.__handler_map.keys():
            return self.__handler_map[request.code](request, context)

        return loopchain_pb2.Message(code=message_code.Response.not_treat_message_code)
