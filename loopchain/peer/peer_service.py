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
"""loopchain main gRPC service. 
It has secure outer service for p2p consensus and status monitoring.
And also has insecure inner service for inner process modules."""

import queue
import timeit

import grpc

from loopchain.baseservice import CommonThread, TxProcess, StubManager
from loopchain.blockchain import *
from loopchain.container import ScoreService, RestService, TxService, CommonService
from loopchain.peer import BlockManager, InnerService, OuterService
from loopchain.peer.peer_authorization import PeerAuthorization
from loopchain.protos import loopchain_pb2, loopchain_pb2_grpc, message_code


class SendToProcess(CommonThread):
    def __init__(self, process):
        CommonThread.__init__(self)
        self.__job = queue.Queue()
        self.__process = process

    def send_to_process(self, params):
        """return이 불필요한 process send를 비동기로 처리하기 위하여 queue in thread 방법을 사용한다.

        :param PeerProcess 에 전달하는 command 와 param 의 쌍
        """
        self.__job.put(params)

    def run(self):
        while self.is_run():
            time.sleep(conf.SLEEP_SECONDS_IN_SERVICE_LOOP)
            while not self.__job.empty():
                # logging.debug("Send to Process by thread.... remain jobs: " + str(self.__job.qsize()))
                self.__process.send_to_process(self.__job.get())


