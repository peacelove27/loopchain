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
"""A module for restful API server of Radio station"""
import base64
import json
import logging
import pickle

from flask import Flask, request
from flask_restful import reqparse, Api, Resource
from flask_restful.utils import cors

from loopchain import configure as conf
from loopchain.baseservice import CommonThread, StubManager
from loopchain.baseservice import PeerManager, PeerStatus
from loopchain.components import SingletonMetaClass
from loopchain.baseservice.ca_service import CAService
from loopchain.protos import loopchain_pb2, loopchain_pb2_grpc, message_code


class ServerComponents(metaclass=SingletonMetaClass):
    def __init__(self):
        self.__app = Flask(__name__)
        self.__api = Api(self.__app)
        self.__api.decorators = [cors.crossdomain(origin='*', headers=['accept', 'Content-Type'])]
        self.__parser = reqparse.RequestParser()
        self.__stub_to_rs_service = None

        # SSL 적용 여부에 따라 context 생성 여부를 결정한다.
        if conf.ENABLE_REST_SSL is True:
            self.__ssl_context = (conf.DEFAULT_SSL_CERT_PATH, conf.DEFAULT_SSL_KEY_PATH)
        else:
            self.__ssl_context = None

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
        return self.__stub_to_rs_service

    @property
    def ssl_context(self):
        return self.__ssl_context

    def set_stub_port(self, port):
        self.__stub_to_rs_service = StubManager.get_stub_manager_to_server(
            conf.IP_LOCAL + ':' + str(port), loopchain_pb2_grpc.RadioStationStub
        )

    def set_argument(self):
        self.__parser.add_argument('peer_id')
        self.__parser.add_argument('group_id')
        self.__parser.add_argument('name')
        self.__parser.add_argument('channel')

    def set_resource(self):
        self.__api.add_resource(Peer, '/api/v1/peer/<string:request_type>')
        self.__api.add_resource(Configuration, '/api/v1/conf')
        self.__api.add_resource(Certificate, '/api/v1/cert/<string:request_type>/<string:certificate_type>')

    def get_peer_list(self, channel):
        return self.__stub_to_rs_service.call(
            "GetPeerList",
            loopchain_pb2.CommonRequest(request="", group_id=conf.ALL_GROUP_ID, channel=channel))

    def get_leader_peer(self, channel):
        return self.__stub_to_rs_service.call(
            "Request",
            loopchain_pb2.Message(code=message_code.Request.peer_get_leader, channel=channel))

    def get_peer_status(self, peer_id, group_id, channel):
        return self.__stub_to_rs_service.call_in_times(
            "GetPeerStatus",
            loopchain_pb2.PeerID(peer_id=peer_id, group_id=group_id, channel=channel))

    def get_configuration(self, conf_info):
        return self.__stub_to_rs_service.call(
            "Request",
            loopchain_pb2.Message(code=message_code.Request.rs_get_configuration, meta=conf_info))

    def set_configuration(self, conf_info):
        return self.__stub_to_rs_service.call(
            "Request",
            loopchain_pb2.Message(code=message_code.Request.rs_set_configuration, meta=conf_info))

    def response_simple_success(self):
        result = json.loads('{}')
        result['response_code'] = message_code.Response.success
        result['message'] = message_code.get_response_msg(message_code.Response.success)

        return result

    def abort_if_url_doesnt_exist(self, request_type, type_list):
        result = json.loads('{}')
        result['response_code'] = message_code.Response.fail

        if request_type not in type_list.values():
            result['message'] = "The resource doesn't exist"

        return result


def get_channel_name_from_args(args) -> str:
    """ get channel name from args, if channel is None return conf.LOOPCHAIN_DEFAULT_CHANNEL
    :param args: params
    :return: channel name if args channel is None return conf.LOOPCHAIN_DEFAULT_CHANNEL
    """

    return conf.LOOPCHAIN_DEFAULT_CHANNEL if args.get('channel') is None else args.get('channel')


