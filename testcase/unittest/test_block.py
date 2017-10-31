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
from loopchain import configure as conf
from loopchain.baseservice import PeerInfo, PeerStatus, PeerObject, ObjectManager

sys.path.append('../')
from loopchain.blockchain import Block, BlockInValidError

util.set_log_level_debug()


class TestBlock(unittest.TestCase):
    __peer_id = 'aaa'

    def setUp(self):
        test_util.print_testname(self._testMethodName)
        self.__peer_auth = test_util.create_peer_auth()

        peer_service_mock = Mock()
        peer_service_mock.peer_manager = Mock()
        mock_info = PeerInfo(peer_id=self.__peer_id, group_id='a', target="192.0.0.1:1234", status=PeerStatus.unknown,
                             cert=self.__peer_auth.get_public_der(), order=0)
        mock_peer_object = PeerObject(mock_info)

        def get_leader_object():
            return mock_peer_object

        peer_service_mock.peer_manager.get_leader_object = get_leader_object
        ObjectManager().peer_service = peer_service_mock

    def tearDown(self):
        ObjectManager().peer_service = None

    def __generate_block_data(self) -> Block:
        """ block data generate
        :return: unsigned block
        """
        genesis = Block(channel_name="test_channel")
        genesis.generate_block()
        # Block 생성
        block = Block(channel_name=conf.LOOPCHAIN_DEFAULT_CHANNEL)
        # Transaction(s) 추가
        for x in range(0, 10):
            block.put_transaction(test_util.create_basic_tx(self.__peer_id, self.__peer_auth))

        # Hash 생성 이 작업까지 끝내고 나서 Block을 peer에 보낸다
        block.generate_block(genesis)
        return block

    def __generate_block(self) -> Block:
        """ block data generate, add sign
        :return: signed block
        """
        block = self.__generate_block_data()
        block.sign(self.__peer_auth)
        return block

    def __generate_invalid_block(self) -> Block:
        """ create invalid signature block
        :return: invalid signature block
        """
        block = self.__generate_block_data()
        block._Block__signature = b'invalid signature '
        return block

    def test_put_transaction(self):
        """
        Block 에 여러 개 transaction 들을 넣는 것을 test.
        """
        block = Block(channel_name=conf.LOOPCHAIN_DEFAULT_CHANNEL)
        tx_list = []
        tx_size = 10
        for x in range(0, tx_size):
            tx = test_util.create_basic_tx(self.__peer_id, self.__peer_auth)
            tx2 = test_util.create_basic_tx(self.__peer_id, self.__peer_auth)
            tx_list.append(tx2)
            self.assertNotEqual(tx.tx_hash, "", "트랜잭션 생성 실패")
            self.assertTrue(block.put_transaction(tx), "Block에 트랜잭션 추가 실패")
        self.assertTrue(block.put_transaction(tx_list), "Block에 여러 트랜잭션 추가 실패")
        self.assertEqual(len(block.confirmed_transaction_list), tx_size*2, "트랜잭션 사이즈 확인 실패")

    # TODO block validate 에 peer_service 정보가 필요해짐, 테스트 수정 필요
    @unittest.skip
    def test_validate_block(self):
        """ GIVEN correct block and invalid signature block
        WHEN validate two block
        THEN correct block validate return True, invalid block raise exception
        """
        # GIVEN
        # create correct block
        block = self.__generate_block()
        # WHEN THEN
        self.assertTrue(Block.validate(block), "Fail to validate block!")

        # GIVEN
        # create invalid block
        invalid_signature_block = self.__generate_invalid_block()

        # WHEN THEN
        with self.assertRaises(BlockInValidError):
            Block.validate(invalid_signature_block)

    def test_transaction_merkle_tree_validate_block(self):
        """
        머클트리 검증
        """
        # 블럭을 검증 - 모든 머클트리의 내용 검증
        block = self.__generate_block()
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
        block = self.__generate_block()
        test_dmp = block.serialize_block()
        block2 = Block(channel_name=conf.LOOPCHAIN_DEFAULT_CHANNEL)
        block2.deserialize_block(test_dmp)
        logging.debug("serialize block hash : %s , deserialize block hash %s", block.merkle_tree_root_hash, block2.merkle_tree_root_hash)
        self.assertEqual(block.merkle_tree_root_hash, block2.merkle_tree_root_hash, "블럭이 같지 않습니다 ")


class Mock:
    pass


if __name__ == '__main__':
    unittest.main()
