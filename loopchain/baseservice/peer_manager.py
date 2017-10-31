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
"""A module for managing peer list"""

import json
import logging
import pickle
import threading

import loopchain.utils as util
from loopchain import configure as conf
from loopchain.baseservice import ObjectManager, StubManager, PeerStatus, PeerObject
from loopchain.protos import loopchain_pb2_grpc, message_code

# loopchain_pb2 를 아래와 같이 import 하지 않으면 broadcast 시도시 pickle 오류가 발생함
import loopchain_pb2


class PeerListData:
    """PeerList 를 DB 에 저장하기 위해 dump 성 데이터를 따로 관리한다.
    gRPC stub 은 pickle 로 덤프시 오류가 발생한다.
    """
    def __init__(self):
        # TODO self.var -> self.__var and use @property 바꾸기~~ ^^
        # { group_id: { peer_id:PeerInfo } } 로 구성된 dictionary
        self.__peer_info_list: dict = {}
        # { group_id : leader_order } 인 정보, 기존의 block_generator_target 정보를 대체한다.
        self.__peer_leader: dict = {}
        # { group_id : { order:peer_id } 인 order 순서 정보
        self.__peer_order_list: dict = {}

    @property
    def peer_leader(self):
        return self.__peer_leader

    @peer_leader.setter
    def peer_leader(self, peer_leader):
        self.__peer_leader = peer_leader

    @property
    def peer_order_list(self):
        return self.__peer_order_list

    @peer_order_list.setter
    def peer_order_list(self, peer_order_list):
        self.__peer_order_list = peer_order_list

    @property
    def peer_info_list(self):
        return self.__peer_info_list

    @peer_info_list.setter
    def peer_info_list(self, peer_info_list):
        self.__peer_info_list = peer_info_list


