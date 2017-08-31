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
"""Test block chain class"""

import leveldb
import logging
import random
import unittest

import loopchain.utils as util
import testcase.unittest.test_util as test_util
from loopchain.blockchain import Block
from loopchain.blockchain import BlockChain, BlockStatus
from loopchain.blockchain import Transaction
from loopchain.protos import message_code

util.set_log_level_debug()


class TestBlockChain(unittest.TestCase):
    chain = None
    db_name = 'blockchain_db'

    def setUp(self):
        test_util.print_testname(self._testMethodName)
        # BlockChain 을 만듬
        test_db = test_util.make_level_db(self.db_name)
        self.assertIsNotNone(test_db, "DB생성 불가")
        self.chain = BlockChain(test_db)

        test_util.print_testname(self._testMethodName)

    def tearDown(self):
        # Blockchain을 삭제
        leveldb.DestroyDB(self.db_name)

    def generate_test_block(self):
        """
        임시 블럭 생성하는 메소드
        :return: 임시 블럭
        """

        block = Block()
        for x in range(0, 10):
            tx = Transaction()
            hashed_value = tx.put_data("{args:[]}")
            self.assertNotEqual(hashed_value, "", "트랜잭션 생성 실패")
            self.assertTrue(block.put_transaction(tx), "Block에 트랜잭션 추가 실패")

        return block

    def test_genesis_block_by_key(self):
        """
        제네시스 블럭을 찾는다
        """
        # 키를 통하여 블럭을 찾는다
        last_block_hash = self.chain.last_block.block_hash
        logging.debug("LAST BLOCK : %s", last_block_hash)
        last_block = self.chain.find_block_by_hash(last_block_hash)
        self.assertIsNotNone(last_block, "제네시스 블럭을 가져올 수 없습니다.")

    def test_find_do_not_exist_block(self):
        """
        블럭체인에 없는 블럭을 찾는다
        """
        none_block_key = "bf5570f5a1810b7af78caf4bc70a660f0df51e42baf91d4de5b2328de0e83dfc"
        none_block = self.chain.find_block_by_hash(none_block_key)
        self.assertIsNot(none_block, "존재하지 않는 블럭이 출력되었습니다.")

    def test_find_block_by_height(self):
        # GIVEN
        size = 10
        find_block_index = int(size*random.random())
        find_block_height = 0
        find_block_hash = None
        for x in range(size):
            last_block = self.chain.last_block
            n_block = self.generate_test_block()
            n_block.generate_block(last_block)
            n_block.block_status = BlockStatus.confirmed
            if find_block_index == x:
                find_block_hash = n_block.block_hash
                find_block_height = n_block.height
            self.chain.add_block(n_block)

        logging.debug("find block hash : %s ", find_block_hash)
        logging.debug("find block height : %d ", find_block_height)

        # WHEN
        find_block_by_hash = self.chain.find_block_by_hash(find_block_hash)
        find_block_by_height = self.chain.find_block_by_height(find_block_height)

        # THEN
        self.assertEqual(find_block_by_hash.block_hash, find_block_by_height.block_hash)

    def test_add_some_block_and_find_by_key(self):
        """몇개의 블럭을 추가한 후 임의의 블럭을 찾는다
        """
        # GIVEN
        size = 10
        find_block_index = int(size*random.random())
        find_block_hash = None
        for x in range(size):
            last_block = self.chain.last_block
            n_block = self.generate_test_block()
            n_block.generate_block(last_block)
            n_block.block_status = BlockStatus.confirmed
            if find_block_index == x:
                find_block_hash = n_block.block_hash
            logging.debug("new block height : %i", n_block.height)
            self.chain.add_block(n_block)

        logging.debug("find block index : %i ", find_block_index)
        logging.debug("find block hash : %s ", find_block_hash)

        # WHEN
        find_block = self.chain.find_block_by_hash(find_block_hash)
        logging.debug("find block height : %i", find_block.height)

        # THEN
        self.assertEqual(find_block_hash, find_block.block_hash)

    def test_add_and_find_tx(self):
        """block db 에 block_hash - block_object 를 저장할때, tx_hash - tx_object 도 저장한다.
        get tx by tx_hash 시 해당 block 을 효율적으로 찾기 위해서
        """
        tx = self.__add_single_tx_to_block_return_tx_with_test()

        saved_tx = self.chain.find_tx_by_key(tx.get_tx_hash())
        logging.debug("saved_tx: " + str(saved_tx.get_tx_hash()))

        self.assertEqual(tx.get_tx_hash(), saved_tx.get_tx_hash(), "Fail Find Transaction")

    def test_add_and_verify_results(self):
        """invoke_result = "{"code" : "invoke_result_code" , "error_message": "message" }"

        """
        tx = self.__add_single_tx_to_block_return_tx_with_test()

        invoke_result = self.chain.find_invoke_result_by_tx_hash(tx.get_tx_hash())
        self.assertEqual(invoke_result['code'], message_code.Response.success)

    def __add_single_tx_to_block_return_tx_with_test(self):
        last_block = self.chain.last_block
        block = Block()
        tx = Transaction()
        hashed_value = tx.put_data("1234")
        self.assertNotEqual(hashed_value, "", "트랜잭션 생성 실패")
        self.assertTrue(block.put_transaction(tx), "Block에 트랜잭션 추가 실패")

        logging.debug("tx_hash: " + tx.get_tx_hash())

        block.generate_block(last_block)
        block.block_status = BlockStatus.confirmed
        # add_block include __add_tx_to_block_db what we want to test
        self.assertTrue(self.chain.add_block(block),
                        "Fail Add Block to BlockChain in test_add_tx_to_block_db")
        return tx

    def test_unicode_decode_error(self):
        """ Transaction hash 는 UTF-8 인코딩이나 block hash 값은 sha256 hex byte array 이므로 인코딩 에러가 발생함
        """

        last_block = self.chain.last_block
        unexpected_transaction = self.chain.find_tx_by_key(last_block.block_hash)
        self.assertIsNone(unexpected_transaction, "unexpected_transaction is not None")

    def test_blockchain_is_singleton(self):
        x = BlockChain(test_util.make_level_db())
        y = BlockChain(test_util.make_level_db())

        self.assertTrue((x is y))

if __name__ == '__main__':
    unittest.main()
