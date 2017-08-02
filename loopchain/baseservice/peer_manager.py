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
from loopchain.baseservice import ObjectManager, StubManager, PeerStatus, Peer
from loopchain.protos import loopchain_pb2, loopchain_pb2_grpc, message_code


class PeerListData:
    """PeerList 를 DB 에 저장하기 위해 dump 성 데이터를 따로 관리한다.
    gRPC stub 은 pickle 로 덤프시 오류가 발생한다.
    """
    def __init__(self):
        # TODO self.var -> self.__var and use @property 바꾸기~~ ^^
        # { group_id: { peer_id:Peer } } 로 구성된 dictionary
        self.peer_list = {}
        # { group_id : leader_order } 인 정보, 기존의 block_generator_target 정보를 대체한다.
        self.peer_leader = {}
        # { group_id : { order:peer_id } 인 order 순서 정보
        self.peer_order_list = {}


class PeerManager:
    def __init__(self):
        # TODO self.var -> self.__var and use @property 바꾸기~~ ^^
        """DB에서 기존에 생성된 PeerList 를 가져온다.
        이때 peer status 는 unknown 으로 리셋한다.

        """
        self.peer_list_data = PeerListData()

        # { group_id: { peer_id:Peer } } 로 구성된 dictionary
        self.peer_list = {}
        # { group_id : leader_order } 인 정보, 기존의 block_generator_target 정보를 대체한다.
        self.peer_leader = {}
        # { group_id : { order:peer_id } 인 order 순서 정보
        self.peer_order_list = {}
        # { group_id: { peer_id:Peer gRPC stub } } 로 구성된 dictionary
        self.peer_stub_managers = {}
        self.__set_data_object_from_data()  # TODO 왜 빈 PeerList 로 init 을 하지? 확인 하고 이유 적어 놓을것

        # peer group 은 전체 peer 가 등록된 ALL GROUP 과 개별 group_id 로 구분된 리스트가 존재한다.
        self.__init_peer_group(conf.ALL_GROUP_ID)

    @property
    def peers(self):
        return self.peer_list

    def __set_data_object_from_data(self):
        # { group_id: { peer_id:Peer } } 로 구성된 dictionary
        self.peer_list = self.peer_list_data.peer_list
        # { group_id : leader_order } 인 정보, 기존의 block_generator_target 정보를 대체한다.
        self.peer_leader = self.peer_list_data.peer_leader
        # { group_id : { order:peer_id } 인 order 순서 정보
        self.peer_order_list = self.peer_list_data.peer_order_list

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
        self.__set_data_object_from_data()
        if do_reset:
            self.__reset_peer_status()

        return self

    @staticmethod
    def make_peer(peer_id, group_id, peer_target, peer_status=PeerStatus.unknown, peer_auth="", peer_token=""):
        peer = Peer()
        peer.order = -1
        peer.peer_id = peer_id
        peer.group_id = group_id
        peer.target = peer_target
        peer.status = peer_status
        peer.auth = peer_auth
        peer.token = peer_token
        return peer

    def add_peer(self, peer_id, group_id, peer_target, peer_status=PeerStatus.unknown, peer_auth="", peer_token=""):
        """peer_id 에 해당하는 peer 의 정보를 추가 혹은 갱신한다.
        RS가 시작한 이후에 접속처리된 사용자는 status 를 connected 로 기록하고
        RS가 재시작하며 DB에서 가져왔을때에는 사용자 status 를 unknown 으로 기록한다.
        명시적으로 로그아웃한 경우 disconnected 로 기록한다.

        :param peer_id:
        :param group_id:
        :param peer_target:
        :param peer_status:
        :param peer_auth:
        :param peer_token
        :return:
        """
        peer = self.make_peer(peer_id, group_id, peer_target, peer_status, peer_auth, peer_token)
        return self.add_peer_object(peer)

    def __get_peer_by_target(self, peer_target):
        for group_id in self.peer_list.keys():
            for peer_id in self.peer_list[group_id]:
                peer_each = self.peer_list[group_id][peer_id]
                if peer_each.target == peer_target:
                    return peer_each
        return None

    def add_peer_object(self, peer):
        logging.debug("in peer_list::add_peer_object")

        # If exist same peer_target in peer_list, delete exist one.
        # this is temporary rule that will be argued.
        if peer.peer_id not in self.peer_list[conf.ALL_GROUP_ID].keys():
            exist_peer = self.__get_peer_by_target(peer.target)
            if exist_peer is not None:
                self.remove_peer(exist_peer.peer_id, exist_peer.group_id)

        self.__init_peer_group(peer.group_id)
        if peer.order <= 0:
            peer.order = self.__make_peer_order(peer)

        if (self.peer_leader[peer.group_id] == 0) or (len(self.peer_list[peer.group_id]) == 0):
            logging.debug("Set Group Leader Peer: " + str(peer.order))
            self.peer_leader[peer.group_id] = peer.order

        if (self.peer_leader[conf.ALL_GROUP_ID] == 0) or (len(self.peer_list[conf.ALL_GROUP_ID]) == 0):
            logging.debug("Set ALL Leader Peer: " + str(peer.order))
            self.peer_leader[conf.ALL_GROUP_ID] = peer.order

        self.peer_list[peer.group_id][peer.peer_id] = peer
        self.peer_list[conf.ALL_GROUP_ID][peer.peer_id] = peer
        self.peer_order_list[peer.group_id][peer.order] = peer.peer_id
        self.peer_order_list[conf.ALL_GROUP_ID][peer.order] = peer.peer_id

        logging.debug("in peer_list::add_peer_object, Peer List is: " + str(self.peer_list))

        return peer.order

    def set_leader_peer(self, peer, group_id=None):
        """리더 피어를 지정한다. group_id 를 지정하면 sub leader 를 지정하고
        없는 경우에는 전체 리더 피어를 지정하게 된다.

        :param peer: 리더로 지정할 peer 의 정보
        :param group_id: sub group 의 id
        :return:
        """

        if self.get_peer(peer.peer_id, peer.group_id) is None:
            self.add_peer_object(peer)

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
            leader_peer_id = self.peer_order_list[search_group][self.peer_leader[search_group]]
            leader_peer = self.get_peer(leader_peer_id, search_group)
            return leader_peer
        except KeyError as e:
            if is_complain_to_rs:
                return self.leader_complain_to_rs(search_group)
            else:
                if is_peer:
                    util.exit_and_msg(f"Fail to find a leader of this network.... {e}")
                else:
                    return None

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
                    "GetStatus",
                    loopchain_pb2.StatusRequest(request="peer_list.__get_next_peer"),
                    conf.GRPC_TIMEOUT
                )

                # If it has no response, increase count of 'next_order_position' for checking next peer.

                if response is not None and response.status != "":
                    break

            next_order_position += 1

        next_peer_id = self.peer_order_list[group_id][order_list[next_order_position]]
        logging.debug("next_leader_peer_id: " + str(next_peer_id))

        return self.peer_list[group_id][next_peer_id]

    def get_next_leader_stub_manager(self, group_id=None):
        """다음 리더 peer, stub manager 을 식별한다.

        :param group_id:
        :return: peer, stub manager
        """

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

    def get_peer_stub_manager(self, peer, group_id=None):
        if group_id is None:
                group_id = conf.ALL_GROUP_ID
        try:
            return self.peer_stub_managers[group_id][peer.peer_id]
        except KeyError:
            try:
                self.__init_peer_group(peer.group_id)
                stub_manager = StubManager(peer.target, loopchain_pb2_grpc.PeerServiceStub)
                self.peer_stub_managers[group_id][peer.peer_id] = stub_manager
                return stub_manager
            except Exception as e:
                logging.debug("try get peer stub except: " + str(e))
                logging.warning("fail make peer stub: " + peer.target)
                return None

    def announce_new_leader(self, complained_leader_id, new_leader_id, is_broadcast=True):
        """Announce New Leader Id to Network

        :param complained_leader_id:
        :param new_leader_id:
        :param is_broadcast: False(notify to RS only), True(broadcast to network include RS)
        :return:
        """

        announce_message = loopchain_pb2.ComplainLeaderRequest(
            complained_leader_id=complained_leader_id,
            new_leader_id=new_leader_id,
            message="Announce New Leader"
        )

        # new_leader_peer = self.get_peer(new_leader_id)

        # Announce New Leader to Radio station
        try:
            if ObjectManager().peer_service.stub_to_radiostation is not None:
                ObjectManager().peer_service.stub_to_radiostation.call("AnnounceNewLeader", announce_message)
        except Exception as e:
            logging.debug("in RS there is no peer_service....")

        if is_broadcast is True:
            for peer_id in list(self.peer_list[conf.ALL_GROUP_ID]):
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
                    stub_manager.call("AnnounceNewPeer", peer_request, is_stub_reuse=False)
            except Exception as e:
                logging.warning("gRPC Exception: " + str(e))
                logging.debug("No response target: " + str(peer_each.target))

    def complain_leader(self, group_id=conf.ALL_GROUP_ID, is_announce=False):
        """When current leader is offline, Find last height alive peer and set as a new leader.

        :param complain_peer:
        :param group_id:
        :param is_announce:
        :return:
        """
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
            stub_manager = self.get_peer_stub_manager(peer_each, group_id)
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

        return most_height_peer

    def check_peer_status(self, group_id=conf.ALL_GROUP_ID):
        delete_peer_list = []
        alive_peer_last = None
        check_leader_peer_count = 0
        for peer_id in list(self.peer_list[group_id]):
            peer_each = self.peer_list[group_id][peer_id]
            stub_manager = self.get_peer_stub_manager(peer_each, group_id)
            try:
                response = stub_manager.call("GetStatus", loopchain_pb2.StatusRequest(request=""), is_stub_reuse=True)
                if response is None:
                    raise Exception
                peer_each.status = PeerStatus.connected
                peer_status = json.loads(response.status)
                # logging.debug(f"Check Peer Status ({peer_status['peer_type']})")
                if peer_status["peer_type"] == "1":
                    check_leader_peer_count += 1
                alive_peer_last = peer_each
            except Exception as e:
                logging.warning("there is disconnected peer peer_id(" + peer_each.peer_id +
                                ") gRPC Exception: " + str(e))
                peer_each.status = PeerStatus.disconnected
                logging.debug(f"diff mins {util.datetime_diff_in_mins(peer_each.status_update_time)}")
                # if util.datetime_diff_in_mins(peer_each.status_update_time) >= conf.TIMEOUT_PEER_REMOVE_IN_LIST:
                #     logging.debug(f"peer status update time: {peer_each.status_update_time}")
                #     logging.debug(f"this peer will remove {peer_each.peer_id}")
                #     self.remove_peer(peer_each.peer_id, peer_each.group_id)
                #     delete_peer_list.append(peer_each)

        logging.debug(f"Leader Peer Count: ({check_leader_peer_count})")
        if check_leader_peer_count != 1:
            # reset network leader by RS
            if alive_peer_last is not None:
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

    def __init_peer_group(self, group_id):
        if group_id not in self.peer_list.keys():
            logging.debug("init group: " + str(group_id))
            self.peer_list[group_id] = {}
            self.peer_order_list[group_id] = {}
            self.peer_leader[group_id] = 0

        if group_id not in self.peer_stub_managers.keys():
            # peer_stub_managers 는 다른 data 와 생성 경로가 다르므로 별도로 체크한다.
            self.peer_stub_managers[group_id] = {}

    def __make_peer_order(self, peer):
        """소속된 그룹과 상관없이 전체 peer 가 순서에 대한 order 값을 가진다.
        이 과정은 중복된 order 발급을 방지하기 위하여 atomic 하여야 한다.

        :param peer:
        :return:
        """

        # TODO peer order 발급 과정은 thread safe 하여야 한다. 임시로 적용. Thread 동작 관계는 추후 검토 필요.
        lock = threading.Lock()
        lock.acquire()

        last_order = 0
        # logging.debug("Peer List is: " + str(self.peer_list))
        # logging.debug("Peer List of peer group: " + str(self.peer_list[peer.group_id]))

        # 기존에 등록된 peer_id 는 같은 order 를 재사용한다.
        if peer.peer_id in self.peer_list[peer.group_id]:
            return self.peer_list[peer.group_id][peer.peer_id].order

        for group_id in self.peer_list.keys():
            for peer_id in self.peer_list[group_id]:
                peer_each = self.peer_list[group_id][peer_id]
                logging.debug("peer each: " + str(peer_each))
                last_order = [last_order, peer_each.order][last_order < peer_each.order]

        last_order += 1
        lock.release()

        return last_order

    def get_peer(self, peer_id, group_id=conf.ALL_GROUP_ID):
        """peer_id 에 해당하는 peer 를 찾는다. group_id 가 주어지면 그룹내에서 검색하고
        없으면 전체에서 검색한다.

        :param peer_id:
        :param group_id:
        :return:
        """

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
        if group_id is None:
            group_id = conf.ALL_GROUP_ID
        try:
            remove_peer = self.peer_list[group_id].pop(peer_id)
            if group_id != conf.ALL_GROUP_ID:
                self.peer_list[conf.ALL_GROUP_ID].pop(peer_id)
            logging.debug("remove_peer: " + str(remove_peer.order))

            if remove_peer.order in self.peer_order_list[group_id].keys():
                del self.peer_order_list[group_id][remove_peer.order]
            if peer_id in self.peer_stub_managers[group_id].keys():
                del self.peer_stub_managers[group_id][peer_id]

            if remove_peer.order in self.peer_order_list[conf.ALL_GROUP_ID].keys():
                del self.peer_order_list[conf.ALL_GROUP_ID][remove_peer.order]
            if peer_id in self.peer_stub_managers[conf.ALL_GROUP_ID].keys():
                del self.peer_stub_managers[conf.ALL_GROUP_ID][peer_id]

            return True
        except KeyError:
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

    def get_IP_of_peers_in_group(self, group_id=conf.ALL_GROUP_ID, status=None):
        # TODO 기존 구현 호환용, 모든 코드에서 PeerManager 를 기준으로 재작성 필요함, 기존 코드는 배려하지 말고 리팩토링으로 개선할 것
        """group_id에 해당하는 peer들의 IP목록을 넘겨준다

        :param group_id: group의 ID.
        :param status: peer online status
        :return: group_id에 해당하는 peer들의 IP들의 list. group_id가 잘못되면 빈 list를 돌려준다.
        """
        ip_list = []
        for peer_id in self.peer_list[group_id]:
            peer_each = self.peer_list[group_id][peer_id]
            if status is None or status == peer_each.status:
                ip_list.append(str(peer_each.order)+":"+peer_each.target)

        return ip_list
