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
"""A management class for peer and channel list."""

from loopchain.blockchain import *


class AdminManager:
    """Radiostation 내에서 Channel 정보와 Peer 정보를 관리한다."""

    def __init__(self, level_db_identity):
        # self.__level_db = None
        # self.__level_db_path = ""
        # self.__level_db, self.__level_db_path = util.init_level_db(f"{level_db_identity}_admin")

        self.__json_data = None
        self.load_json_data(conf.CHANNEL_MANAGE_DATA_PATH)

    def load_json_data(self, channel_manage_data_path):
        try:
            logging.debug(f"try to load channel management data from json file ({channel_manage_data_path})")
            with open(channel_manage_data_path) as file:
                self.__json_data = json.load(file)
                logging.info(f"loading channel info : {self.json_data}")
        except Exception as e:
            util.exit_and_msg(f"cannot open json file in ({channel_manage_data_path}): {e}")

    @property
    def json_data(self) -> dict:
        return self.__json_data

    def get_channel_list(self) -> list:
        return list(self.json_data)

    def save_channel_manage_data(self, updated_data):
        # TODO reload!

        with open(conf.CHANNEL_MANAGE_DATA_PATH, 'w') as f:
            json.dump(updated_data, f, indent=2)

        self.load_json_data(channel_manage_data_path=conf.CHANNEL_MANAGE_DATA_PATH)

    def get_all_channel_info(self) -> str:
        """get channel info

        :return:
        """
        all_channel_info = json.dumps(self.json_data)

        return all_channel_info

    def get_score_package(self, channel):
        """load score packages in loopchain

        :return:
        """
        # TODO score packages를 로드한다.
        pass

    def get_channel_infos_by_peer_target(self, peer_target) -> str:
        """get channel infos by peer target

        :param peer_target:
        :return:
        """
        channel_list = []
        filtered_channel = {}
        dict_data = self.json_data

        if conf.ENABLE_CHANNEL_AUTH:
            for key, value in dict_data.items():
                target_list = value["peers"]
                for each_target in target_list:
                    if peer_target == each_target["peer_target"]:
                        channel_list.append(key)
            for each_channel in channel_list:
                filtered_channel[each_channel] = dict_data[each_channel]
            channel_infos = json.dumps(filtered_channel)
        else:
            channel_infos = self.get_all_channel_info()

        return channel_infos

    def add_channel(self, new_channel):
        """add new channel

        :param new_channel:
        :return:
        """
        loaded_data = self.json_data
        channel_list = self.get_channel_list()
        if new_channel not in channel_list:
            print(f"Please enter the name of score_package you want to add:")
            score_package_input = input(" >>  ")
            loaded_data[new_channel] = {"score_package": score_package_input}
            logging.info(f"result for adding new channel: {loaded_data}")
        else:
            logging.warning(f"channel: {new_channel} already exists.")

        self.save_channel_manage_data(loaded_data)

    def ui_add_peer_target(self, new_peer_target):
        """

        :param new_peer_target:
        :return:
        """
        loaded_data = self.json_data
        channel_list = self.get_channel_list()
        i = 0
        while i < len(channel_list):
            peer_target_list = loaded_data[channel_list[i]]["peers"]
            print(f"Do you want to add new peer to channel: {channel_list[i]}? Y/n")
            choice = input(" >>  ")
            self.add_peer_target(choice, new_peer_target, peer_target_list, i)
            i += 1

        self.save_channel_manage_data(loaded_data)

    def add_peer_target(self, choice, new_peer_target, peer_target_list, i):
        loaded_data = self.json_data
        channel_list = self.get_channel_list()
        if choice == 'Y' or choice == 'y':
            if new_peer_target not in [dict['peer_target'] for dict in peer_target_list]:
                peer_target_list.append({'peer_target': new_peer_target})
                logging.info(f"result for adding new peer target: {loaded_data}")
            else:
                logging.warning(f"peer_target: {new_peer_target} is already in channel: {channel_list[i]}")
        elif choice == 'n':
            pass
        return loaded_data