class Peer(Resource):
    __REQUEST_TYPE = {
        'PEER_LIST': 'list',
        'LEADER_PEER': 'leader',
        'PEER_STATUS': 'status',
        'PEER_STATUS_LIST': 'status-list'
    }

    def get(self, request_type):
        args = ServerComponents().parser.parse_args()
        channel = get_channel_name_from_args(args)
        logging.debug(f'channel name : {channel}')
        if request_type == self.__REQUEST_TYPE['PEER_LIST']:
            response = ServerComponents().get_peer_list(channel)

            peer_manager = PeerManager()
            peer_list_data = pickle.loads(response.peer_list)
            peer_manager.load(peer_list_data, False)

            all_peer_list = []
            connected_peer_list = []

            leader_peer_id = ""
            leader_peer = peer_manager.get_leader_peer(conf.ALL_GROUP_ID, is_peer=False)  # for set peer_type info to peer
            if leader_peer is not None:
                leader_peer_id = leader_peer.peer_id
            
            for peer_id in peer_manager.peer_list[conf.ALL_GROUP_ID]:
                peer_each = peer_manager.peer_list[conf.ALL_GROUP_ID][peer_id]
                peer_data = self.__change_format_to_json(peer_each)

                if peer_each.peer_id == leader_peer_id:
                    peer_data['peer_type'] = loopchain_pb2.BLOCK_GENERATOR
                else:
                    peer_data['peer_type'] = loopchain_pb2.PEER

                all_peer_list.append(peer_data)

                if peer_each.status == PeerStatus.connected:
                    connected_peer_list.append(peer_data)

            json_data = json.loads('{}')
            json_data['registered_peer_count'] = peer_manager.get_peer_count()
            json_data['connected_peer_count'] = peer_manager.get_connected_peer_count()
            json_data['registered_peer_list'] = all_peer_list
            json_data['connected_peer_list'] = connected_peer_list

            result = json.loads('{}')
            result['response_code'] = message_code.Response.success
            result['data'] = json_data
            
        elif request_type == self.__REQUEST_TYPE['PEER_STATUS_LIST']:
            response = ServerComponents().get_peer_list(channel)

            peer_manager = PeerManager()
            peer_list_data = pickle.loads(response.peer_list)
            peer_manager.load(peer_list_data, False)

            all_peer_list = []

            for peer_id in peer_manager. peer_list[conf.ALL_GROUP_ID]:
                response = ServerComponents().get_peer_status(peer_id, conf.ALL_GROUP_ID, channel)
                if response is not None and response.status != "":
                    peer_each = peer_manager.peer_list[conf.ALL_GROUP_ID][peer_id]
                    status_json = json.loads(response.status)
                    status_json["order"] = peer_each.order
                    all_peer_list.append(status_json)

            json_data = json.loads('{}')
            json_data['registered_peer_count'] = peer_manager.get_peer_count()
            json_data['connected_peer_count'] = peer_manager.get_connected_peer_count()
            json_data['peer_status_list'] = all_peer_list

            result = json.loads('{}')
            result['response_code'] = message_code.Response.success
            result['data'] = json_data

        elif request_type == self.__REQUEST_TYPE['LEADER_PEER']:
            response = ServerComponents().get_leader_peer(channel)

            result = json.loads('{}')
            result['response_code'] = response.code

            if response.code == message_code.Response.success:
                result['data'] = self.__change_format_to_json(pickle.loads(response.object))
            else:
                result['message'] = message_code.get_response_msg(response.code)

        elif request_type == self.__REQUEST_TYPE['PEER_STATUS']:
            peer_id = args['peer_id']
            group_id = args['group_id']

            if peer_id is None or group_id is None:
                return self.__abort_if_arg_isnt_enough('peer_id, group_id')

            # logging.debug(f"try get_peer_status peer_id({peer_id}), group_id({group_id})")
            response = ServerComponents().get_peer_status(args['peer_id'], args['group_id'], channel)
            if response.status == message_code.get_response_msg(message_code.Response.fail):
                result = json.loads('{}')
                result['response_code'] = message_code.Response.fail
                result['message'] = response.status
            else:
                result = json.loads(response.status)

        else:
            return ServerComponents().abort_if_url_doesnt_exist(request_type, self.__REQUEST_TYPE)

        return result

    def __change_format_to_json(self, peer):
        json_data = json.loads('{}')
        json_data['order'] = peer.order
        json_data['peer_id'] = peer.peer_id
        json_data['group_id'] = peer.group_id
        json_data['target'] = peer.target
        json_data['cert'] = base64.b64encode(peer.cert).decode("utf-8")
        json_data['status_update_time'] = str(peer.status_update_time)
        json_data['status'] = peer.status

        return json_data

    def __abort_if_arg_isnt_enough(self, param_name):
        result = json.loads('{}')
        result['response_code'] = message_code.Response.fail_validate_params
        result['message'] = \
            message_code.get_response_msg(result['response_code']) \
            + ". You must throw all of parameters : " + param_name
        return result