class PeerService:
    """Peer Service 의 gRPC 인터페이스를 구현한다.
    서비스 루프 및 공통 요소는 commonservice 를 통해서 처리한다.
    """

    def __init__(self, group_id=None, radio_station_ip=conf.IP_RADIOSTATION,
                 radio_station_port=conf.PORT_RADIOSTATION,
                 cert_path=None, cert_pass=None):
        """Peer는 Radio Station 에 접속하여 leader 및 다른 Peer에 대한 접속 정보를 전달 받는다.

        :param group_id: Peer Group 을 구분하기 위한 ID, None 이면 Single Peer Group 이 된다. (peer_id is group_id)
        conf.PEER_GROUP_ID 를 사용하면 configure 파일에 저장된 값을 group_id 로 사용하게 된다.
        :param radio_station_ip: RS IP
        :param radio_station_port: RS Port
        :param cert_path: Peer 인증서 디렉토리 경로
        :param cert_pass: Peer private key password
        :return:
        """
        self.__handler_map = {
            message_code.Request.status: self.__handler_status,
            message_code.Request.peer_peer_list: self.__handler_peer_list
        }
        self.__peer_type = loopchain_pb2.PEER
        self.__send_to_process_thread = None

        self.__radio_station_target = radio_station_ip + ":" + str(radio_station_port)
        self.__stub_to_radio_station = None
        logging.info("Set Radio Station target is " + self.__radio_station_target)

        self.__peer_id = None
        self.__group_id = group_id
        if self.__group_id is None and conf.PEER_GROUP_ID != "":
            self.__group_id = conf.PEER_GROUP_ID

        self.__common_service = None
        self.__peer_manager = None
        self.__block_manager = None
        self.__score_service = None
        self.__rest_service = None
        self.__tx_service = None

        # Channel and  Stubs for Servers, It can be set after serve()
        self.__stub_to_blockgenerator = None
        self.__stub_to_score_service = None

        # TODO peer 서비스의 .__score를 삭제, set chain code 테스트에서만 쓰인다. (검토후 제거할 것)
        self.__score = None
        self.__score_info = None
        self.__peer_target = None
        self.__inner_target = None
        self.__peer_port = 0

        self.__block_height_sync_lock = False

        # For Send tx to leader
        self.__tx_process = None

        self.__auth = PeerAuthorization()

        # gRPC service for Peer
        self.__inner_service = InnerService()
        self.__outer_service = OuterService()

        # 인증서 저장
        if cert_path is not None:
            self.__auth.load_pki(cert_path, cert_pass)

        self.__reset_voter_in_progress = False

    @property
    def common_service(self):
        return self.__common_service

    @property
    def block_manager(self):
        return self.__block_manager

    # TODO peer_manager 로 이름을 변경하였으나 수정 범위가 광범위 하여 기존 이름 임시로 유지함
    # 점차적으로 적용하여 리팩토링 범위를 축소한 후 모두 처리한 다음 제거할 것
    @property
    def peer_list(self):
        return self.__peer_manager

    @property
    def peer_manager(self):
        return self.__peer_manager

    @property
    def stub_to_score_service(self):
        return self.__stub_to_score_service

    @property
    def score_info(self):
        return self.__score_info

    @property
    def send_to_process_thread(self):
        return self.__send_to_process_thread

    @property
    def peer_type(self):
        return self.__peer_type

    @property
    def auth(self):
        return self.__auth

    @property
    def stub_to_blockgenerator(self):
        return self.__stub_to_blockgenerator

    @property
    def stub_to_radiostation(self):
        return self.__stub_to_radio_station

    def __handler_status(self, request, context):
        return loopchain_pb2.Message(code=message_code.Response.success)

    def __handler_peer_list(self, request, context):
        message = "All Group Peers count: " + str(len(self.__peer_manager.peer_list[conf.ALL_GROUP_ID]))
        return loopchain_pb2.Message(
            code=message_code.Response.success,
            message=message,
            meta=str(self.__peer_manager.peer_list))

    def rotate_next_leader(self):
        """Find Next Leader Id from peer_list and reset leader to that peer

        :return:
        """

        # logging.debug("rotate next leader...")
        next_leader = self.__peer_manager.get_next_leader_peer(is_only_alive=True)

        # Check Next Leader is available...
        if next_leader is not None and next_leader.peer_id != self.peer_id:
            try:
                stub_manager = self.__peer_manager.get_peer_stub_manager(next_leader)
                response = stub_manager.call(
                    "GetStatus",
                    loopchain_pb2.StatusRequest(request="get_leader_peer"),
                    is_stub_reuse=False
                )

                # Peer 가 leader 로 변경되는데 시간이 필요함으로 접속 여부만 확인한다.
                # peer_status = json.loads(response.status)
                # if peer_status["peer_type"] != str(loopchain_pb2.BLOCK_GENERATOR):
                #     logging.warning("next rotate is not a leader")
                #     raise Exception

            except Exception as e:
                logging.warning(f"rotate next leader exceptions({e})")
                next_leader = self.__peer_manager.leader_complain_to_rs(conf.ALL_GROUP_ID)

        if next_leader is not None:
            self.reset_leader(next_leader.peer_id)

    def reset_leader(self, new_leader_id):
        logging.warning("RESET LEADER: " + str(new_leader_id))

        complained_leader = self.__peer_manager.get_leader_peer()

        leader_peer = self.__peer_manager.get_peer(new_leader_id, None)
        if leader_peer is None:
            logging.warning(f"in peer_service::reset_leader There is no peer by peer_id({new_leader_id})")
            return

        self.__peer_manager.set_leader_peer(leader_peer, None)

        peer_self = self.__peer_manager.get_peer(self.peer_id)
        peer_leader = self.__peer_manager.get_leader_peer()

        if peer_self.target == peer_leader.target:
            logging.debug("Set Peer Type Block Generator!")
            self.__peer_type = loopchain_pb2.BLOCK_GENERATOR
            self.__block_manager.get_blockchain().reset_made_block_count()

            # TODO 아래 코드는 중복된 의미이다. 하지만, leader 가 변경되길 기다리는 코드로 의미를 명확히 할 경우
            # 블록체인 동작 지연으로 인한 오류가 발생한다. 우선 더 안정적인 테스트 결과를 보이는 상태로 유지한다.
            response = self.peer_list.get_peer_stub_manager(peer_self).call(
                "GetStatus",
                loopchain_pb2.StatusRequest(request="reset_leader"),
                is_stub_reuse=True
            )

            status_json = json.loads(response.status)
            if status_json['peer_type'] == str(loopchain_pb2.BLOCK_GENERATOR):
                is_broadcast = True
            else:
                is_broadcast = False

            self.__peer_manager.announce_new_leader(complained_leader.peer_id, new_leader_id, is_broadcast=is_broadcast)
        else:
            logging.debug("Set Peer Type Peer!")
            self.__peer_type = loopchain_pb2.PEER
            self.__stub_to_blockgenerator = self.__peer_manager.get_peer_stub_manager(peer_leader)
            # 새 leader 에게 subscribe 하기
            self.__common_service.subscribe(self.__stub_to_blockgenerator, loopchain_pb2.BLOCK_GENERATOR)

        self.__common_service.set_peer_type(self.__peer_type)
        # update candidate blocks
        self.__block_manager.get_candidate_blocks().set_last_block(self.__block_manager.get_blockchain().last_block)
        self.__block_manager.set_peer_type(self.__peer_type)

        if self.__tx_process is not None:
            # peer_process 의 남은 job 을 처리한다. (peer->leader 인 경우),
            # peer_process 를 리더 정보를 변경한다. (peer->peer 인 경우)
            self.__tx_process_connect_to_leader(self.__tx_process, peer_leader.target)

    def show_peers(self):
        logging.debug("Peers: ")
        for peer in self.__peer_manager.get_IP_of_peers_in_group():
            logging.debug("peer_target: " + peer)

    def __load_score(self, score):
        """스코어를 로드한다.

        :param score: score package name
        """
        if self.__score_info is None:
            logging.info("LOAD SCORE AND CONNECT TO SCORE SERVICE!")
            params = dict()
            params[message_code.MetaParams.ScoreLoad.repository_path] = conf.DEFAULT_SCORE_REPOSITORY_PATH
            params[message_code.MetaParams.ScoreLoad.score_package] = score
            params[message_code.MetaParams.ScoreLoad.base] = conf.DEFAULT_SCORE_BASE
            params[message_code.MetaParams.ScoreLoad.peer_id] = self.__peer_id
            meta = json.dumps(params)

            if self.__stub_to_score_service is None:
                logging.error(f"there is no __stub_to_scoreservice!")
                return False

            # Score Load is so slow ( load time out is more than GRPC_CONNECTION_TIMEOUT)
            response = self.__stub_to_score_service.call(
                "Request",
                loopchain_pb2.Message(code=message_code.Request.score_load, meta=meta),
                conf.SCORE_LOAD_TIMEOUT
            )
            logging.debug("try score load on score service: " + str(response))

            response_connect = self.__stub_to_score_service.call(
                "Request",
                loopchain_pb2.Message(code=message_code.Request.score_connect, message=self.__peer_target),
                conf.GRPC_CONNECTION_TIMEOUT
            )
            logging.debug("try connect to score service: " + str(response_connect))

            if response.code == message_code.Response.success:
                logging.debug("Get Score from Score Server...")
                self.__score_info = json.loads(response.meta)
            else:
                logging.error("Fail Get Score from Score Server...")
                return False
            logging.info("LOAD SCORE DONE!")
        else:
            logging.info("PEER SERVICE HAS SCORE BUT LOAD SCORE FUNCTION CALL!")
            score_dump = pickle.dumps(self.__score)
            response = self.__stub_to_score_service.call(
                "Request",
                loopchain_pb2.Message(code=message_code.Request.score_set, object=score_dump)
            )
            if response.code != message_code.Response.success:
                logging.error("Fail Set Score!!")
            logging.info("LOAD SCORE DONE!")

        return True

    def service_stop(self):
        self.__block_manager.stop()
        self.__common_service.stop()

    def score_invoke(self, block):
        block_object = pickle.dumps(block)
        try:
            response = self.__stub_to_score_service.call(
                "Request",
                loopchain_pb2.Message(code=message_code.Request.score_invoke, object=block_object)
            )
            # logging.debug("Score Server says: " + str(response))
            if response.code == message_code.Response.success:
                return json.loads(response.meta)
            else:
                raise ScoreInvokeError('score process grpc fail')
        except Exception as e:
            logging.warning("fail score invoke: " + str(e))
            return False

    def __load_block_manager(self):
        try:
            block_manager = BlockManager(self.__common_service)
            return block_manager
        except leveldb.LevelDBError as e:
            util.exit_and_msg("LevelDBError(" + str(e) + ")")

    def __connect_to_radiostation(self):
        """RadioStation 접속

        :return: 접속정보, 실패시 None
        """
        logging.debug("try to connect to radiostation")

        self.__stub_to_radio_station = StubManager.get_stub_manager_to_server(
            self.__radio_station_target,
            loopchain_pb2_grpc.RadioStationStub,
            conf.CONNECTION_RETRY_TIMEOUT_TO_RS)

        if self.__stub_to_radio_station is None:
            logging.warning("fail make stub to Radio Station!!")
            return None

        token = None
        if self.__auth.is_secure:
            peer_self = self.__peer_manager.get_peer(self.peer_id)
            token = None
            if peer_self is not None:
                token = peer_self.token
            logging.debug("Self Peer Token : %s", token)

            # 토큰 유효시간이 지나면 다시 생성 요청
            if token is not None and self.__auth.get_token_time(token) is None:
                token = None

            self.__auth.set_peer_info(self.peer_id, self.__peer_target, self.group_id, self.__peer_type)
            cert_bytes = self.__auth.get_cert_bytes()
            if token is None:
                # 서버로부터 난수 수신
                # response = util.request_server_in_time(self.__stub_to_radio_station.ConnectPeer,
                #                                        loopchain_pb2.PeerRequest(
                #                                            peer_object=b'',
                #                                            peer_id=self.peer_id,
                #                                            peer_target=self.__peer_target,
                #                                            group_id=self.group_id,
                #                                            peer_type=self.__peer_type,
                #                                            token=conf.TOKEN_TYPE_CERT + cert_bytes.hex())
                #                                        )
                response = self.__stub_to_radio_station.call("ConnectPeer", loopchain_pb2.PeerRequest(
                    peer_object=b'',
                    peer_id=self.peer_id,
                    peer_target=self.__peer_target,
                    group_id=self.group_id,
                    peer_type=self.__peer_type,
                    token=conf.TOKEN_TYPE_CERT + cert_bytes.hex()), conf.GRPC_TIMEOUT
                )

                rand_key = None
                if response is not None and response.status == message_code.Response.success:
                    logging.debug("Received Random : %s", response.more_info)
                    if len(response.more_info) is not 32:
                        # 토큰 크기가 16바이트가 아니면 접속을 할 수 없습니다.
                        logging.debug('서버로부터 수신한 토큰 길이는 16바이트가 되어야 합니다.')
                    else:
                        rand_key = response.more_info
                else:
                    return response

                # 난수와 Peer 정보에 서명
                if rand_key is None:
                    return None
                else:
                    sign = self.__auth.generate_request_sign(rand_key=rand_key)
                    token = conf.TOKEN_TYPE_SIGN + sign.hex()
            else:
                self.__auth.add_token(token)

        # 공통 부분
        # response = util.request_server_in_time(self.__stub_to_radio_station.ConnectPeer,
        #                                        loopchain_pb2.PeerRequest(
        #                                            peer_object=b'',
        #                                            peer_id=self.peer_id,
        #                                            peer_target=self.__peer_target,
        #                                            group_id=self.group_id,
        #                                            peer_type=self.__peer_type,
        #                                            token=token
        #                                        ))
        response = self.__stub_to_radio_station.call("ConnectPeer", loopchain_pb2.PeerRequest(
            peer_object=b'',
            peer_id=self.peer_id,
            peer_target=self.__peer_target,
            group_id=self.group_id,
            peer_type=self.__peer_type,
            token=token), conf.GRPC_CONNECTION_TIMEOUT
        )

        if response is not None and response.status == message_code.Response.success:
            if self.__auth.is_secure:
                logging.debug("Received Token : %s", response.more_info)
                # Radiostation으로부터 수신한 토큰 검증
                if len(response.more_info) < 9:
                    # 토큰 크기가 8 + 1바이트 보다 크지 아니면 접속을 할 수 없습니다.
                    logging.debug('서버로부터 수신한 토큰 길이는 9바이트 이상이 되어야 합니다.')
                    response.status = message_code.Response.fail_validate_params
                    response.more_info = "Invalid Token Data"
                else:
                    token = response.more_info
                    tag = token[:2]
                    if tag == conf.TOKEN_TYPE_TOKEN:
                        if self.__auth.verify_token(token):
                            logging.debug("토큰 검증에 성공하였습니다.")
                            self.__auth.add_token(token)
                        else:
                            logging.debug("토큰 검증에 실패하였습니다.")
                            response.status = message_code.Response.fail_validate_params
                            response.more_info = "Invalid Token Signature"

        return response

    def add_unconfirm_block(self, block_unloaded):
        block = pickle.loads(block_unloaded)
        block_hash = block.block_hash

        response_code, response_msg = message_code.get_response(message_code.Response.fail_validate_block)

        # block 검증
        block_is_validated = False
        try:
            block_is_validated = block.validate()
        except (BlockInValidError, BlockError, TransactionInValidError) as e:
            logging.error(e)

        if block_is_validated:
            # broadcast 를 받으면 받은 블럭을 검증한 후 검증되면 자신의 blockchain 의 unconfirmed block 으로 등록해 둔다.
            confirmed, reason = self.__block_manager.get_blockchain().add_unconfirm_block(block)
            if confirmed:
                response_code, response_msg = message_code.get_response(message_code.Response.success_validate_block)
            elif reason == "block_height":
                # Announce 되는 블럭과 자신의 height 가 다르면 Block Height Sync 를 다시 시도한다.
                self.block_height_sync(self.__stub_to_blockgenerator)

        return response_code, response_msg, block_hash

    def __tx_process_connect_to_leader(self, peer_process, leader_target):
        logging.debug("try... Peer Process connect_to_blockgenerator: " + leader_target)
        logging.debug("peer_process: " + str(peer_process))
        peer_process.send_to_process(("connect_to_blockgenerator", leader_target))

    def __run_tx_process(self, blockgenerator_info, inner_channel_info):
        tx_process = TxProcess()
        tx_process.start()
        tx_process.send_to_process(("status", ""))

        wait_times = 0
        wait_for_process_start = None

        while wait_for_process_start is None:
            time.sleep(conf.SLEEP_SECONDS_FOR_SUB_PROCESS_START)
            logging.debug(f"wait start tx process....")
            wait_for_process_start = tx_process.get_receive("status")

            if wait_for_process_start is None and wait_times > conf.WAIT_SUB_PROCESS_RETRY_TIMES:
                util.exit_and_msg("Tx Process start Fail!")

        logging.debug(f"Tx Process start({wait_for_process_start})")

        self.__tx_process_connect_to_leader(tx_process, blockgenerator_info)
        tx_process.send_to_process(("make_self_connection", inner_channel_info))

        return tx_process

    def __stop_tx_process(self):
        if self.__tx_process is not None:
            self.__tx_process.stop()
            self.__tx_process.wait()

    @property
    def peer_id(self):
        return self.__peer_id

    @peer_id.setter
    def peer_id(self, peer_id):
        self.__peer_id = peer_id

    @property
    def group_id(self):
        if self.__group_id is None:
            self.__group_id = self.__peer_id
        return self.__group_id

    @property
    def peer_list(self):
        return self.__peer_manager

    @property
    def peer_target(self):
        return self.__peer_target

    def block_height_sync(self, target_peer_stub=None):
        """Peer간의 데이타 동기화
        """
        if self.__block_height_sync_lock is True:
            # ***** 이 보정 프로세스는 AnnounceConfirmBlock 메시지를 받았을때 블럭 Height 차이로 Peer 가 처리하지 못한 경우에도 진행한다.
            # 따라서 이미 sync 가 진행 중일때의 요청은 무시한다.
            logging.warning("block height sync is already running...")
            return

        self.__block_height_sync_lock = True
        if target_peer_stub is None:
            target_peer_stub = self.__stub_to_blockgenerator

        ### Block Height 보정 작업, Peer의 데이타 동기화 Process ###
        ### Love&Hate Algorithm ###
        logging.info("try block height sync...with love&hate")

        # Make Peer Stub List [peer_stub, ...] and get max_height of network
        max_height = 0
        peer_stubs = []
        for peer_target in self.__peer_manager.get_IP_of_peers_in_group():
            target = ":".join(peer_target.split(":")[1:])
            if target != self.__peer_target:
                logging.debug(f"try to target({target})")
                channel = grpc.insecure_channel(target)
                stub = loopchain_pb2_grpc.PeerServiceStub(channel)
                try:
                    response = stub.GetStatus(loopchain_pb2.StatusRequest(request=""))
                    if response.block_height > max_height:
                        # Add peer as higher than this
                        max_height = response.block_height
                        peer_stubs.append(stub)
                except Exception as e:
                    logging.warning("Already bad.... I don't love you" + str(e))

        my_height = self.__block_manager.get_blockchain().block_height

        if max_height > my_height:  # 자기가 가장 높은 블럭일때 처리 필요 TODO
            logging.info(f"You need block height sync to: {max_height} yours: {my_height}")
            # 자기(현재 Peer)와 다르면 Peer 목록을 순회하며 마지막 block 에서 자기 Height Block 까지 역순으로 요청한다.
            # (blockchain 의 block 탐색 로직 때문에 height 순으로 조회는 비효율적이다.)

            preload_blocks = {}  # height : block dictionary

            # Target Peer 의 마지막 block hash 부터 시작한다.
            response = target_peer_stub.call(
                "GetLastBlockHash",
                loopchain_pb2.StatusRequest(request="")
            )
            logging.debug(response)
            request_hash = response.block_hash

            max_try = max_height - my_height
            while self.__block_manager.get_blockchain().last_block.block_hash != request_hash and max_try > 0:

                for peer_stub in peer_stubs:
                    response = None
                    try:
                        # 이때 요청 받은 Peer 는 해당 Block 과 함께 자신의 현재 Height 를 같이 보내준다.
                        # TODO target peer 의 마지막 block 보다 높은 Peer 가 있으면 현재 target height 까지 완료 후
                        # TODO Height Sync 를 다시 한다.
                        response = peer_stub.BlockSync(loopchain_pb2.BlockSyncRequest(block_hash=request_hash),
                                                       conf.GRPC_TIMEOUT)
                    except Exception as e:
                        logging.warning("There is a bad peer, I hate you: " + str(e))

                    if response is not None and response.response_code == message_code.Response.success:
                        dump = response.block
                        block = pickle.loads(dump)

                        # 마지막 블럭에서 역순으로 블럭을 구한다.
                        request_hash = block.prev_block_hash

                        # add block to preload_blocks
                        logging.debug("Add preload_blocks Height: " + str(block.height))
                        preload_blocks[block.height] = block

                        if response.max_block_height > max_height:
                            max_height = response.max_block_height

                        if (my_height + 1) == block.height:
                            max_try = 0  # 더이상 요청을 진행하지 않는다.
                            logging.info("Block Height Sync Complete.")
                            break
                        max_try -= 1
                    else:
                        # 이 반복 요청중 응답 하지 않은 Peer 는 반복중에 다시 요청하지 않는다.
                        # (TODO: 향후 Bad에 대한 리포트 전략은 별도로 작업한다.)
                        peer_stubs.remove(peer_stub)
                        logging.warning("Make this peer to bad (error above or no response): " + str(peer_stub))

            if preload_blocks.__len__() > 0:
                while my_height < max_height:
                    add_height = my_height + 1
                    logging.debug("try add block height: " + str(add_height))
                    try:
                        self.__block_manager.add_block(preload_blocks[add_height])
                        my_height = add_height
                    except KeyError as e:
                        logging.error("fail block height sync: " + str(e))
                        break
                    except exception.BlockError as e:
                        logging.error("Block Error Clear all block and restart peer.")
                        self.__block_manager.clear_all_blocks()
                        util.exit_and_msg("Block Error Clear all block and restart peer.")

            if my_height < max_height:
                # block height sync 가 완료되지 않았으면 다시 시도한다.
                logging.warning("fail block height sync in one time... try again...")
                self.__block_height_sync_lock = False
                self.block_height_sync(target_peer_stub)

        self.__block_height_sync_lock = False

    def reset_voter_count(self):
        """peer_list 의 활성화 상태(gRPC 응답)을 갱신하여 voter 수를 변경한다.

        :return:
        """
        if self.__reset_voter_in_progress is not True:
            self.__reset_voter_in_progress = True
            logging.debug("reset voter count before: " + str(self.__common_service.get_voter_count()))

            # TODO peer_list 를 순회하면서 gRPC 오류인 사용자를 remove_audience 한다.
            self.__peer_manager.reset_peers(None, self.__common_service.remove_audience)
            logging.debug("reset voter count after: " + str(self.__common_service.get_voter_count()))
            self.__reset_voter_in_progress = False

    def set_chain_code(self, score):
        """Score를 패스로 전달하지 않고 (serve(...)의 score 는 score 의 파일 Path 이다.)
        Object 를 직접 할당하기 위한 인터페이스로 serve 호출전에 지정되어야 한다.

        :param score: score Object
        """
        # TODO 현재는 테스트를 위해서만 사용되고 있다. 검토후 제거 할 것
        self.__score = score
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
            self.__rest_service = RestService(int(port))

        self.__score_service = ScoreService(int(port) + conf.PORT_DIFF_SCORE_CONTAINER)

        # TODO tx service 는 더이상 사용하지 않는다. 하지만 이 로직을 제거하면 블록체인 네트워크가 정상적으로 형성되지 않는
        # 버그가 발생한다. 원인 파악 필요함
        self.__tx_service = TxService(int(port) + conf.PORT_DIFF_TX_CONTAINER)

        # TODO stub to score service Connect 확인을 util 로 할 수 있게 수정하기
        # self.__stub_to_score_service = util.get_stub_to_server('localhost:' +
        #                                                        str(int(port) + conf.PORT_DIFF_SCORE_CONTAINER),
        #                                                        loopchain_pb2_grpc.ContainerStub)
        self.__stub_to_score_service = StubManager.get_stub_manager_to_server(
            conf.IP_PEER + ':' + str(int(port) + conf.PORT_DIFF_SCORE_CONTAINER),
            loopchain_pb2_grpc.ContainerStub,
            is_allow_null_stub=True
        )

    def serve(self, port, score=conf.DEFAULT_SCORE_PACKAGE):
        """피어 실행

        :param port: 피어의 실행포트
        :param score: 피어의 실행 체인코드
        """
        stopwatch_start = timeit.default_timer()

        is_all_service_safe_start = True
        is_delay_announce_new_leader = False

        self.__port_init(port)
        self.__run_inner_services(port)

        inner_service_port = conf.PORT_INNER_SERVICE or (int(port) + conf.PORT_DIFF_INNER_SERVICE)
        self.__common_service = CommonService(loopchain_pb2, self.__peer_target, inner_service_port)
        self.peer_id = str(self.__common_service.get_peer_id())
        self.__peer_manager = self.__common_service.load_peer_manager()
        self.__block_manager = self.__load_block_manager()

        response = self.__connect_to_radiostation()
        logging.debug("Connect to radiostation: " + str(response))

        is_peer_list_from_rs = False

        if response is not None and response.status == message_code.Response.success:
            # RS 의 응답이 있으면 peer_list 는 RS 가 전달한 결과로 업데이트 된다.
            # 없는 경우 local 의 level DB 로 부터 읽어드린 값을 default 로 사용하게 된다.
            # TODO RS 는 어떻게 신뢰하지? RS 가 새로운 피어의 참여를 승인하더라도 참여한 피어 목록은 더 신뢰할만한 방식으로 보호가 필요하지 않나?
            # 누군가 RS 를 죽인다면 RS 인척 가짜로 이루어진 피어 리스트를 전송하면 네트워크를 파괴할 수 있지 않나?
            # 피어의 참여는 RS 가 승인한 다음 블록에 담아서 블록체인에 추가하면 어떨까?

            peer_list_data = pickle.loads(response.peer_list)
            self.__peer_manager.load(peer_list_data, False)
            self.__common_service.save_peer_list(self.__peer_manager)
            logging.debug("peer list update: " + self.__peer_manager.get_peers_for_debug())
            is_peer_list_from_rs = True
        else:
            logging.debug("using local peer list: " + self.__peer_manager.get_peers_for_debug())

        logging.debug("peer_id: " + str(self.peer_id))

        if self.__peer_manager.get_peer_count() == 0:
            util.exit_and_msg("There is no peer_list, initial network is not allowed without RS!")
        peer_self = self.__peer_manager.get_peer(self.peer_id, self.group_id)
        logging.debug("peer_self: " + str(peer_self))
        peer_leader = self.__peer_manager.get_leader_peer(is_complain_to_rs=True)
        logging.debug("peer_leader: " + str(peer_leader))

        # TODO LOOPCHAIN-61 인증서 로드
        _cert = None
        # TODO LOOPCHAIN-61 인증서 키로드
        _private_key = None
        # TODO 인증정보 요청

        # TODO 이 부분을 조건 검사가 아니라 leader complain 을 이용해서 리더가 되도록 하는 방법 검토하기
        if peer_self.peer_id == peer_leader.peer_id:
            # 자기가 peer_list 의 유일한 connected PEER 이거나 rs 의 leader 정보와 같을 때 block generator 가 된다.
            if is_peer_list_from_rs is True or self.__peer_manager.get_connected_peer_count(None) == 1:
                logging.debug("Set Peer Type Block Generator!")
                self.__peer_type = loopchain_pb2.BLOCK_GENERATOR

        # load score 는 score 서비스가 시작된 이후 block height sync 가 시작되기전에 이루어져야 한다.
        is_all_service_safe_start &= self.__load_score(score)

        if self.__peer_type == loopchain_pb2.PEER:
            # leader 로 시작하지 않았는데 자신의 정보가 leader Peer 정보이면 block height sync 하여
            # 최종 블럭의 leader 를 찾는다.
            if peer_leader.target != self.__peer_target:
                block_sync_target_stub = StubManager.get_stub_manager_to_server(
                    peer_leader.target,
                    loopchain_pb2_grpc.PeerServiceStub,
                    time_out_seconds=conf.GRPC_TIMEOUT
                )
            else:
                block_sync_target_stub = None

            if block_sync_target_stub is None:
                logging.warning("You maybe Older from this network... or No leader in this network!")

                # TODO 이 상황에서 rs 에 leader complain 을 진행한다
                is_delay_announce_new_leader = True
                peer_old_leader = peer_leader
                peer_leader = self.__peer_manager.leader_complain_to_rs(conf.ALL_GROUP_ID, is_announce_new_peer=False)

                if peer_leader is not None:
                    block_sync_target_stub = StubManager.get_stub_manager_to_server(
                        peer_leader.target,
                        loopchain_pb2_grpc.PeerServiceStub,
                        time_out_seconds=conf.GRPC_TIMEOUT
                    )

            if peer_leader is None or peer_leader.peer_id == peer_self.peer_id:
                peer_leader = peer_self
                self.__peer_type = loopchain_pb2.BLOCK_GENERATOR
            else:
                self.block_height_sync(block_sync_target_stub)

                # # TODO 마지막 블럭으로 leader 정보를 판단하는 로직은 리더 컴플레인 알고리즘 수정 후 유효성을 다시 판단할 것
                # last_block_peer_id = self.__block_manager.get_blockchain().last_block.peer_id
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
                #     self.__stub_to_blockgenerator = self.__peer_list.get_peer_stub_manager(new_leader_peer)
                #     peer_leader = new_leader_peer
                # else:
                #     self.__stub_to_blockgenerator = block_sync_target_stub

                self.__stub_to_blockgenerator = block_sync_target_stub

                if self.__stub_to_blockgenerator is None:
                    util.exit_and_msg("Fail connect to leader!!")

                self.show_peers()

        self.__common_service.set_peer_type(self.__peer_type)

        if self.__peer_type == loopchain_pb2.BLOCK_GENERATOR:
            self.__block_manager.set_peer_type(self.__peer_type)

        loopchain_pb2_grpc.add_PeerServiceServicer_to_server(self.__outer_service, self.__common_service.outer_server)
        loopchain_pb2_grpc.add_InnerServiceServicer_to_server(self.__inner_service, self.__common_service.inner_server)
        logging.info("Start peer service at port: " + str(port))

        self.__block_manager.start()
        self.__common_service.start(port, self.peer_id, self.group_id)

        if self.__stub_to_radio_station is not None:
            self.__common_service.subscribe(self.__stub_to_radio_station)

        # Start Peer Process for gRPC send to Block Generator
        # But It use only when create tx (yet)
        logging.debug("peer_leader target is: " + str(peer_leader.target))

        self.__tx_process = self.__run_tx_process(
            blockgenerator_info=peer_leader.target,
            inner_channel_info=conf.IP_LOCAL + ":" + str(inner_service_port)
        )

        if self.__stub_to_blockgenerator is not None:
            self.__common_service.subscribe(self.__stub_to_blockgenerator, loopchain_pb2.BLOCK_GENERATOR)

        if is_delay_announce_new_leader:
            self.__peer_manager.announce_new_leader(peer_old_leader.peer_id, peer_leader.peer_id)

        self.__send_to_process_thread = SendToProcess(self.__tx_process)
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

        logging.info("Peer Service Ended.")
        self.__score_service.stop()
        if self.__rest_service is not None:
            self.__rest_service.stop()
        self.__tx_service.stop()
        self.__stop_tx_process()
