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
import secrets
import time
import timeit

from loopchain import configure as conf
from loopchain.baseservice import PeerStatus
from loopchain.container import RestServiceRS, CommonService
from loopchain.protos import loopchain_pb2_grpc, message_code
from loopchain.radiostation import RadioStation
from .certificate_authorization import CertificateAuthorization

# loopchain_pb2 를 아래와 같이 import 하지 않으면 broadcast 시도시 pickle 오류가 발생함
import loopchain_pb2


class RadioStationService(loopchain_pb2_grpc.RadioStationServicer):
    """Radiostation의 gRPC service를 구동하는 Class.
    """
    # 인증처리
    __ca = None

    def __init__(self, radio_station_ip=conf.IP_RADIOSTATION, cert_path=None, cert_pass=None):
        """
        RadioStation Init

        :param radio_station_ip: radioStation Ip
        :param cert_path: RadioStation 인증서 디렉토리 경로
        :param cert_pass: RadioStation private key password
        """
        self.__handler_map = {
            message_code.Request.status: self.__handler_status,
            message_code.Request.peer_get_leader: self.__handler_get_leader_peer,
            message_code.Request.peer_complain_leader: self.__handler_complain_leader,
            message_code.Request.rs_set_configuration: self.__handler_set_configuration,
            message_code.Request.rs_get_configuration: self.__handler_get_configuration
        }
        logging.info("Set RadioStationService IP: " + radio_station_ip)
        if cert_path is not None:
            logging.info("CA Certificate Path : " + cert_path)

        self._rs = RadioStation()
        self.__common_service = CommonService(loopchain_pb2)
        self.__common_service.set_peer_type(loopchain_pb2.RADIO_STATION)
        self.__peer_manager = self.__common_service.load_peer_manager()

        self.__rest_service = None

        # 인증 클래스
        self.__ca = CertificateAuthorization()

        if cert_path is not None:
            # 인증서 로드
            self.__ca.load_pki(cert_path, cert_pass)

        logging.info("Current group ID:"+self._rs.get_group_id())
        logging.info("Current RadioStation SECURITY_MODE : " + str(self.__ca.is_secure))

    def __handler_status(self, request, context):
        return loopchain_pb2.Message(code=message_code.Response.success)

    def __handler_get_leader_peer(self, request, context):
        """Get Leader Peer

        :param request: proto.Message {message=group_id}
        :param context:
        :return: proto.Message {object=leader_peer_object}
        """

        # TODO 현재는 peer_list.get_leader_peer 가 서브 그룹 리더에 대한 처리를 제공하지 않고 있다.
        leader_peer = self.__peer_manager.get_leader_peer(group_id=request.message, is_peer=False)
        if leader_peer is not None:
            logging.debug(f"leader_peer ({leader_peer.peer_id})")
            peer_dump = pickle.dumps(leader_peer)

            return loopchain_pb2.Message(code=message_code.Response.success, object=peer_dump)

        return loopchain_pb2.Message(code=message_code.Response.fail_no_leader_peer)

    def __handler_complain_leader(self, request, context):
        """Complain Leader Peer

        :param request: proto.Message {message=group_id}
        :param context:
        :return: proto.Message {object=leader_peer_object}
        """

        # 현재 leader peer status 확인 후 맞으면 peer id 를
        # 아니면 complain 한 peer 로 leader 를 변경 후 응답한다.

        # 선택된 peer 가 leader 로 동작하고 있는지 확인 후 지정하는데 만약
        # get_leader_peer 한 내용과 다르면 AnnounceNewLeader 를 broadcast 하여야 한다.

        logging.debug("in complain leader (radiostation)")
        leader_peer = self.__peer_manager.complain_leader(group_id=request.message)
        if leader_peer is not None:
            logging.warning(f"leader_peer after complain({leader_peer.peer_id})")
            peer_dump = pickle.dumps(leader_peer)
            return loopchain_pb2.Message(code=message_code.Response.success, object=peer_dump)

        return loopchain_pb2.Message(code=message_code.Response.fail_no_leader_peer)

    def __handler_get_configuration(self, request, context):
        """Get Configuration

        :param request: proto.Message {meta=configuration_name}
        :param context:
        :return: proto.Message {meta=configuration_info(s)}
        """

        if request.meta == '':
            result = conf.get_all_configurations()
        else:
            meta = json.loads(request.meta)
            conf_name = meta['name']
            result = conf.get_configuration(conf_name)

        if result is None:
            return loopchain_pb2.Message(
                code=message_code.Response.fail,
                message="'" + conf_name + "' is an incorrect configuration name."
            )
        else:
            json_result = json.dumps(result)
            return loopchain_pb2.Message(
                code=message_code.Response.success,
                meta=json_result
            )

    def __handler_set_configuration(self, request, context):
        """Set Configuration

        :param request: proto.Message {meta=configuration_info}
        :param context:
        :return: proto.Message
        """

        meta = json.loads(request.meta)

        if conf.set_configuration(meta['name'], meta['value']):
            return loopchain_pb2.Message(code=message_code.Response.success)
        else:
            return loopchain_pb2.Message(
                code=message_code.Response.fail,
                message='"' + meta['name'] + '" does not exist in the loopchain configuration list.'
            )

    def Request(self, request, context):
        logging.debug("RadioStationService got request: " + str(request))

        if request.code in self.__handler_map.keys():
            return self.__handler_map[request.code](request, context)

        return loopchain_pb2.Message(code=message_code.Response.not_treat_message_code)

    def GetStatus(self, request, context):
        """RadioStation의 현재 상태를 요청한다.

        :param request:
        :param context:
        :return:
        """

        logging.debug("RadioStation GetStatus : %s", request)
        peer_status = self.__common_service.getstatus(None)

        return loopchain_pb2.StatusReply(
            status=json.dumps(peer_status),
            block_height=peer_status["block_height"],
            total_tx=peer_status["total_tx"])

    def Stop(self, request, context):
        """RadioStation을 종료한다.

        :param request: StopRequest
        :param context:
        :return: StopReply
        """
        logging.info('RadioStation will stop... by: ' + request.reason)
        self.__common_service.stop()
        return loopchain_pb2.StopReply(status="0")

    def ConnectPeer(self, request, context):
        """RadioStation 에 접속한다. 응답으로 기존의 접속된 Peer 목록을 받는다.

        :param request: PeerRequest
        :param context:
        :return: PeerReply
        """
        logging.info("Trying to connect peer: "+request.peer_id)

        res, info = self._rs.validate_group_id(request.group_id)
        if res < 0:  # 잘못된 입력이 들어오면 빈 list를 보내준다.
            return loopchain_pb2.PeerReply(status=message_code.Response.fail, peer_list=b'', more_info=info)

        logging.debug("Connect Peer "
                      + "\nPeer_id : " + request.peer_id
                      + "\nGroup_id : " + request.group_id
                      + "\nPeer_target : " + request.peer_target)

        auth = ""
        token = ""
        logging.info("CA SECURITY_MODE : " + str(self.__ca.is_secure))
        if self.__ca.is_secure:
            logging.debug("RadioStation is secure mode")
            if request.token is None or request.token is "":
                info = "Peer Token is None"
                return loopchain_pb2.PeerReply(status=message_code.Response.fail, peer_list=b'', more_info=info)

            else:
                # TOKEN : "00", CERT : "01", SIGN : "02"
                tag = request.token[:2]
                data = request.token[2:]
                logging.debug("TOKEN TYPE : %s", tag)

                if tag == conf.TOKEN_TYPE_TOKEN:
                    peer = self.__peer_manager.get_peer(request.peer_id, request.group_id)
                    if peer is None:
                        info = "Invalid Peer_ID[" + request.peer_id + "], Group_ID[" + request.group_id + "%s]"
                        return loopchain_pb2.PeerReply(status=message_code.Response.fail, peer_list=b'', more_info=info)
                    else:
                        peer_type = request.peer_type
                        if peer_type is loopchain_pb2.BLOCK_GENERATOR:
                            peer_type = loopchain_pb2.PEER

                        if self.__ca.verify_peer_token(peer_token=data, peer=peer, peer_type=peer_type):
                            auth = peer.auth
                            token = request.token
                        else:
                            info = "Invalid TOKEN"
                            return loopchain_pb2.PeerReply(status=message_code.Response.fail, peer_list=b'', more_info=info)

                elif tag == conf.TOKEN_TYPE_CERT:
                    # TODO: 인증서와 Peer_ID가 연결될 수 있는 장치가 필요(인증서 내부 정보 활용)
                    if self.__ca.verify_certificate_der(bytes.fromhex(data)):
                        rand_key = secrets.token_bytes(16).hex()
                        self._rs.auth[request.peer_id] = {'rand_key': rand_key, 'auth': data}
                        return loopchain_pb2.PeerReply(status=message_code.Response.success, peer_list=b'', more_info=rand_key)
                    else:
                        info = "Invalid Peer Certificate"
                        return loopchain_pb2.PeerReply(status=message_code.Response.fail, peer_list=b'', more_info=info)

                elif tag == conf.TOKEN_TYPE_SIGN:
                    try:
                        peer_auth = self._rs.auth[request.peer_id]
                        rand_key = peer_auth['rand_key']
                        auth = peer_auth['auth']
                    except KeyError:
                        info = "No Peer Info"
                        return loopchain_pb2.PeerReply(status=message_code.Response.fail, peer_list=b'', more_info=info)
                    logging.debug("Get Rand_key: %s, auth: %s", rand_key, auth)

                    new_token = self.__ca.generate_peer_token(peer_sign=bytes.fromhex(data),
                                                              peer_cert=bytes.fromhex(auth),
                                                              peer_id=request.peer_id,
                                                              peer_target=request.peer_target,
                                                              group_id=request.group_id,
                                                              peer_type=request.peer_type,
                                                              rand_key=bytes.fromhex(rand_key),
                                                              token_interval=conf.TOKEN_INTERVAL)

                    if new_token is not None:
                        self._rs.auth[request.peer_id] = {}

                    token = conf.TOKEN_TYPE_TOKEN + new_token

                else:
                    info = "Unknown token type(" + tag + ")"
                    return loopchain_pb2.PeerReply(status=message_code.Response.fail, peer_list=b'', more_info=info)

        peer = self.__peer_manager.make_peer(request.peer_id,
                                             request.group_id,
                                             request.peer_target,
                                             PeerStatus.connected,
                                             peer_auth=auth,
                                             peer_token=token)

        peer_order = self.__peer_manager.add_peer_object(peer)
        self.__common_service.save_peer_list(self.__peer_manager)

        if peer_order > 0:
            # 접속 완료
            try:
                peer_dump = pickle.dumps(peer)
            except pickle.PicklingError as e:
                logging.warning("Fail Peer Dump: " + str(e))
                peer_dump = b''

            request.peer_object = peer_dump
            request.peer_order = peer_order
            logging.debug("Connect Peer: " + str(request))

            # self.__broadcast_new_peer(request)
            # TODO RS subsribe 를 이용하는 경우, RS 가 재시작시 peer broadcast 가 전체로 되지 않는 문제가 있다.
            # peer_list 를 이용하여 broadcast 하는 구조가되면 RS 혹은 Leader 에 대한 Subscribe 구조는 유효하지 않다.
            # 하지만 broadcast process 는 peer_list broadcast 인 경우 사용되어지지 않는다. peer_list 에서 broadcast 하는 동안
            # block 되는 구조. broadcast Process 를 peer_list 를 이용한 broadcast 에서도 활용할 수 있게 하거나.
            # RS 혹은 Leader 가 재시작 후에 Subscribe 정보를 복원하게 하거나.
            # 혹은 peer_list 가 broadcast 하여도 성능상(동시성에 있어) 문제가 없는지 보증하여야 한다. TODO TODO TODO
            self.__peer_manager.announce_new_peer(request)

            logging.debug("get_IP_of_peers_in_group: " + str(self.__peer_manager.get_IP_of_peers_in_group()))

            try:
                peer_list_dump = self.__peer_manager.dump()
                status, reason = message_code.get_response(message_code.Response.success)
                # TODO 현재는 reason 을 token return 으로 사용하고 있음, 이 용도로 reason 을 사용할 때에는 token 만 담겨있어야 함
                # 추후 메시지를 확장할 때 리팩토링 할 것
                reason = token
            except pickle.PicklingError as e:
                logging.warning("fail peer_list dump")
                peer_list_dump = b''
                status, reason = message_code.get_response(message_code.Response.fail)
                reason += " " + str(e)

            return loopchain_pb2.PeerReply(
                status=status,
                peer_list=peer_list_dump,
                more_info=reason
            )

    def GetPeerList(self, request, context):
        """현재 RadioStation 에 접속된 Peer 목록을 구한다.

        :param request: CommonRequest
        :param context:
        :return: PeerList
        """
        try:
            peer_list_dump = self.__peer_manager.dump()
        except pickle.PicklingError as e:
            logging.warning("fail peer_list dump")
            peer_list_dump = b''

        return loopchain_pb2.PeerList(
            peer_list=peer_list_dump
        )

    def GetPeerStatus(self, request, context):
        # request parsing
        logging.debug(f"rs service GetPeerStatus peer_id({request.peer_id}) group_id({request.group_id})")

        # get stub of target peer
        peer_stub_manager = self.__peer_manager.get_peer_stub_manager(self.__peer_manager.get_peer(request.peer_id))
        if peer_stub_manager is not None:
            try:
                response = peer_stub_manager.call_in_times(
                    "GetStatus",
                    loopchain_pb2.StatusRequest(request="get peer status from rs"))
                if response is not None:
                    return response
            except Exception as e:
                logging.warning(f"fail GetStatus... ({e})")

        return loopchain_pb2.StatusReply(status="", block_height=0, total_tx=0)

    def AnnounceNewLeader(self, request, context):
        new_leader_peer = self.__peer_manager.get_peer(request.new_leader_id, None)
        logging.debug(f"AnnounceNewLeader({request.new_leader_id})({new_leader_peer.target}): " + request.message)

        self.__peer_manager.set_leader_peer(new_leader_peer, None)

        return loopchain_pb2.CommonReply(response_code=message_code.Response.success, message="success")

    def Subscribe(self, request, context):
        """RadioStation 이 broadcast 하는 채널에 Peer 를 등록한다.

        :param request: SubscribeRequest
        :param context:
        :return: CommonReply
        """
        logging.debug("Radio Station Subscription peer_id: " + str(request))
        self.__common_service.add_audience(request)
        return loopchain_pb2.CommonReply(response_code=message_code.get_response_code(message_code.Response.success),
                                         message=message_code.get_response_msg(message_code.Response.success))

    def UnSubscribe(self, request, context):
        """RadioStation 의 broadcast 채널에서 Peer 를 제외한다.

        :param request: SubscribeRequest
        :param context:
        :return: CommonReply
        """
        logging.debug("Radio Station UnSubscription peer_id: " + request.peer_target)
        self.__peer_manager.remove_peer(request.peer_id, request.group_id)
        self.__common_service.remove_audience(request.peer_id, request.peer_target)
        return loopchain_pb2.CommonReply(response_code=0, message="success")

    def __broadcast_new_peer(self, peer_request):
        """새로 들어온 peer 를 기존의 peer 들에게 announce 한다.
        """
        logging.debug("Broadcast New Peer.... " + str(peer_request))
        if self.__common_service is not None:
            self.__common_service.broadcast("AnnounceNewPeer", peer_request)

    def check_peer_status(self):
        """service loop for status heartbeat check to peer list

        :return:
        """
        delete_peer_list = self.__peer_manager.check_peer_status()

        for delete_peer in delete_peer_list:
            logging.debug(f"delete peer {delete_peer.peer_id}")
            message = loopchain_pb2.PeerID(peer_id=delete_peer.peer_id, group_id=delete_peer.group_id)
            self.__common_service.broadcast("AnnounceDeletePeer", message)

        time.sleep(conf.SLEEP_SECONDS_IN_RADIOSTATION_HEARTBEAT)

    def serve(self, port=conf.PORT_RADIOSTATION):
        """Peer(BlockGenerator Peer) to RadioStation

        :param port: RadioStation Peer
        """
        stopwatch_start = timeit.default_timer()

        if conf.ENABLE_REST_SERVICE:
            self.__rest_service = RestServiceRS(int(port))

        loopchain_pb2_grpc.add_RadioStationServicer_to_server(self, self.__common_service.outer_server)
        logging.info("Start peer service at port: " + str(port))

        self.__common_service.add_loop(self.check_peer_status)
        self.__common_service.start(port)

        stopwatch_duration = timeit.default_timer() - stopwatch_start
        logging.info(f"Start Radio Station start duration({stopwatch_duration})")

        # service 종료를 기다린다.
        self.__common_service.wait()

        if self.__rest_service is not None:
            self.__rest_service.stop()