class Configuration(Resource):
    def get(self):
        args = ServerComponents().parser.parse_args()

        if args['name'] is not None:
            json_data = json.loads('{}')
            json_data['name'] = args['name']
            request_data = json.dumps(json_data)

        else:
            request_data = ''

        response = ServerComponents().get_configuration(request_data)

        result = json.loads('{}')
        result['response_code'] = response.code

        if response.meta is not "":
            result['data'] = json.loads(response.meta)
        else:
            result['message'] = response.message

        return result

    def post(self):
        result = json.loads('{}')
        request_data = request.get_json()

        try:
            if request_data is None:
                result['response_code'] = message_code.Response.fail
                result['message'] = 'You must throw parameter of JSON when you call (/api/v1/conf) by post method.'

            else:
                response = ServerComponents().set_configuration(json.dumps(request_data))

                result = json.loads('{}')
                result['response_code'] = response.code
                result['message'] = message_code.get_response_msg(message_code.Response.success)

        except ValueError as e:
            result['response_code'] = message_code.Response.fail
            result['message'] = str(e)

        return result


class Certificate(Resource):
    __REQUEST_TYPE = {
        'CERT_LIST': 'list',
        'ISSUE': 'issue'
    }

    __CERTIFICATE_TYPE = {
        'CA': 'ca',
        'PEER': 'peer'
    }

    # TODO: 사용자로 부터 입력 받거나 Configuration으로 명시해서 발급 하는 것으로 구현
    _DEFAULT_PATH = "resources/testcerts/"
    _DEFAULT_COMMON_NAME = "Test CA"
    _DEFAULT_ORGANIZATION_UNIT = "DEV"
    _DEFAULT_ORGANIZATION = "THeLoop"
    _DEFAULT_COUNTRY = "kr"
    _DEFAULT_PERIOD = 5

    def get(self, request_type, certificate_type):
        ca = CAService(self._DEFAULT_PATH, None)
        result = json.loads('{}')

        if request_type == self.__REQUEST_TYPE['CERT_LIST']:
            if certificate_type == self.__CERTIFICATE_TYPE['CA']:
                certificate = ca.get_ca_certificate()
                result['response_code'] = message_code.Response.success
                result['data'] = ca.get_certificate_json(certificate)

            elif certificate_type == self.__CERTIFICATE_TYPE['PEER']:
                certificate = ca.get_peer_certificate_list()
                cert_json = []

                for cert_key in certificate:
                    cert_peer = ca.get_peer_certificate(cert_key)
                    cert_json.append(ca.get_certificate_json(cert_peer))

                result['response_code'] = message_code.Response.success
                result['data'] = cert_json

            else:
                return ServerComponents().abort_if_url_doesnt_exist(certificate_type, self.__CERTIFICATE_TYPE)

        elif request_type == self.__REQUEST_TYPE['ISSUE']:
            if certificate_type == self.__CERTIFICATE_TYPE['CA']:
                ca.generate_ca_cert(
                    cn=self._DEFAULT_COMMON_NAME,
                    ou=self._DEFAULT_ORGANIZATION_UNIT,
                    o=self._DEFAULT_ORGANIZATION,
                    expire_period=self._DEFAULT_PERIOD,
                    password=None
                )

                return ServerComponents().response_simple_success()

            elif certificate_type == self.__CERTIFICATE_TYPE['PEER']:
                if ca.is_secure is False:
                    return self.__abort_if_CA_certificate_loading_fails()

                else:
                    ca.generate_peer_cert(self._DEFAULT_COMMON_NAME, None)
                    return ServerComponents().response_simple_success()

            else:
                return ServerComponents().abort_if_url_doesnt_exist(certificate_type, self.__CERTIFICATE_TYPE)

        else:
            return ServerComponents().abort_if_url_doesnt_exist(request_type, self.__REQUEST_TYPE)

        return result

    def __abort_if_CA_certificate_loading_fails(self):
        result = json.loads('{}')
        result['response_code'] = message_code.Response.fail
        result['message'] = 'Fail loading of CA certificate.'

        return result


class RestServerRS(CommonThread):
    def __init__(self, rs_port):
        CommonThread.__init__(self)
        self.__rs_port = rs_port
        ServerComponents().set_argument()
        ServerComponents().set_resource()

    def run(self):
        ServerComponents().set_stub_port(self.__rs_port)
        api_port = self.__rs_port + conf.PORT_DIFF_REST_SERVICE_CONTAINER
        logging.debug("RestServerRS run... %s", str(api_port))
        ServerComponents().app.run(port=api_port, host='0.0.0.0',
                                   debug=False, ssl_context=ServerComponents().ssl_context)
