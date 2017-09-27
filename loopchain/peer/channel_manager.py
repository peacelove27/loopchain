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
""" A class for Manage Channels """

import leveldb
import logging
import pickle

import loopchain.utils as util
from loopchain import configure as conf
from loopchain.baseservice import PeerManager
from loopchain.container import CommonService
from loopchain.peer import BlockManager


class ChannelManager:
    """어떤 Peer가 loopchain network 에 접속할 권한을 가지고 있는지 어떤 채널에 속할 권한을 가지고 있는지 관리한다.
    이 데이터는 RS Admin site 를 통해서 설정될 수 있으며, 이중화 또는 3중화된 복수의 RS가 존재할 경우 이 데이터를 동기되어야한다.
    key 생성을 위한 난수표는 메모리상에만 존재해야 하며 나머지 데이터는 level DB 를 사용한다.

    """

    # TODO 현재는 multi channel 구현을 위해서 임의로 두개의 채널이 존재하며 모든 peer 에게 권한이 허용 되어 있도록 가정한다.

    def __init__(self, common_service: CommonService, level_db_identity="station"):
        self.__common_service = common_service
        self.__level_db_identity = level_db_identity
        self.__peer_managers = {}  # key(channel_name):value(peer_manager)
        self.__block_managers = {}  # key(channel_name):value(block_manager), This available only peer
        self.__load_peer_managers()
        self.load_block_manager_each(channel=conf.LOOPCHAIN_DEFAULT_CHANNEL)

    def load_block_managers(self, peer_id, is_include_default=False):
        """load block managers
        caution! this is called after connect to all channels (function of peer service)

        :return:
        """
        for channel in self.__peer_managers:
            if is_include_default or channel != conf.LOOPCHAIN_DEFAULT_CHANNEL:
                self.load_block_manager_each(peer_id=peer_id, channel=channel)

    def load_block_manager_each(self, peer_id=None, channel=conf.LOOPCHAIN_DEFAULT_CHANNEL):
        logging.debug(f"load_block_manager_each channel({channel})")
        try:
            self.__block_managers[channel] = BlockManager(
                common_service=self.__common_service,
                peer_id=peer_id,
                channel_name=channel,
                level_db_identity=self.__level_db_identity
            )
        except leveldb.LevelDBError as e:
            util.exit_and_msg("LevelDBError(" + str(e) + ")")

    def get_channel_list(self) -> list:
        return list(self.__peer_managers)

    def get_peer_manager(self, channel_name=conf.LOOPCHAIN_DEFAULT_CHANNEL) -> PeerManager:
        return self.__peer_managers[channel_name]

    def get_block_manager(self, channel_name=conf.LOOPCHAIN_DEFAULT_CHANNEL) -> BlockManager:
        return self.__block_managers[channel_name]

    def start_block_managers(self):
        for block_manager in self.__block_managers:
            self.__block_managers[block_manager].start()

    def stop_block_managers(self):
        for block_manager in self.__block_managers:
            self.__block_managers[block_manager].stop()

    def remove_peer(self, peer_id, group_id):
        for peer_manager in self.__peer_managers:
            self.__peer_managers[peer_manager].remove_peer(peer_id, group_id)

    def set_peer_type(self, peer_type):
        """Set peer type when peer start only

        :param peer_type:
        :return:
        """
        for block_manager in self.__block_managers:
            self.__block_managers[block_manager].set_peer_type(peer_type)

    def save_peer_manager(self, peer_manager, channel_name=conf.LOOPCHAIN_DEFAULT_CHANNEL):
        """peer_list 를 leveldb 에 저장한다.

        :param peer_manager:
        :param channel_name:
        """
        level_db_key_name = str.encode(conf.LEVEL_DB_KEY_FOR_PEER_LIST)

        try:
            dump = peer_manager.dump()
            level_db = self.__block_managers[channel_name].get_level_db()
            level_db.Put(level_db_key_name, dump)
            # 아래의 audience dump update 는 안정성에 문제를 야기한다. (원인 미파악)
            # self.update_audience(dump)
        except AttributeError as e:
            logging.warning("Fail Save Peer_list: " + str(e))

    def __load_peer_managers(self):
        # TODO make this work with db and rs admin site, but now just filled with test values
        self.__peer_managers[conf.LOOPCHAIN_DEFAULT_CHANNEL] = \
            self.__load_peer_manager_each(conf.LOOPCHAIN_DEFAULT_CHANNEL)
        self.__peer_managers[conf.LOOPCHAIN_TEST_CHANNEL] = \
            self.__load_peer_manager_each(conf.LOOPCHAIN_TEST_CHANNEL)

    def __load_peer_manager_each(self, channel_name=conf.LOOPCHAIN_DEFAULT_CHANNEL):
        """leveldb 로 부터 peer_manager 를 가져온다.

        :return: peer_manager
        """
        peer_manager = PeerManager(channel_name)

        level_db_key_name = str.encode(conf.LEVEL_DB_KEY_FOR_PEER_LIST)

        if conf.IS_LOAD_PEER_MANAGER_FROM_DB:
            try:
                level_db = self.__block_managers[channel_name].get_level_db()
                peer_list_data = pickle.loads(level_db.Get(level_db_key_name))
                peer_manager.load(peer_list_data)
                logging.debug("load peer_list_data on yours: " + peer_manager.get_peers_for_debug())
            except KeyError:
                logging.warning("There is no peer_list_data on yours")

        return peer_manager

    def authorized_channels(self, peer_id) -> list:
        authorized_channels = []

        # TODO 실제 코드는 아래와 같아야 한다.
        # rs_admin_site 를 통해 형성된 peer auth manager 에서 peer 가 속한 channel 을 구해야 한다.
        # for channel in self.__peer_managers:
        #     logging.warning(f"channel is ({channel})")
        #     peer_manager = self.__peer_managers[channel]
        #
        #     if peer_manager is not None and peer_manager.get_peer(peer_id):
        #         authorized_channels.append(channel)

        # TODO 하지만 테스트를 위해서 우선 아래와 같이 모든 채널에 권한이 있는 것으로 리턴한다.
        for channel in self.__peer_managers:
            logging.warning(f"channel is ({channel})")
            authorized_channels.append(channel)

        logging.warning(f"authorized channels ({authorized_channels})")

        return authorized_channels
