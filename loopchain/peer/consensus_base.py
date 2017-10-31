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
"""A base class of consensus for the loopchain"""

from abc import ABCMeta, abstractmethod

from loopchain.baseservice import ObjectManager
from loopchain.blockchain import *


class ConsensusBase(metaclass=ABCMeta):
    """LoopChain 의 Consensus Algorithm 을 표현하는 클래스
    """

    def __init__(self, blockmanager):
        self._made_block_count = 0
        self._block = None
        self._blockmanager = blockmanager
        self._channel_name = blockmanager.channel_name
        self._blockchain = self._blockmanager.get_blockchain()
        self._txQueue = self._blockmanager.get_tx_queue()
        self._current_vote_block_hash = ""
        self._candidate_blocks = self._blockmanager.get_candidate_blocks()
        self._gen_block()

    @abstractmethod
    def consensus(self):
        """Block Manager 의 Thread Loop 에서 호출 하는 합의 알고리즘
        """
        pass

    @property
    def block(self):
        return self._block

    @property
    def made_block_count(self):
        return self._made_block_count

    @made_block_count.setter
    def made_block_count(self, value):
        self._made_block_count = value

    def _gen_block(self):
        self._made_block_count += 1
        self._block = Block(channel_name=self._channel_name, made_block_count=self._made_block_count)

    def _stop_gen_block(self):
        self._made_block_count = 0
        self._block = None

    def _makeup_block(self):
        """Queue 에 수집된 tx 를 block 으로 만든다.
        setttings 에 정의된 조건에 따라 한번의 작업으로 여러개의 candidate_block 으로 나뉘어진 블럭을 생성할 수 있다.
        (주의! 성능상의 이유로 가능한 운행 조건에서 블럭이 나누어지지 않도록 설정하는 것이 좋다.)
        """

        # TODO: Queue에서 tx를 수집하는 동안 Peer list정보를 만나면,
        # TODO: 직전 tx까지 block을 생성하고, 다음 block으로 peerlist타입의 block을 생성한다
        tx_count = 0
        peer_manager_block = None
        while not self._txQueue.empty():
            # 수집된 tx 가 있으면 Block 에 집어 넣는다.
            tx_unloaded = self._txQueue.get()
            tx = pickle.loads(tx_unloaded)

            if isinstance(tx, Transaction):
                # logging.debug("txQueue get tx: " + tx.get_tx_hash())
                tx_count += 1
            else:
                logging.error("Load Transaction Error!")
                continue

            if tx.type is TransactionType.peer_list:
                peer_manager_block = Block(channel_name=self._channel_name)
                peer_manager_block.block_type = BlockType.peer_list
                peer_manager_block.peer_manager = tx.get_data()
                break
            elif self._block is None:
                logging.error("Leader Can't Add tx...")
            else:
                tx_confirmed = self._block.put_transaction(tx)
                # logging.debug("put transaction to block: " + str(tx_confirmed))

            # 블럭의 담기는 트랜잭션의 최대 갯수, 메시지 크기를 계속 dump 로 비교하는 것은 성능에 부담이 되므로 tx 추가시에는 갯수로만 방지한다.
            if tx_count >= conf.MAX_BLOCK_TX_NUM:
                break

        if self._block is not None and len(self._block.confirmed_transaction_list) > 0:
            # 최종 블럭 생성뒤 gRPC 메시지 사이즈를 넘게 되면 블럭을 나누어서 다시 생성하게 한다.
            block_dump = pickle.dumps(self._block)
            block_dump_size = len(block_dump)

            if block_dump_size > (conf.MAX_BLOCK_KBYTES * 1024):
                # TODO block 나누기
                divided_block = Block(channel_name=self._channel_name, is_divided_block=True)
                do_divide = False

                next_tx = (self._block.confirmed_transaction_list.pop(0), None)[
                    len(self._block.confirmed_transaction_list) == 0]
                expected_block_size = len(pickle.dumps(divided_block))

                while next_tx is not None:
                    # logging.debug("next_tx: " + str(next_tx.get_tx_hash()))
                    tx_dump = pickle.dumps(next_tx)
                    expected_block_size += len(tx_dump)

                    if expected_block_size < (conf.MAX_BLOCK_KBYTES * 1024):
                        divided_block.put_transaction(next_tx)
                        next_tx = (self._block.confirmed_transaction_list.pop(0), None)[
                            len(self._block.confirmed_transaction_list) == 0]
                        if next_tx is None:
                            do_divide = True
                    else:
                        do_divide = True

                    if do_divide:
                        # 검증 받을 블록의 hash 를 생성하고 후보로 등록한다.
                        logging.warning("Block divide, add unconfirmed block to candidate blocks")
                        divided_block.generate_block(self._candidate_blocks.get_last_block(self._blockchain))
                        self._candidate_blocks.add_unconfirmed_block(divided_block)
                        # 새로운 Block 을 생성하여 다음 tx 을 수집한다.
                        divided_block = Block(channel_name=self._channel_name, is_divided_block=True)
                        expected_block_size = len(pickle.dumps(divided_block))
                        do_divide = False

        if peer_manager_block is not None:
            peer_manager_block.generate_block(self._candidate_blocks.get_last_block(self._blockchain))
            peer_manager_block.sign(ObjectManager().peer_service.auth)

