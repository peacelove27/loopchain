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
"""loopchain main peer service.
It has secure outer service for p2p consensus and status monitoring.
And also has insecure inner service for inner process modules."""

import subprocess
import timeit
import uuid

from loopchain.baseservice import BroadcastProcess, StubManager, TimerService
from loopchain.blockchain import *
from loopchain.container import RestService, CommonService
from loopchain.peer import SendToProcess, InnerService, OuterService, ChannelManager
from loopchain.peer.peer_authorization import PeerAuthorization
from loopchain.protos import loopchain_pb2, loopchain_pb2_grpc, message_code


class PeerService:
    """Peer Service 의 main Class
    outer 와 inner gRPC 인터페이스를 가진다.
    서비스 루프 및 공통 요소는 commonservice 를 통해서 처리한다.
    channel 관련 instance 는 channel manager 를 통해서 관리한다.
    """

    def __init__(self,
                 group_id=None,
                 radio_station_ip=None,
                 radio_station_port=None,
                 public_path=None,
                 private_path=None,
                 cert_pass=None):
        """Peer는 Radio Station 에 접속하여 leader 및 다른 Peer에 대한 접속 정보를 전달 받는다.

        :param group_id: Peer Group 을 구분하기 위한 ID, None 이면 Single Peer Group 이 된다. (peer_id is group_id)
        conf.PEER_GROUP_ID 를 사용하면 configure 파일에 저장된 값을 group_id 로 사용하게 된다.
        :param radio_station_ip: RS IP
        :param radio_station_port: RS Port
        :param public_path: Peer 인증서 디렉토리 경로
        :param private_path: Cert Private key
        :param cert_pass: Peer private key password
        :return:
        """
        if radio_station_ip is None:
            radio_station_ip = conf.IP_RADIOSTATION
        if radio_station_port is None:
            radio_station_port = conf.PORT_RADIOSTATION
        if public_path is None:
            public_path = conf.PUBLIC_PATH
        if private_path is None:
            private_path = conf.PRIVATE_PATH
        if cert_pass is None:
            cert_pass = conf.DEFAULT_PW

        util.logger.spam(f"Your Peer Service runs on debugging MODE!")
        util.logger.spam(f"You can see many terrible garbage logs just for debugging, R U Really want it?")

        self.__send_to_process_thread = SendToProcess()

        self.__radio_station_target = radio_station_ip + ":" + str(radio_station_port)
        logging.info("Set Radio Station target is " + self.__radio_station_target)

        self.__stub_to_radio_station = None

        self.__level_db = None
        self.__level_db_path = ""

        self.__peer_id = None
        self.__group_id = group_id
        if self.__group_id is None and conf.PEER_GROUP_ID != "":
            self.__group_id = conf.PEER_GROUP_ID

        self.__common_service = None
        self.__channel_manager: ChannelManager = None

        self.__rest_service = None
        self.__timer_service = TimerService()

        # TODO peer 서비스의 .__score를 삭제, set chain code 테스트에서만 쓰인다. (검토후 제거할 것)
        self.__score = None
        self.__peer_target = None
        self.__inner_target = None
        self.__peer_port = 0

        # For Send tx to leader
        self.__tx_process = None

        if conf.ENABLE_KMS:
            rand_table = self.__get_random_table()
            self.__auth = PeerAuthorization(rand_table=rand_table)
        else:
            self.__auth = PeerAuthorization(public_path, private_path, cert_pass)

        # gRPC service for Peer
        self.__inner_service = InnerService()
        self.__outer_service = OuterService()

        self.__reset_voter_in_progress = False

    @property
    def common_service(self):
        return self.__common_service

    @property
    def timer_service(self):
        return self.__timer_service

    @property
    def channel_manager(self):
        return self.__channel_manager

    @property
    def send_to_process_thread(self):
        return self.__send_to_process_thread

    @property
    def tx_process(self):
        return self.__tx_process

    @property
    def peer_target(self):
        return self.__peer_target

    @property
    def auth(self):
        return self.__auth

    @property
    def stub_to_radiostation(self) -> StubManager:
        if self.__stub_to_radio_station is None:
            self.__stub_to_radio_station = StubManager.get_stub_manager_to_server(
                self.__radio_station_target,
                loopchain_pb2_grpc.RadioStationStub,
                conf.CONNECTION_RETRY_TIMEOUT_TO_RS)

        return self.__stub_to_radio_station

    @property
    def peer_id(self):
        return self.__peer_id

    @property
    def group_id(self):
        if self.__group_id is None:
            self.__group_id = self.__peer_id
        return self.__group_id

    @property
    def peer_target(self):
        return self.__peer_target

    def __get_random_table(self) -> list:
        """request get rand_table to rs

        :return: rand_table from rs
        """
        try:
            response = self.stub_to_radiostation.call_in_time("GetRandomTable", loopchain_pb2.CommonRequest(request=""))
            if response.response_code == message_code.Response.success:
                random_table = json.loads(response.message)
            else:
                util.exit_and_msg(f"get random table fail \n"
                                  f"cause by {response.message}")
            return random_table
        except Exception as e:
            util.exit_and_msg(f"get random table and init peer_auth fail \n"
                              f"cause by : {e}")

    def rotate_next_leader(self, channel_name):
        """Find Next Leader Id from peer_list and reset leader to that peer"""

        # logging.debug("rotate next leader...")
        util.logger.spam(f"peer_service:rotate_next_leader")
        peer_manager = self.__channel_manager.get_peer_manager(channel_name)
        next_leader = peer_manager.get_next_leader_peer(is_only_alive=True)

        # Check Next Leader is available...
        if next_leader is not None and next_leader.peer_id != self.peer_id:
            try:
                stub_manager = peer_manager.get_peer_stub_manager(next_leader)
                response = stub_manager.call(
                    "GetStatus",
                    loopchain_pb2.StatusRequest(request="get_leader_peer"),
                    is_stub_reuse=True
                )

                # Peer 가 leader 로 변경되는데 시간이 필요함으로 접속 여부만 확인한다.
                # peer_status = json.loads(response.status)
                # if peer_status["peer_type"] != str(loopchain_pb2.BLOCK_GENERATOR):
                #     logging.warning("next rotate is not a leader")
                #     raise Exception

            except Exception as e:
                logging.warning(f"rotate next leader exceptions({e})")
                next_leader = peer_manager.leader_complain_to_rs(conf.ALL_GROUP_ID)

        if next_leader is not None:
            self.reset_leader(next_leader.peer_id, channel_name)
        else:
            util.logger.warning(f"peer_service:rotate_next_leader next_leader is None({next_leader})")

    def reset_leader(self, new_leader_id, channel: str):
        logging.info(f"RESET LEADER channel({channel}) leader_id({new_leader_id})")

        block_manager = self.__channel_manager.get_block_manager(channel)
        peer_manager = self.__channel_manager.get_peer_manager(channel)
        complained_leader = peer_manager.get_leader_peer()
        leader_peer = peer_manager.get_peer(new_leader_id, None)

        if leader_peer is None:
            logging.warning(f"in peer_service:reset_leader There is no peer by peer_id({new_leader_id})")
            return

        util.logger.spam(f"peer_service:reset_leader target({leader_peer.target})")

        peer_manager.set_leader_peer(leader_peer, None)

        self_peer_object = peer_manager.get_peer(self.__peer_id)
        peer_leader = peer_manager.get_leader_peer()
        peer_type = loopchain_pb2.PEER

        if self_peer_object.target == peer_leader.target:
            util.change_log_color_set(True)
            logging.debug("Set Peer Type Leader!")
            peer_type = loopchain_pb2.BLOCK_GENERATOR
            block_manager.get_blockchain().reset_made_block_count()

            # TODO 아래 코드는 중복된 의미이다. 하지만, leader 가 변경되길 기다리는 코드로 의미를 명확히 할 경우
            # 블록체인 동작 지연으로 인한 오류가 발생한다. 우선 더 안정적인 테스트 결과를 보이는 상태로 유지한다.
            response = peer_manager.get_peer_stub_manager(self_peer_object).call(
                "Request",
                loopchain_pb2.Message(
                    code=message_code.Request.status,
                    channel=channel
                ),
                is_stub_reuse=True
            )

            peer_status = json.loads(response.meta)
            if peer_status['peer_type'] == str(loopchain_pb2.BLOCK_GENERATOR):
                is_broadcast = True
            else:
                is_broadcast = False

            peer_manager.announce_new_leader(complained_leader.peer_id, new_leader_id, is_broadcast=is_broadcast)
        else:
            util.change_log_color_set()
            logging.debug("Set Peer Type Peer!")
            # 새 leader 에게 subscribe 하기
            self.__common_service.subscribe(
                channel=channel,
                subscribe_stub=peer_manager.get_peer_stub_manager(peer_leader),
                peer_type=loopchain_pb2.BLOCK_GENERATOR
            )

        # update candidate blocks
        block_manager.get_candidate_blocks().set_last_block(block_manager.get_blockchain().last_block)
        block_manager.set_peer_type(peer_type)

        if self.__tx_process is not None:
            # peer_process 의 남은 job 을 처리한다. (peer->leader 인 경우),
            # peer_process 를 리더 정보를 변경한다. (peer->peer 인 경우)
            self.__tx_process_connect_to_leader(self.__tx_process, peer_leader.target)

    def show_peers(self, channel_name):
        logging.debug(f"peer_service:show_peers ({channel_name}): ")
        for peer in self.__channel_manager.get_peer_manager(channel_name).get_IP_of_peers_in_group():
            logging.debug("peer_target: " + peer)

    def service_stop(self):
        self.__channel_manager.stop_block_managers()
        self.__common_service.stop()

    def score_invoke(self, block, channel) -> dict:
        block_object = pickle.dumps(block)
        response = self.channel_manager.get_score_container_stub(channel).call(
            method_name="Request",
            message=loopchain_pb2.Message(code=message_code.Request.score_invoke, object=block_object),
            timeout=conf.SCORE_INVOKE_TIMEOUT,
            is_raise=True
        )
        # logging.debug("Score Server says: " + str(response))
        if response.code == message_code.Response.success:
            return json.loads(response.meta)

    def __connect_to_all_channel(self) -> bool:
        """connect to radiostation with all channel

        :return: is radiostation connected
        """
        response = self.__get_channel_infos()
        is_radiostation_connected = response is not None

        if is_radiostation_connected:
            logging.info(f"Connect to channels({response.channel_infos})")
            channels = json.loads(response.channel_infos)
            score_container_port_diff = 0

            for channel in list(channels.keys()):
                logging.debug(f"Try join channel({channel})")
                self.__channel_manager.load_block_manager(peer_id=self.peer_id, channel=channel)
                self.__channel_manager.load_peer_manager(channel=channel)

                is_score_container_loaded = self.__channel_manager.load_score_container_each(
                    channel_name=channel,
                    score_package=channels[channel]["score_package"],
                    container_port=self.__peer_port + conf.PORT_DIFF_SCORE_CONTAINER + score_container_port_diff,
                    peer_target=self.__peer_target)

                if is_score_container_loaded is False:
                    util.exit_and_msg(f"peer_service:__connect_to_all_channel score container load Fail ({channel})")

                score_container_port_diff = score_container_port_diff + conf.PORT_DIFF_BETWEEN_SCORE_CONTAINER
                response = self.connect_to_radiostation(channel=channel)
                if response is not None:
                    self.__channel_manager.save_peer_manager(
                        self.__channel_manager.get_peer_manager(channel),
                        channel
                    )

        return is_radiostation_connected

    def __get_channel_infos(self):
        response = self.stub_to_radiostation.call_in_times(
            method_name="GetChannelInfos",
            message=loopchain_pb2.GetChannelInfosRequest(
                peer_id=self.__peer_id,
                peer_target=self.__peer_target,
                group_id=self.group_id,
                cert=self.__auth.get_public_der()),
            retry_times=conf.CONNECTION_RETRY_TIMES_TO_RS,
            is_stub_reuse=True,
            timeout=conf.CONNECTION_TIMEOUT_TO_RS
        )

        return response

    def connect_to_radiostation(self, channel: str, is_reconnect: bool=False) -> loopchain_pb2.ConnectPeerReply:
        """connect to radiostation with channel

        :return: 접속정보, 실패시 None
        """
        logging.debug(f"try to connect to radiostation channel({channel})")

        if self.stub_to_radiostation is None:
            logging.warning("fail make stub to Radio Station!!")
            return None

        # 공통 부분
        response = self.stub_to_radiostation.call_in_times(
            method_name="ConnectPeer",
            message=loopchain_pb2.ConnectPeerRequest(
                channel=channel,
                peer_object=b'',
                peer_id=self.__peer_id,
                peer_target=self.__peer_target,
                group_id=self.group_id,
                cert=self.__auth.get_public_der()),
            retry_times=conf.CONNECTION_RETRY_TIMES_TO_RS,
            is_stub_reuse=True,
            timeout=conf.CONNECTION_TIMEOUT_TO_RS
        )

        if not is_reconnect:
            if response is not None and response.status == message_code.Response.success:
                peer_list_data = pickle.loads(response.peer_list)
                self.__channel_manager.get_peer_manager(channel).load(peer_list_data, False)
                logging.debug("peer list update: " +
                              self.__channel_manager.get_peer_manager(channel).get_peers_for_debug())
            else:
                logging.debug("using local peer list: " +
                              self.__channel_manager.get_peer_manager(channel).get_peers_for_debug())

        return response

    def add_unconfirm_block(self, block_unloaded, channel_name=None):
        if channel_name is None:
            channel_name = conf.LOOPCHAIN_DEFAULT_CHANNEL

        block = pickle.loads(block_unloaded)
        block_hash = block.block_hash

        response_code, response_msg = message_code.get_response(message_code.Response.fail_validate_block)

        # block 검증
        block_is_validated = False
        try:
            block_is_validated = Block.validate(block)
        except Exception as e:
            logging.error(e)

        if block_is_validated:
            # broadcast 를 받으면 받은 블럭을 검증한 후 검증되면 자신의 blockchain 의 unconfirmed block 으로 등록해 둔다.
            confirmed, reason = \
                self.__channel_manager.get_block_manager(channel_name).get_blockchain().add_unconfirm_block(block)

            if confirmed:
                response_code, response_msg = message_code.get_response(message_code.Response.success_validate_block)
            elif reason == "block_height":
                # Announce 되는 블럭과 자신의 height 가 다르면 Block Height Sync 를 다시 시도한다.
                self.__channel_manager.get_block_manager(channel_name).block_height_sync()

        return response_code, response_msg, block_hash

    def __tx_process_connect_to_leader(self, peer_process, leader_target):
        logging.debug("try... Peer Process connect_to_leader: " + leader_target)
        logging.debug("peer_process: " + str(peer_process))
        peer_process.send_to_process((BroadcastProcess.CONNECT_TO_LEADER_COMMAND, leader_target))
        peer_process.send_to_process((BroadcastProcess.SUBSCRIBE_COMMAND, leader_target))

    def __run_tx_process(self, inner_channel_info):
        tx_process = BroadcastProcess("Tx Process")
        tx_process.start()
        tx_process.send_to_process(("status", ""))

        wait_times = 0
        wait_for_process_start = None

        # TODO process wait loop 를 살리고 시간을 조정하였음, 이 상태에서 tx process 가 AWS infra 에서 시작되는지 확인 필요.
        # time.sleep(conf.WAIT_SECONDS_FOR_SUB_PROCESS_START)

        while wait_for_process_start is None:
            time.sleep(conf.SLEEP_SECONDS_FOR_SUB_PROCESS_START)
            logging.debug(f"wait start tx process....")
            wait_for_process_start = tx_process.get_receive("status")

            if wait_for_process_start is None and wait_times > conf.WAIT_SUB_PROCESS_RETRY_TIMES:
                util.exit_and_msg("Tx Process start Fail!")

        logging.debug(f"Tx Process start({wait_for_process_start})")
        tx_process.send_to_process((BroadcastProcess.MAKE_SELF_PEER_CONNECTION_COMMAND, inner_channel_info))

        return tx_process

    def __stop_tx_process(self):
        if self.__tx_process is not None:
            self.__tx_process.stop()
            self.__tx_process.wait()

    def reset_voter_count(self):
        """peer_list 의 활성화 상태(gRPC 응답)을 갱신하여 voter 수를 변경한다.

        :return:
        """
        # if self.__reset_voter_in_progress is not True:
        #     self.__reset_voter_in_progress = True
        #     logging.debug("reset voter count before: " +
        #                   str(ObjectManager().peer_service.peer_manager.get_peer_count()))
        #
        #     # TODO peer_list 를 순회하면서 gRPC 오류인 사용자를 remove_audience 한다.
        #     self.__channel_manager.get_peer_manager(
        #         conf.LOOPCHAIN_DEFAULT_CHANNEL).reset_peers(None, self.__common_service.remove_audience)
        #     logging.debug("reset voter count after: " +
        #                   str(ObjectManager().peer_service.peer_manager.get_peer_count()))
        #     self.__reset_voter_in_progress = False
        pass

    def set_chain_code(self, score):
        """Score를 패스로 전달하지 않고 (serve(...)의 score 는 score 의 파일 Path 이다.)
        Object 를 직접 할당하기 위한 인터페이스로 serve 호출전에 지정되어야 한다.

        :param score: score Object
        """
        # TODO 현재는 테스트를 위해서만 사용되고 있다. 검토후 제거 할 것
        self.__score = score

        # TODO 아래 세줄은 삭제 가능할 듯 검토 후 다음 merge 때 삭제 부탁합니다. assign to @godong
        self.__score_info = dict()
        self.__score_info[message_code.MetaParams.ScoreInfo.score_id] = self.__score.id()
        self.__score_info[message_code.MetaParams.ScoreInfo.score_version] = self.__score.version()

    def __port_init(self, port):
        # service 초기화 작업
        self.__peer_target = util.get_private_ip() + ":" + str(port)
        self.__inner_target = conf.IP_LOCAL + ":" + str(port)
        self.__peer_port = int(port)

        # SCORE Service check Using Port
        # check Port Using
        if util.check_port_using(conf.IP_PEER, int(port)+conf.PORT_DIFF_SCORE_CONTAINER):
            util.exit_and_msg('Score Service Port is Using '+str(int(port)+conf.PORT_DIFF_SCORE_CONTAINER))

    def __run_inner_services(self, port):
        if conf.ENABLE_REST_SERVICE:
            if conf.USE_GUNICORN_HA_SERVER:
                # Run web app on gunicorn in another process.
                new_rest_port = int(port)+conf.PORT_DIFF_REST_SERVICE_CONTAINER
                logging.debug(f'Launch gunicorn proxy server. Port = {new_rest_port}')
                subprocess.Popen(['python3', './rest_proxy.py', '-p', str(port), '&'])
            else:
                # Run web app as it is.  
                logging.debug(f'Launch Flask RESTful server. Port = {port}')
                self.__rest_service = RestService(int(port))

    def __make_peer_id(self):
        """네트워크에서 Peer 를 식별하기 위한 UUID를 level db 에 생성한다.
        """
        try:
            uuid_bytes = bytes(self.__level_db.Get(conf.LEVEL_DB_KEY_FOR_PEER_ID))
            peer_id = uuid.UUID(bytes=uuid_bytes)
        except KeyError:  # It's first Run
            peer_id = None

        if peer_id is None:
            peer_id = uuid.uuid1()
            logging.info("make new peer_id: " + str(peer_id))
            self.__level_db.Put(conf.LEVEL_DB_KEY_FOR_PEER_ID, peer_id.bytes)

        self.__peer_id = str(peer_id)

    def timer_test_callback_function(self, message):
        logging.debug(f'timer test callback function :: ({message})')

    def __block_height_sync_channel(self, channel_name):
        # leader 로 시작하지 않았는데 자신의 정보가 leader Peer 정보이면 block height sync 하여
        # 최종 블럭의 leader 를 찾는다.
        block_sync_target_stub = None
        peer_manager = self.__channel_manager.get_peer_manager(channel_name)
        peer_leader = peer_manager.get_leader_peer()
        self_peer_object = peer_manager.get_peer(self.__peer_id)
        is_delay_announce_new_leader = False
        peer_old_leader = None

        if peer_leader.target != self.__peer_target:
            block_sync_target_stub = StubManager.get_stub_manager_to_server(
                peer_leader.target,
                loopchain_pb2_grpc.PeerServiceStub,
                time_out_seconds=conf.CONNECTION_RETRY_TIMEOUT
            )

            if block_sync_target_stub is None:
                logging.warning("You maybe Older from this network... or No leader in this network!")

                # TODO 이 상황에서 rs 에 leader complain 을 진행한다
                is_delay_announce_new_leader = True
                peer_old_leader = peer_leader
                peer_leader = self.__channel_manager.get_peer_manager(
                    channel_name).leader_complain_to_rs(conf.ALL_GROUP_ID, is_announce_new_peer=False)

                if peer_leader is not None:
                    block_sync_target_stub = StubManager.get_stub_manager_to_server(
                        peer_leader.target,
                        loopchain_pb2_grpc.PeerServiceStub,
                        time_out_seconds=conf.CONNECTION_RETRY_TIMEOUT
                    )

            if peer_leader is None or peer_leader.peer_id == self.__peer_id:
                peer_leader = self_peer_object
                self.__channel_manager.get_block_manager(channel_name).set_peer_type(loopchain_pb2.BLOCK_GENERATOR)
            else:
                self.__channel_manager.get_block_manager(channel_name).block_height_sync(block_sync_target_stub)
                # # TODO 마지막 블럭으로 leader 정보를 판단하는 로직은 리더 컴플레인 알고리즘 수정 후 유효성을 다시 판단할 것
                # last_block_peer_id = self.__channel_manager.get_block_manager().get_blockchain().last_block.peer_id
                #
                # if last_block_peer_id != "" and last_block_peer_id != self.__peer_list.get_leader_peer().peer_id:
                #     logging.debug("make leader stub after block height sync...")
                #     new_leader_peer = self.__peer_list.get_peer(last_block_peer_id)
                #
                #     if new_leader_peer is None:
                #         new_leader_peer = self.__peer_list.leader_complain_to_rs(conf.ALL_GROUP_ID)
                #
                #     self.__peer_list.set_leader_peer(new_leader_peer, None)
                #     # TODO 리더가 상단의 next_leader_pear 와 같을 경우 stub 을 재설정하게 되는데 문제 없는지 확인 할 것
                #     peer_leader = new_leader_peer
                # else:

                if block_sync_target_stub is None:
                    util.exit_and_msg("Fail connect to leader!!")

                self.show_peers(channel_name)

            if block_sync_target_stub is not None:
                self.__common_service.subscribe(channel_name, block_sync_target_stub, loopchain_pb2.BLOCK_GENERATOR)

            if is_delay_announce_new_leader:
                self.__channel_manager.get_peer_manager(
                    channel_name).announce_new_leader(peer_old_leader.peer_id, peer_leader.peer_id)

    def __start_base_services(self, score):
        """start base services >> common_service, channel_manager, tx_process

        :param score:
        :return:
        """
        inner_service_port = conf.PORT_INNER_SERVICE or (self.__peer_port + conf.PORT_DIFF_INNER_SERVICE)

        self.__common_service = CommonService(loopchain_pb2, inner_service_port)

        self.__channel_manager = ChannelManager(
            common_service=self.__common_service,
            level_db_identity=self.__peer_target
        )

        self.__tx_process = self.__run_tx_process(
            inner_channel_info=conf.IP_LOCAL + ":" + str(inner_service_port)
        )

    def serve(self, port, score=None):
        """start func of Peer Service ===================================================================

        :param port:
        :param score:
        """
        if score is None:
            score = conf.DEFAULT_SCORE_PACKAGE

        stopwatch_start = timeit.default_timer()
        peer_type = loopchain_pb2.PEER

        is_all_service_safe_start = True

        self.__port_init(port)
        self.__level_db, self.__level_db_path = util.init_level_db(self.__peer_target)
        self.__make_peer_id()
        self.__run_inner_services(port)
        self.__start_base_services(score=score)

        is_radiostation_connected = self.__connect_to_all_channel()

        if is_radiostation_connected is False:
            util.exit_and_msg("There is no peer_list, initial network is not allowed without RS!")

        # start timer service.
        if conf.CONSENSUS_ALGORITHM == conf.ConsensusAlgorithm.lft:
            self.__timer_service.start()

        # TODO LOOPCHAIN-61 인증서 로드
        _cert = None
        # TODO LOOPCHAIN-61 인증서 키로드
        _private_key = None
        # TODO 인증정보 요청

        for channel in self.__channel_manager.get_channel_list():
            peer_leader = self.__channel_manager.get_peer_manager(channel).get_leader_peer(is_complain_to_rs=True)
            logging.debug(f"channel({channel}) peer_leader: " + str(peer_leader))

            # TODO 이 부분을 조건 검사가 아니라 leader complain 을 이용해서 리더가 되도록 하는 방법 검토하기
            # 자기가 peer_list 의 유일한 connected PEER 이거나 rs 의 leader 정보와 같을 때 block generator 가 된다.
            if self.__peer_id == peer_leader.peer_id:
                if is_radiostation_connected is True or self.__channel_manager.get_peer_manager(
                        channel).get_connected_peer_count(None) == 1:
                    util.change_log_color_set(True)
                    logging.debug(f"Set Peer Type Leader! channel({channel})")
                    peer_type = loopchain_pb2.BLOCK_GENERATOR

            # load score 는 score 서비스가 시작된 이후 block height sync 가 시작되기전에 이루어져야 한다.
            # is_all_service_safe_start &= self.__load_score(score)

            if peer_type == loopchain_pb2.BLOCK_GENERATOR:
                self.__channel_manager.get_block_manager(channel).set_peer_type(peer_type)
            elif peer_type == loopchain_pb2.PEER:
                self.__block_height_sync_channel(channel)

            if conf.CONSENSUS_ALGORITHM == conf.ConsensusAlgorithm.lft:
                self.__common_service.update_audience(self.channel_manager.get_peer_manager().dump())

        loopchain_pb2_grpc.add_PeerServiceServicer_to_server(self.__outer_service, self.__common_service.outer_server)
        loopchain_pb2_grpc.add_InnerServiceServicer_to_server(self.__inner_service, self.__common_service.inner_server)
        logging.info("Start peer service at port: " + str(port))

        self.__channel_manager.start_block_managers()
        self.__common_service.start(port, self.__peer_id, self.__group_id)

        if self.stub_to_radiostation is not None:
            for channel in self.__channel_manager.get_channel_list():
                self.__common_service.subscribe(
                    channel=channel,
                    subscribe_stub=self.stub_to_radiostation
                )

        for channel in self.__channel_manager.get_channel_list():
            channel_leader = self.__channel_manager.get_peer_manager(channel).get_leader_peer()
            if channel_leader is not None:
                util.logger.spam(f"connnect to channel({channel}) leader({channel_leader.target})")
                self.__tx_process_connect_to_leader(self.__tx_process, channel_leader.target)

        self.__send_to_process_thread.set_process(self.__tx_process)
        self.__send_to_process_thread.start()

        stopwatch_duration = timeit.default_timer() - stopwatch_start
        logging.info(f"Start Peer Service start duration({stopwatch_duration})")

        # service 종료를 기다린다.
        if is_all_service_safe_start:
            self.__common_service.wait()
        else:
            self.service_stop()

        self.__send_to_process_thread.stop()
        self.__send_to_process_thread.wait()

        if self.__timer_service.is_run():
            self.__timer_service.stop()
            self.__timer_service.wait()

        logging.info("Peer Service Ended.")
        self.__channel_manager.stop_score_containers()
        if self.__rest_service is not None:
            self.__rest_service.stop()
        self.__stop_tx_process()