class PeerManager:
    def __init__(self, channel_name=None):
        if channel_name is None:
            channel_name = conf.LOOPCHAIN_DEFAULT_CHANNEL
        # TODO self.var -> self.__var and use @property 바꾸기~~ ^^
        """DB에서 기존에 생성된 PeerList 를 가져온다.
        이때 peer status 는 unknown 으로 리셋한다.
        """
        self.peer_list_data = PeerListData()
        self.__channel_name = channel_name
        self.__peer_object_list = {}
        # peer group 은 전체 peer 가 등록된 ALL GROUP 과 개별 group_id 로 구분된 리스트가 존재한다.
        self.__init_peer_group(conf.ALL_GROUP_ID)
        # lock object for if add new peer don't have order that must locking
        self.__add_peer_lock: threading.Lock = threading.Lock()

        self.__peer_id = None
        if ObjectManager().peer_service is not None:
            self.__peer_id = ObjectManager().peer_service.peer_id

    @property
    def peer_object_list(self) -> dict:
        """

        :return:  group_id: { peer_id:Peer } }
        """
        return self.__peer_object_list

    @property
    def peer_list(self) -> dict:
        """

        :return: { group_id: { peer_id:PeerInfo } }
        """
        return self.peer_list_data.peer_info_list

    @property
    def peer_leader(self) -> dict:
        """

        :return: { group_id : leader_order }
        """
        return self.peer_list_data.peer_leader

    @property
    def peer_order_list(self) -> dict:
        """

        :return: { group_id : { order:peer_id }
        """
        return self.peer_list_data.peer_order_list

    def dump(self):
        """DB에 저장가능한 data dump를 제공한다.

        :return: dump data of PeerList
        """
        return pickle.dumps(self.peer_list_data)

    def load(self, peer_list_data, do_reset=True):
        """DB 로 부터 로드한 dump data 로 PeerList 를 복원한다.

        :param peer_list_data: pickle 로 로드한 PeerList 의 dump 데이타
        :param do_reset: RS 로부터 받았을 때에는 status 를 리셋하지 않는다.
        """
        self.peer_list_data = peer_list_data
        if do_reset:
            self.__reset_peer_status()
        self.__set_peer_object_list()

        return self

    def __set_peer_object_list(self):
        """ peer_info_list convert peer_object_list"""

        for group_id in list(self.peer_list_data.peer_info_list.keys()):
            self.__peer_object_list[group_id] = self.__set_peer_object_list_in_group(group_id)

    def __set_peer_object_list_in_group(self, group_id):
        """peer_info_list[group_id] -> peer_object_list[group_id]

        :param group_id: group_id
        :return: {peer_id: PeerObject, ... }
        """
        def convert_peer_info_item_to_peer_item(item):
            """(peer_id, PeerInfo) -> (peer_id, PeerObject)

            :param item: (peer_id, PeerInfo)
            :return: peer_id, PeerObject)
            """
            return item[0], PeerObject(item[1])
        # PeerInfo List To PeerObjectList
        # map(func, [a, b] ) -> [func(a), func(b)]
        # dict([(a, b), (a1,b1)]) -> {a: b, a1, b1}
        return dict(
            map(convert_peer_info_item_to_peer_item, self.peer_list_data.peer_info_list[group_id].items())
        )

    def __get_peer_by_target(self, peer_target):
        for group_id in self.peer_list.keys():
            for peer_id in self.peer_list[group_id]:
                peer_each = self.peer_list[group_id][peer_id]
                if peer_each.target == peer_target:
                    return peer_each
        return None

    def add_peer(self, peer_info):
        """add_peer to peer_manager

        :param peer_info: PeerInfo
        :return: create_peer_order
        """
        logging.debug(f"add peer id: {peer_info.peer_id}")

        # If exist same peer_target in peer_list, delete exist one.
        # this is temporary rule that will be argued.
        # if peer_info.peer_id not in self.peer_list[conf.ALL_GROUP_ID].keys():
        #     exist_peer = self.__get_peer_by_target(peer_info.target)
        #     if exist_peer is not None:
        #         self.remove_peer(exist_peer.peer_id, exist_peer.group_id)

        self.__init_peer_group(peer_info.group_id)

        util.logger.spam(f"peer_manager::add_peer try make PeerObject")
        peer = PeerObject(peer_info)

        # add_peer logic must be atomic
        self.__add_peer_lock.acquire()

        if peer_info.order <= 0:
            if peer_info.peer_id in self.peer_list[peer_info.group_id]:
                peer_info.order = self.peer_list[peer_info.group_id][peer_info.peer_id].order
            else:
                peer_info.order = self.__make_peer_order(peer_info)

        logging.debug(f"new peer order {peer_info.peer_id} : {peer_info.order}")

        # set to leader peer
        if (self.peer_leader[peer_info.group_id] == 0) or (len(self.peer_list[peer_info.group_id]) == 0):
            logging.debug("Set Group Leader Peer: " + str(peer_info.order))
            self.peer_leader[peer_info.group_id] = peer_info.order

        if (self.peer_leader[conf.ALL_GROUP_ID] == 0) or (len(self.peer_list[conf.ALL_GROUP_ID]) == 0):
            logging.debug("Set ALL Leader Peer: " + str(peer_info.order))
            self.peer_leader[conf.ALL_GROUP_ID] = peer_info.order

        self.peer_list[peer_info.group_id][peer_info.peer_id] = peer_info
        self.peer_list[conf.ALL_GROUP_ID][peer_info.peer_id] = peer_info
        self.peer_order_list[peer_info.group_id][peer_info.order] = peer_info.peer_id
        self.peer_order_list[conf.ALL_GROUP_ID][peer_info.order] = peer_info.peer_id
        self.__peer_object_list[peer_info.group_id][peer_info.peer_id] = peer
        self.__peer_object_list[conf.ALL_GROUP_ID][peer_info.peer_id] = peer

        self.__add_peer_lock.release()

        return peer_info.order

    def update_peer_status(self, peer_id, group_id=None, peer_status=PeerStatus.connected):
        if group_id is None:
            group_id = conf.ALL_GROUP_ID
        try:
            peer = self.peer_list[group_id][peer_id]
            peer.status = peer_status
            return peer
        except Exception as e:
            logging.warning(f"fail update peer status peer_id({peer_id})")

        return None

    def set_leader_peer(self, peer, group_id=None):
        """리더 피어를 지정한다. group_id 를 지정하면 sub leader 를 지정하고
        없는 경우에는 전체 리더 피어를 지정하게 된다.

        :param peer: 리더로 지정할 peer 의 정보
        :param group_id: sub group 의 id
        :return:
        """

        if self.get_peer(peer.peer_id, peer.group_id) is None:
            self.add_peer(peer)

        if group_id is None:
            self.peer_leader[conf.ALL_GROUP_ID] = peer.order
        else:
            self.peer_leader[group_id] = peer.order

    def get_leader_peer(self, group_id=None, is_complain_to_rs=False, is_peer=True):
        """현재는 sub leader 에 대한 처리는 하지 않는다.

        :param group_id:
        :return:
        """

        # if group_id is None:
        search_group = conf.ALL_GROUP_ID

        try:
            leader_peer_id = self.get_leader_id(search_group)

            leader_peer = self.get_peer(leader_peer_id, search_group)
            return leader_peer
        except KeyError as e:
            logging.exception(e)
            if is_complain_to_rs:
                return self.leader_complain_to_rs(search_group)
            else:
                if is_peer:
                    util.exit_and_msg(f"Fail to find a leader of this network.... {e}")
                else:
                    return None

    def get_leader_id(self, search_group) -> str:
        """ get leader's peer id

        :param search_group:
        :return: leader peer_id
        """
        leader_peer_order = self.peer_leader[search_group]
        logging.debug(f"peer_manager:get_leader_id leader peer order {leader_peer_order}")
        # util.logger.spam(f"peer_manager:get_leader_id peer_orger_list({self.peer_order_list})")
        leader_peer_id = self.peer_order_list[search_group][leader_peer_order]
        return leader_peer_id

    def get_leader_object(self) -> PeerObject:
        """ get leader peer object

        :param search_group:
        :return: leader peer object
        """

        search_group = conf.ALL_GROUP_ID
        # TODO group 별 리더가 필요하면 그에 맞춰 구현
        leader_id = self.get_leader_id(search_group)
        leader_object = self.peer_object_list[search_group][leader_id]
        return leader_object

    def leader_complain_to_rs(self, group_id, is_announce_new_peer=True):
        """When fail to find a leader, Ask to RS.
        RS check leader and notify leader info or set new leader first peer who complained

        :param group_id:
        :param is_announce_new_peer:
        :return:
        """

        if ObjectManager().peer_service.stub_to_radiostation is None:
            return None

        peer_self = self.get_peer(ObjectManager().peer_service.peer_id, ObjectManager().peer_service.group_id)
        peer_self_dump = pickle.dumps(peer_self)
        response = ObjectManager().peer_service.stub_to_radiostation.call(
            "Request",
            loopchain_pb2.Message(
                code=message_code.Request.peer_complain_leader,
                message=group_id,
                object=peer_self_dump
            )
        )

        # leader_peer = pickle.loads(response.object)
        if response is not None and response.code == message_code.Response.success:
            leader_peer = pickle.loads(response.object)
            self.set_leader_peer(leader_peer)
        else:
            leader_peer = None

        # logging.debug(str(leader_peer))
        # self.set_leader_peer(leader_peer)
        #
        # if is_announce_new_peer:
        #     self.announce_new_leader("", leader_peer.peer_id)

        return leader_peer

    def get_next_leader_peer(self, group_id=None, is_only_alive=False):
        util.logger.spam(f"peer_manager:get_next_leader_peer")
        leader_peer = self.get_leader_peer(group_id, is_complain_to_rs=True)
        return self.__get_next_peer(leader_peer, group_id, is_only_alive)

    def __get_next_peer(self, peer, group_id=None, is_only_alive=False):
        if peer is None:
            return None

        if group_id is None:
            group_id = conf.ALL_GROUP_ID

        order_list = list(self.peer_order_list[group_id].keys())
        order_list.sort()

        # logging.debug("order list: " + str(order_list))
        # logging.debug("peer.order: " + str(peer.order))

        peer_order_position = order_list.index(peer.order)
        next_order_position = peer_order_position + 1
        peer_count = len(order_list)

        util.logger.spam(f"peer_manager:__get_next_peer peer_count({peer_count})")

        for i in range(peer_count):
            # Prevent out of range
            if next_order_position >= peer_count:
                next_order_position = 0

            # It doesn't matter that peer status is connected or not, when 'is_only_alive' is false.
            if not is_only_alive:
                break

            peer_order = order_list[next_order_position]
            peer_id = self.peer_order_list[group_id][peer_order]
            peer_each = self.peer_list[group_id][peer_id]

            # It need to check real time status of peer, if 'is_only_alive' is true and status is connected.
            if is_only_alive and peer_each.status == PeerStatus.connected:

                next_peer_id = self.peer_order_list[group_id][order_list[next_order_position]]
                leader_peer = self.peer_list[group_id][next_peer_id]
                stub_manager = self.get_peer_stub_manager(leader_peer)

                response = stub_manager.call_in_times(
                    "Request", loopchain_pb2.Message(
                        code=message_code.Request.status,
                        channel=self.__channel_name
                    ), is_stub_reuse=True)

                # If it has no response, increase count of 'next_order_position' for checking next peer.
                if response is not None:
                    break  # LABEL 1

            next_order_position += 1
            util.logger.spam(f"peer_manager:__get_next_peer next_order_position({next_order_position})")

        # Prevent out of range
        # TODO LABEL 1 에서 break 되지 않은 경우 response 가 적절하게 오지 않은 경우 list out of range 가 발생한다.
        if next_order_position >= peer_count:
            util.logger.spam(f"peer_manager:__get_next_peer Fail break at LABEL 1")
            next_order_position = 0

        try:
            next_peer_id = self.peer_order_list[group_id][order_list[next_order_position]]
            logging.debug("peer_manager:__get_next_peer next_leader_peer_id: " + str(next_peer_id))
            return self.peer_list[group_id][next_peer_id]
        except IndexError as e:
            logging.warning(f"peer_manager:__get_next_peer there is no next peer ({e})")
            util.logger.spam(f"peer_manager:__get_next_peer "
                             f"\npeer_id({peer.peer_id}), group_id({group_id}), "
                             f"\npeer_order_list({self.peer_object_list}), "
                             f"\npeer_list[group_id]({self.peer_list[group_id]})")
            return None

    def get_next_leader_stub_manager(self, group_id=None):
        """다음 리더 peer, stub manager 을 식별한다.

        :param group_id:
        :return: peer, stub manager
        """
        util.logger.spam(f"peer_manager:get_next_leader_stub_manager")
        # TODO 피어 재시작 후의 접속하는 피어의 connected 상태 변경 확인할 것
        # connected peer 만 순회하도록 수정할 것, 현재는 확인 되지 않았으므로 전체 순회로 구현함
        # max_retry = self.get_connected_peer_count(group_id)

        if group_id is None:
            group_id = conf.ALL_GROUP_ID

        max_retry = self.get_peer_count(None)
        try_count = 0

        next_leader_peer = self.__get_next_peer(self.get_leader_peer(group_id), group_id)

        while try_count < max_retry:
            stub_manager = StubManager(next_leader_peer.target, loopchain_pb2_grpc.PeerServiceStub)
            try:
                try_count += 1
                response = stub_manager.call("GetStatus", loopchain_pb2.CommonRequest(request=""))
                logging.debug("Peer Status: " + str(response))
                return next_leader_peer, stub_manager
            except Exception as e:
                logging.debug("try another stub..." + str(e))

            next_leader_peer = self.__get_next_peer(next_leader_peer, group_id)

        logging.warning("fail found next leader stub")
        return None, None

    def get_leader_stub_manager(self, group_id=None):
        return self.get_peer_stub_manager(self.get_leader_peer(group_id), group_id)

    def get_peer_stub_manager(self, peer, group_id=None):
        logging.debug("get_peer_stub_manager")
        logging.debug(f"peer_info : {peer.peer_id} {peer.group_id}")
        if group_id is None:
                group_id = conf.ALL_GROUP_ID
        try:
            return self.__peer_object_list[group_id][peer.peer_id].stub_manager
        except Exception as e:
            logging.debug("try get peer stub except: " + str(e))
            return None

    def announce_new_leader(self, complained_leader_id, new_leader_id, is_broadcast=True):
        """Announce New Leader Id to Network

        :param complained_leader_id:
        :param new_leader_id:
        :param is_broadcast: False(notify to RS only), True(broadcast to network include RS)
        :return:
        """
        util.logger.spam(f"peer_manager:announce_new_leader channel({self.__channel_name})")
        is_rs = False

        announce_message = loopchain_pb2.ComplainLeaderRequest(
            complained_leader_id=complained_leader_id,
            channel=self.__channel_name,
            new_leader_id=new_leader_id,
            message="Announce New Leader"
        )

        # new_leader_peer = self.get_peer(new_leader_id)

        # Announce New Leader to Radio station
        try:
            if ObjectManager().peer_service.stub_to_radiostation is not None:
                response = ObjectManager().peer_service.stub_to_radiostation.call("AnnounceNewLeader", announce_message)
                if response.response_code == message_code.Response.fail_no_peer_info_in_rs:
                    util.logger.spam(
                        f"peer_manager:announce_new_leader fail no peer info in rs! is_broadcast({is_broadcast})")
                    announce_message.message = message_code.get_response_msg(
                        message_code.Response.fail_no_peer_info_in_rs)
                    ObjectManager().peer_service.connect_to_radiostation(channel=self.__channel_name, is_reconnect=True)
                    ObjectManager().peer_service.common_service.broadcast(
                        "Request",
                        loopchain_pb2.Message(
                            code=message_code.Request.peer_reconnect_to_rs,
                            channel=self.__channel_name)
                    )
        except Exception as e:
            # logging.debug("in RS there is no peer_service....")
            is_rs = True

        if is_broadcast is True:
            for peer_id in list(self.peer_list[conf.ALL_GROUP_ID]):
                if new_leader_id == peer_id and is_rs is not True:
                    util.logger.spam(f"Prevent reset leader loop in AnnounceNewLeader message")
                    continue
                peer_each = self.peer_list[conf.ALL_GROUP_ID][peer_id]
                stub_manager = self.get_peer_stub_manager(peer_each, conf.ALL_GROUP_ID)
                try:
                    stub_manager.call("AnnounceNewLeader", announce_message, is_stub_reuse=True)
                except Exception as e:
                    logging.warning("gRPC Exception: " + str(e))
                    logging.debug("No response target: " + str(peer_each.target))


    def announce_new_peer(self, peer_request):
        logging.debug("announce_new_peer")
        for peer_id in list(self.peer_list[conf.ALL_GROUP_ID]):
            peer_each = self.peer_list[conf.ALL_GROUP_ID][peer_id]
            stub_manager = self.get_peer_stub_manager(peer_each, peer_each.group_id)
            try:
                if peer_each.target != peer_request.peer_target:
                    stub_manager.call("AnnounceNewPeer", peer_request, is_stub_reuse=True)
            except Exception as e:
                logging.warning("gRPC Exception: " + str(e))
                logging.debug("No response target: " + str(peer_each.target))

    def complain_leader(self, group_id=None, is_announce=False):
        """When current leader is offline, Find last height alive peer and set as a new leader.

        :param complain_peer:
        :param group_id:
        :param is_announce:
        :return:
        """
        if group_id is None:
            group_id = conf.ALL_GROUP_ID
        leader_peer = self.get_leader_peer(group_id=group_id, is_peer=False)
        try:
            stub_manager = self.get_peer_stub_manager(leader_peer, group_id)
            response = stub_manager.call("GetStatus", loopchain_pb2.StatusRequest(request=""), is_stub_reuse=True)

            status_json = json.loads(response.status)
            logging.warning(f"stub_manager target({stub_manager.target}) type({status_json['peer_type']})")

            if status_json["peer_type"] == str(loopchain_pb2.BLOCK_GENERATOR):
                return leader_peer
            else:
                raise Exception
        except Exception as e:
            new_leader = self.__find_last_height_peer(group_id=group_id)
            if new_leader is not None:
                # 변경된 리더를 announce 해야 한다
                logging.warning("Change peer to leader that complain old leader.")
                self.set_leader_peer(new_leader, None)
                if is_announce is True:
                    self.announce_new_leader(
                        complained_leader_id=new_leader.peer_id, new_leader_id=new_leader.peer_id,
                        is_broadcast=True
                    )
        return new_leader

    def __find_last_height_peer(self, group_id):
        # 강제로 list 를 적용하여 값을 복사한 다음 사용한다. (중간에 값이 변경될 때 발생하는 오류를 방지하기 위해서)
        most_height = 0
        most_height_peer = None
        for peer_id in list(self.peer_list[group_id]):
            peer_each = self.peer_list[group_id][peer_id]
            stub_manager = peer_each.stub_manager
            try:
                response = stub_manager.call("GetStatus",
                                             loopchain_pb2.StatusRequest(request="reset peers in group"),
                                             is_stub_reuse=True)

                peer_status = json.loads(response.status)
                if int(peer_status["block_height"]) >= most_height:
                    most_height = int(peer_status["block_height"])
                    most_height_peer = peer_each
            except Exception as e:
                logging.warning("gRPC Exception: " + str(e))

        if len(self.peer_list[group_id]) == 0 and group_id != conf.ALL_GROUP_ID:
            del self.peer_list[group_id]
            del self.peer_object_list[group_id]

        return most_height_peer

    def check_peer_status(self, group_id=None):
        if group_id is None:
            group_id = conf.ALL_GROUP_ID
        delete_peer_list = []
        alive_peer_last = None
        check_leader_peer_count = 0
        for peer_id in list(self.__peer_object_list[group_id]):
            peer_each = self.peer_list[group_id][peer_id]
            stub_manager = self.get_peer_stub_manager(peer_each, group_id)
            peer_object_each = self.__peer_object_list[group_id][peer_id]

            try:
                response = stub_manager.call(
                    "Request", loopchain_pb2.Message(
                        code=message_code.Request.status,
                        channel=self.__channel_name
                    ), is_stub_reuse=True)
                if response is None:
                    raise Exception

                peer_object_each.no_response_count_reset()
                peer_each.status = PeerStatus.connected
                peer_status = json.loads(response.meta)

                # logging.debug(f"Check Peer Status ({peer_status['peer_type']})")
                if peer_status["peer_type"] == loopchain_pb2.BLOCK_GENERATOR:
                    check_leader_peer_count += 1

                alive_peer_last = peer_each

            except Exception as e:
                util.apm_event(self.__peer_id, {
                    'event_type': 'DisconnectedPeer',
                    'peer_id': self.__peer_id,
                    'data': {
                        'message': 'there is disconnected peer gRPC Exception: ' + str(e),
                        'peer_id': peer_each.peer_id}})

                logging.warning("there is disconnected peer peer_id(" + peer_each.peer_id +
                                ") gRPC Exception: " + str(e))
                peer_object_each.no_response_count_up()

                util.logger.spam(
                    f"peer_manager::check_peer_status "
                    f"peer_id({peer_object_each.peer_info.peer_id}) "
                    f"no response count up({peer_object_each.no_response_count})")

                if peer_object_each.no_response_count >= conf.NO_RESPONSE_COUNT_ALLOW_BY_HEARTBEAT:
                    peer_each.status = PeerStatus.disconnected
                    logging.debug(f"peer status update time: {peer_each.status_update_time}")
                    logging.debug(f"this peer will remove {peer_each.peer_id}")
                    self.remove_peer(peer_each.peer_id, peer_each.group_id)
                    delete_peer_list.append(peer_each)

                # logging.debug(f"diff mins {util.datetime_diff_in_mins(peer_each.status_update_time)}")
                # if util.datetime_diff_in_mins(peer_each.status_update_time) >= conf.TIMEOUT_PEER_REMOVE_IN_LIST:
                #     logging.debug(f"peer status update time: {peer_each.status_update_time}")
                #     logging.debug(f"this peer will remove {peer_each.peer_id}")
                #     self.remove_peer(peer_each.peer_id, peer_each.group_id)
                #     delete_peer_list.append(peer_each)

        logging.debug(f"({self.__channel_name}) Leader Peer Count: ({check_leader_peer_count})")
        if len(delete_peer_list) > 0 and check_leader_peer_count != 1:
            if alive_peer_last is not None:
                logging.warning(f"reset network({self.__channel_name}) "
                                f"leader by RS new leader({alive_peer_last.peer_id}) "
                                f"target({alive_peer_last.target})")

                self.set_leader_peer(alive_peer_last, None)
                self.announce_new_leader(
                    complained_leader_id=alive_peer_last.peer_id, new_leader_id=alive_peer_last.peer_id,
                    is_broadcast=True
                )
            else:
                logging.error("There is no leader in this network.")

        return delete_peer_list

    def reset_peers(self, group_id, reset_action):
        if group_id is None:
            for search_group in list(self.peer_list.keys()):
                self.__reset_peers_in_group(search_group, reset_action)
        else:
            self.__reset_peers_in_group(group_id, reset_action)

    def __reset_peers_in_group(self, group_id, reset_action):
        # 강제로 list 를 적용하여 값을 복사한 다음 사용한다. (중간에 값이 변경될 때 발생하는 오류를 방지하기 위해서)
        for peer_id in list(self.peer_list[group_id]):
            peer_each = self.peer_list[group_id][peer_id]
            stub_manager = self.get_peer_stub_manager(peer_each, group_id)
            try:
                stub_manager.call("GetStatus", loopchain_pb2.StatusRequest(request="reset peers in group"),
                                  is_stub_reuse=True)
            except Exception as e:
                logging.warning("gRPC Exception: " + str(e))
                logging.debug("remove this peer(target): " + str(peer_each.target))
                self.remove_peer(peer_each.peer_id, group_id)

                if reset_action is not None:
                    reset_action(peer_each.peer_id, peer_each.target)

        if len(self.peer_list[group_id]) == 0 and group_id != conf.ALL_GROUP_ID:
            del self.peer_list[group_id]
            del self.peer_object_list[group_id]

    def __init_peer_group(self, group_id):
        logging.debug(f"before init order list {self.peer_order_list}")
        if group_id not in self.peer_list.keys():
            logging.debug("init group: " + str(group_id))
            self.peer_list[group_id] = {}
            self.peer_order_list[group_id] = {}
            self.peer_leader[group_id] = 0
            self.__peer_object_list[group_id] = {}

    def __make_peer_order(self, peer):
        """소속된 그룹과 상관없이 전체 peer 가 순서에 대한 order 값을 가진다.
        이 과정은 중복된 order 발급을 방지하기 위하여 atomic 하여야 한다.

        :param peer:
        :return:
        """
        last_order = 0
        # logging.debug("Peer List is: " + str(self.peer_list))
        # logging.debug("Peer List of peer group: " + str(self.peer_list[peer.group_id]))

        # 기존에 등록된 peer_id 는 같은 order 를 재사용한다.

        for group_id in list(self.peer_list.keys()):
            for peer_id in self.peer_list[group_id]:
                peer_each = self.peer_list[group_id][peer_id]
                logging.debug("peer each: " + str(peer_each))
                last_order = [last_order, peer_each.order][last_order < peer_each.order]

        last_order += 1

        return last_order

    def get_peer(self, peer_id, group_id=None):
        """peer_id 에 해당하는 peer 를 찾는다. group_id 가 주어지면 그룹내에서 검색하고
        없으면 전체에서 검색한다.

        :param peer_id:
        :param group_id:
        :return:
        """

        if group_id is None:
            group_id = conf.ALL_GROUP_ID
        try:
            if not isinstance(peer_id, str):
                logging.error("peer_id type is: " + str(type(peer_id)) + ":" + str(peer_id))
            if group_id is not None:
                return self.peer_list[group_id][str(peer_id)]
            else:
                return [self.peer_list[group_id][str(peer_id)]
                        for group_id in self.peer_list.keys() if str(peer_id) in self.peer_list[group_id].keys()][0]
        except KeyError:
            logging.error("there is no peer by id: " + str(peer_id))
            logging.debug(self.get_peers_for_debug(group_id))
            return None
        except IndexError:
            logging.error(f"there is no peer by id({str(peer_id)}) group_id({group_id})")
            logging.debug(self.get_peers_for_debug(group_id))
            return None

    def remove_peer(self, peer_id, group_id=None):
        logging.debug(f"remove peer : {peer_id}")

        if group_id is None:
            group_id = conf.ALL_GROUP_ID
        try:
            remove_peer = self.peer_list[group_id].pop(peer_id)
            self.__peer_object_list[group_id].pop(peer_id)
            if group_id != conf.ALL_GROUP_ID:
                self.peer_list[conf.ALL_GROUP_ID].pop(peer_id)
                self.__peer_object_list[conf.ALL_GROUP_ID].pop(peer_id)

            logging.debug("remove_peer: " + str(remove_peer.order))

            if remove_peer.order in self.peer_order_list[group_id].keys():
                del self.peer_order_list[group_id][remove_peer.order]

            if remove_peer.order in self.peer_order_list[conf.ALL_GROUP_ID].keys():
                del self.peer_order_list[conf.ALL_GROUP_ID][remove_peer.order]

            if ObjectManager().peer_service is not None:
                util.logger.spam(f"peer_manager:remove_peer try remove audience in sub processes")
                ObjectManager().peer_service.common_service.remove_audience(peer_id, remove_peer.target)

            return True
        except KeyError as e:
            logging.debug(f"peer_manager:remove_peer there is no peer({e})")

        return False

    def get_peer_count(self, group_id=None):
        count = 0
        try:
            if group_id is None:
                # count = sum([len(key) for key in self.peer_list.items()])
                count = len(self.peer_list[conf.ALL_GROUP_ID])
            else:
                count = len(self.peer_list[group_id])
        except KeyError:
            logging.debug("no peer list")

        return count

    def get_connected_peer_count(self, group_id=None):
        if group_id is None:
            group_id = conf.ALL_GROUP_ID

        return sum(
            self.peer_list[group_id][peer_id].status == PeerStatus.connected for peer_id in self.peer_list[group_id]
        )

    def __reset_peer_status(self):
        for group_id in self.peer_list.keys():
            for peer_id in self.peer_list[group_id]:
                peer_each = self.peer_list[group_id][peer_id]
                peer_each.status = PeerStatus.unknown

    def get_peers_for_debug(self, group_id=None):
        if group_id is None:
            group_id = conf.ALL_GROUP_ID
        peers = ""
        try:
            for peer_id in self.peer_list[group_id]:
                peer_each = self.peer_list[group_id][peer_id]
                peers += "\n" + (str(peer_each.order) + ":" + peer_each.target
                                 + " " + str(peer_each.status)) + " " + str(peer_id) + " (" + str(type(peer_id)) + ")"
        except KeyError:
            logging.debug("no peer list")

        return peers

    def peer_list_full_print_out_for_debug(self):
        """peer list 의 data 목록을 전체 출력한다.
        디버깅을 위한 함수로 필요한 구간에서만 호출한 후 제거할 것

        """
        peer_list = self.peer_list
        logging.warning("peer_list: " + str(peer_list.items()))
        peer_leader = self.peer_leader
        logging.warning("peer_leader: " + str(peer_leader.items()))
        peer_order_list = self.peer_order_list
        logging.warning("peer_order_list: " + str(peer_order_list.items()))

        for group_id in peer_list:
            logging.warning("group_id: " + str(group_id) + "(" + str(type(group_id)) + ")")
            # peer_list_object.get_peers_for_debug(group_id)

            for peer_id in peer_list[group_id]:
                peer_each = peer_list[group_id][peer_id]
                logging.warning("peer_each: " + str(peer_each))
                # peer_each.dump()

    def get_IP_of_peers_in_group(self, group_id=None, status=None):
        # TODO 기존 구현 호환용, 모든 코드에서 PeerManager 를 기준으로 재작성 필요함, 기존 코드는 배려하지 말고 리팩토링으로 개선할 것
        """group_id에 해당하는 peer들의 IP목록을 넘겨준다

        :param group_id: group의 ID.
        :param status: peer online status
        :return: group_id에 해당하는 peer들의 IP들의 list. group_id가 잘못되면 빈 list를 돌려준다.
        """

        if group_id is None:
            group_id = conf.ALL_GROUP_ID
        ip_list = []
        for peer_id in self.peer_list[group_id]:
            peer_each = self.peer_list[group_id][peer_id]
            if status is None or status == peer_each.status:
                ip_list.append(str(peer_each.order)+":"+peer_each.target)

        return ip_list
