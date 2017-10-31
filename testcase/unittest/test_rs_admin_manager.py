#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
"""Test Radiostation Admin Manager"""
import unittest
import json

import os

import loopchain.utils as util
from loopchain.radiostation import AdminManager
from loopchain import configure as conf

util.set_log_level_debug()


class TestRSAdminManager(unittest.TestCase):

    def test_get_channel_info_by_peer_target(self):
        # GIVEN
        default_CHANNEL_MANAGE_DATA_PATH = conf.CHANNEL_MANAGE_DATA_PATH
        default_ENABLE_CHANNEL_AUTH = conf.ENABLE_CHANNEL_AUTH
        conf.CHANNEL_MANAGE_DATA_PATH = os.path.join(conf.LOOPCHAIN_ROOT_PATH,
                                                     "testcase/unittest/channel_manage_data_for_test.json")
        conf.ENABLE_CHANNEL_AUTH = True

        peer_target1 = '111.123.123.123:7100'
        peer_target2 = '222.123.123.123:7200'
        peer_target3 = '333.123.123.123:7300'
        peer_target4 = '444.123.123.123:7400'

        channel1 = 'kofia_certificate'
        channel2 = 'kofia_fine'

        # WHEN
        channel_infos1 = json.loads(AdminManager("station").get_channel_infos_by_peer_target(peer_target1))
        channel_infos2 = json.loads(AdminManager("station").get_channel_infos_by_peer_target(peer_target2))
        channel_infos3 = json.loads(AdminManager("station").get_channel_infos_by_peer_target(peer_target3))
        channel_infos4 = json.loads(AdminManager("station").get_channel_infos_by_peer_target(peer_target4))

        # THEN
        self.assertEqual(list(channel_infos1.keys()), [channel1, channel2])
        self.assertEqual(list(channel_infos2.keys()), [channel1])
        self.assertEqual(list(channel_infos3.keys()), [channel2])
        self.assertEqual(list(channel_infos4.keys()), [])

        # CLEAR
        conf.CHANNEL_MANAGE_DATA_PATH = default_CHANNEL_MANAGE_DATA_PATH
        conf.ENABLE_CHANNEL_AUTH = default_ENABLE_CHANNEL_AUTH

    def test_get_all_channel_info(self):
        # GIVEN
        default_CHANNEL_MANAGE_DATA_PATH = conf.CHANNEL_MANAGE_DATA_PATH
        conf.CHANNEL_MANAGE_DATA_PATH = os.path.join(conf.LOOPCHAIN_ROOT_PATH,
                                                     "testcase/unittest/channel_manage_data_for_test.json")

        # WHEN
        all_channel_info = AdminManager("station").get_all_channel_info()

        # THEN
        self.assertTrue(isinstance(all_channel_info, str))

        # CLEAR
        conf.CHANNEL_MANAGE_DATA_PATH = default_CHANNEL_MANAGE_DATA_PATH

    def test_add_peer_target(self):
        # GIVEN
        default_CHANNEL_MANAGE_DATA_PATH = conf.CHANNEL_MANAGE_DATA_PATH
        conf.CHANNEL_MANAGE_DATA_PATH = os.path.join(conf.LOOPCHAIN_ROOT_PATH,
                                                     "testcase/unittest/channel_manage_data_for_test.json")
        choice = 'Y'
        i = 0
        new_peer_target = '9.9.9.9:9999'
        default_data = AdminManager("station").json_data
        channel_list = AdminManager("station").get_channel_list()
        peer_target_list = default_data[channel_list[0]]["peers"]

        # WHEN
        modified_data = AdminManager("station").add_peer_target(choice, new_peer_target, peer_target_list, i)

        # THEN
        self.assertNotEqual(default_data, modified_data)

        # CLEAR
        conf.CHANNEL_MANAGE_DATA_PATH = default_CHANNEL_MANAGE_DATA_PATH


if __name__ == '__main__':
    unittest.main()
