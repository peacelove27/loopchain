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
"""Test block manager"""

import time
import unittest

import loopchain.utils as util
import testcase.unittest.test_util as test_util
from loopchain.blockchain import Transaction
from loopchain.peer import BlockManager

util.set_log_level_debug()


class TestBlockManager(unittest.TestCase):

    def setUp(self):
        test_util.print_testname(self._testMethodName)

    def tearDown(self):
        pass

    # TODO BlockManager 의 동작이 CommonService 와 연동하는 형태로 변경되어 아래 테스트는 수정되어야 한다.
    # def test_add_tx(self):
    #     block_manager = BlockManager(None)
    #     block_manager.start()
    #
    #     for data in range(5):
    #         tx = Transaction()
    #         tx.put_data("TEST"+str(data))
    #         block_manager.add_tx(tx)
    #
    #     time.sleep(2)
    #
    #     for data in range(5, 10):
    #         tx = Transaction()
    #         tx.put_data("TEST"+str(data))
    #         block_manager.add_tx(tx)
    #
    #     time.sleep(2)
    #
    #     # 블럭매니저의 트랜잭션 개수는 10개임
    #     self.assertEqual(10, block_manager.get_count_of_unconfirmed_tx(), "Block Manager Not Running for unconfirmed tx")
    #
    #     block_manager.stop()
