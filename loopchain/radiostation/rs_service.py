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

import logging
import random
import time
import timeit

import loopchain.utils as util
from loopchain import configure as conf
from loopchain.baseservice import ObjectManager
from loopchain.container import RestServiceRS, CommonService
from loopchain.peer import ChannelManager
from loopchain.protos import loopchain_pb2_grpc
from loopchain.radiostation import OuterService, AdminService, AdminManager
from .certificate_authorization import CertificateAuthorization

# loopchain_pb2 를 아래와 같이 import 하지 않으면 broadcast 시도시 pickle 오류가 발생함
import loopchain_pb2


class RadioStationService:
    """Radiostation 의 main Class
    peer 를 위한 outer service 와 관리용 admin service 두개의 gRPC interface 를 가진다.
    """

    # 인증처리
    __ca = None

    def __init__(self, radio_station_ip=None, cert_path=None, cert_pass=None, rand_seed=None):
        """RadioStation Init

        :param radio_station_ip: radioStation Ip
        :param cert_path: RadioStation 인증서 디렉토리 경로
        :param cert_pass: RadioStation private key password
        """
        if radio_station_ip is None:
            radio_station_ip = conf.IP_RADIOSTATION
        logging.info("Set RadioStationService IP: " + radio_station_ip)
        if cert_path is not None:
            logging.info("CA Certificate Path : " + cert_path)

        self.__common_service = CommonService(loopchain_pb2)
        self.__admin_manager = AdminManager("station")
        self.__channel_manager = None
        self.__rest_service = None

        # RS has two status (active, standby) active means enable outer service
        # standby means stop outer service and heartbeat to the other RS (active)
        self.__is_active = False

        # 인증 클래스
        self.__ca = CertificateAuthorization()

        if cert_path is not None:
            # 인증서 로드
            self.__ca.load_pki(cert_path, cert_pass)

        if conf.ENABLE_KMS:
            if rand_seed is None:
                util.exit_and_msg("KMS needs input random seed \n"
                                  "you can put seed -s --seed")
            self.__random_table = self.__create_random_table(rand_seed)

        logging.info("Current RadioStation SECURITY_MODE : " + str(self.__ca.is_secure))

        # gRPC service for Radiostation
        self.__outer_service = OuterService()
        self.__admin_service = AdminService()

        # {group_id:[ {peer_id:IP} ] }로 구성된 dictionary
        self.peer_groups = {conf.ALL_GROUP_ID: []}

        # Peer의 보안을 담당
        self.auth = {}

        ObjectManager().rs_service = self

    def __del__(self):
        pass

    def launch_block_generator(self):
        pass

    def validate_group_id(self, group_id: str):
        # TODO group id 를 검사하는 새로운 방법이 필요하다, 현재는 임시로 모두 통과 시킨다.
        return 0, "It's available group ID:"+group_id

    @property
    def admin_manager(self):
        return self.__admin_manager

    @property
    def channel_manager(self):
        return self.__channel_manager

    @property
    def common_service(self):
        return self.__common_service

    @property
    def random_table(self):
        return self.__random_table

    def __broadcast_new_peer(self, peer_request):
        """새로 들어온 peer 를 기존의 peer 들에게 announce 한다."""

        logging.debug("Broadcast New Peer.... " + str(peer_request))
        if self.__common_service is not None:
            self.__common_service.broadcast("AnnounceNewPeer", peer_request)

    def check_peer_status(self):
        """service loop for status heartbeat check to peer list

        :return:
        """
        time.sleep(conf.SLEEP_SECONDS_IN_RADIOSTATION_HEARTBEAT)
        util.logger.spam(f"rs_service:check_peer_status(Heartbeat.!.!) for reset Leader and delete no response Peer")

        for channel in self.__channel_manager.get_channel_list():
            delete_peer_list = self.__channel_manager.get_peer_manager(channel).check_peer_status()

            for delete_peer in delete_peer_list:
                logging.debug(f"delete peer {delete_peer.peer_id}")
                message = loopchain_pb2.PeerID(
                    peer_id=delete_peer.peer_id,
                    channel=channel,
                    group_id=delete_peer.group_id)
                self.__common_service.broadcast("AnnounceDeletePeer", message)

    def __create_random_table(self, rand_seed: int) -> list:
        """create random_table using random_seed
        table size define in conf.RANDOM_TABLE_SIZE

        :param rand_seed: random seed for create random table
        :return: random table
        """
        random.seed(rand_seed)
        random_table = []
        for i in range(conf.RANDOM_TABLE_SIZE):
            random_num: int = random.getrandbits(conf.RANDOM_SIZE)
            random_table.append(random_num)

        return random_table

    def serve(self, port=None):
        """Peer(BlockGenerator Peer) to RadioStation

        :param port: RadioStation Peer
        """
        if port is None:
            port = conf.PORT_RADIOSTATION
        stopwatch_start = timeit.default_timer()

        self.__channel_manager = ChannelManager(self.__common_service)

        if conf.ENABLE_REST_SERVICE:
            self.__rest_service = RestServiceRS(int(port))

        loopchain_pb2_grpc.add_RadioStationServicer_to_server(self.__outer_service, self.__common_service.outer_server)
        loopchain_pb2_grpc.add_AdminServiceServicer_to_server(self.__admin_service, self.__common_service.inner_server)

        logging.info("Start peer service at port: " + str(port))

        if conf.ENABLE_RADIOSTATION_HEARTBEAT:
            self.__common_service.add_loop(self.check_peer_status)
        self.__common_service.start(port)

        stopwatch_duration = timeit.default_timer() - stopwatch_start
        logging.info(f"Start Radio Station start duration({stopwatch_duration})")

        # service 종료를 기다린다.
        self.__common_service.wait()

        if self.__rest_service is not None:
            self.__rest_service.stop()
