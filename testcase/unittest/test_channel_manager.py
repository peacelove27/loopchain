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
"""Test Channel Manager for new functions not duplicated another tests"""
import logging
import unittest

import os

import loopchain.utils as util
import testcase.unittest.test_util as test_util
from loopchain import configure as conf
from loopchain.baseservice import StubManager
from loopchain.peer import ChannelManager
from loopchain.protos import message_code

util.set_log_level_debug()


class MockCommonService:
    peer_id = 'asdsadsadsadsadsad'


class TestChannelManager(unittest.TestCase):

    __channel_manager = None

    def setUp(self):
        test_util.print_testname(self._testMethodName)

    def tearDown(self):
        self.__channel_manager.stop_score_containers()
        conf.DEFAULT_SCORE_REPOSITORY_PATH = os.path.join(conf.LOOPCHAIN_ROOT_PATH, 'score')

    def test_load_score_containers(self):
        """GIVEN default_score_package, and test_score_package different value,
        conf.PORT_DIFF_TEST_SCORE_CONTAINER, new ChannelManager, peer_port for channel manager
        WHEN ChannelManager.load_score_containers
        THEN score_info, stub_to_score_container, score_process
        """
        # GIVEN
        conf.DEFAULT_SCORE_REPOSITORY_PATH = os.path.join(conf.LOOPCHAIN_ROOT_PATH, 'resources/test_score_repository')
        default_score_package = 'loopchain/default'
        test_score_package = 'develop/test_score'

        self.__channel_manager = ChannelManager(MockCommonService())

        peer_port = 7100

        # WHEN
        default_score_port = peer_port + 2000
        self.__channel_manager.load_score_container_each(channel_name=conf.LOOPCHAIN_DEFAULT_CHANNEL,
                                                  score_package=default_score_package,
                                                  container_port=default_score_port,
                                                  peer_target='localhost:7100')
        test_score_port = peer_port + 3000
        self.__channel_manager.load_score_container_each(channel_name=conf.LOOPCHAIN_TEST_CHANNEL,
                                                  score_package=test_score_package,
                                                  container_port=test_score_port,
                                                  peer_target='localhost:7100')

        # THEN
        # stub port must setting port
        default_score_stub: StubManager = self.__channel_manager.get_score_container_stub(conf.LOOPCHAIN_DEFAULT_CHANNEL)
        test_score_stub: StubManager = self.__channel_manager.get_score_container_stub(conf.LOOPCHAIN_TEST_CHANNEL)
        self.assertEqual(default_score_stub.target.split(":")[-1], str(default_score_port))
        self.assertEqual(test_score_stub.target.split(":")[-1], str(test_score_port))

        # score_info
        default_score_info: dict = self.__channel_manager.get_score_info(conf.LOOPCHAIN_DEFAULT_CHANNEL)
        test_score_info: dict = self.__channel_manager.get_score_info(conf.LOOPCHAIN_TEST_CHANNEL)

        logging.debug(f'default_score_info : {default_score_info}')
        logging.debug(f'test_score_info : {test_score_info}')

        self.assertEqual(default_score_info[message_code.MetaParams.ScoreInfo.score_id], default_score_package)
        self.assertEqual(test_score_info[message_code.MetaParams.ScoreInfo.score_id], test_score_package)

        # AFTER



if __name__ == '__main__':
    unittest.main()
