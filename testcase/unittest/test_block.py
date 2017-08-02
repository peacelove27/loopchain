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
"""Test Block functions"""

import logging
import sys
import unittest

import loopchain.utils as util
import testcase.unittest.test_util as test_util

sys.path.append('../')
from loopchain.blockchain import Block
from loopchain.blockchain import Transaction

util.set_log_level_debug()


class TestBlock(unittest.TestCase):
    def setUp(self):
        test_util.print_testname(self._testMethodName)

    def generate_block(self):
        """
        블럭 생성기
        :return: 임의생성블럭
        """
        genesis = Block()
        genesis.generate_block()
        # Block 생성
        block = Block()
        # Transaction(s) 추가
        for x in range(0, 10):
            tx = Transaction()
            tx.put_data("{args:[]}")
            block.put_transaction(tx)

        # Hash 생성 이 작업까지 끝내고 나서 Block을 peer에 보낸다
        block.generate_block(genesis)
        return block

    def test_put_transaction(self):
        """
        Block 에 여러 개 transaction 들을 넣는 것을 test.
        """
        block = Block()
        tx_list = []
        tx_size = 10
        for x in range(0, tx_size):
            tx = Transaction()
            tx2 = Transaction()
            hashed_value = tx.put_data("{args:[]}")
            tx2.put_data("{args:[]}")
            tx_list.append(tx2)
            self.assertNotEqual(hashed_value, "", "트랜잭션 생성 실패")
            self.assertTrue(block.put_transaction(tx), "Block에 트랜잭션 추가 실패")
        self.assertTrue(block.put_transaction(tx_list), "Block에 여러 트랜잭션 추가 실패")
        self.assertEqual(len(block.confirmed_transaction_list), tx_size*2, "트랜잭션 사이즈 확인 실패")

    def test_validate_block(self):
        """
        블럭 검증
        """
        # Block 생성
        block = self.generate_block()
        # 생성 블럭 Validation
        self.assertTrue(block.validate(), "Fail to validate block!")

    def test_transaction_merkle_tree_validate_block(self):
        """
        머클트리 검증
        """
        # 블럭을 검증 - 모든 머클트리의 내용 검증
        block = self.generate_block()
        mk_result = True
        for tx in block.confirmed_transaction_list:
            # FIND tx index
            idx = block.confirmed_transaction_list.index(tx)
            sm_result = Block.merkle_path(block, idx)
            mk_result &= sm_result
            # logging.debug("Transaction %i th is %s (%s)", idx, sm_result, tx.get_tx_hash())
        # logging.debug("block mekletree : %s ", block.merkle_tree)
        self.assertTrue(mk_result, "머클트리검증 실패")

    def test_serialize_and_deserialize(self):
        """
        블럭 serialize and deserialize 테스트
        """
        block = self.generate_block()
        test_dmp = block.serialize_block()
        block2 = Block()
        block2.deserialize_block(test_dmp)
        logging.debug("serialize block hash : %s , deserialize block hash %s", block.merkle_tree_root_hash, block2.merkle_tree_root_hash)
        self.assertEqual(block.merkle_tree_root_hash, block2.merkle_tree_root_hash, "블럭이 같지 않습니다 ")


if __name__ == '__main__':
    unittest.main()
