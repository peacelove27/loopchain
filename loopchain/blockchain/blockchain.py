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
"""Block chain class with authorized blocks only"""

import json
import leveldb

from loopchain import configure as conf
from loopchain.baseservice import ObjectManager
from loopchain.baseservice.SingletonMetaClass import *
from loopchain.blockchain import BlockStatus, Block
from loopchain.blockchain.exception import *
from loopchain.blockchain.score_base import *
from loopchain.protos import message_code
from loopchain.scoreservice import ScoreResponse


class BlockChain(metaclass=SingletonMetaClass):
    """인증된 Block들만 가지고 있는 Blockchain.
    """
    block_height = 0
    last_block = None
    unconfirmed_block = None

    UNCONFIRM_BLOCK_KEY = b'UNCONFIRM_BLOCK'
    LAST_BLOCK_KEY = b'last_block_key'
    BLOCK_HEIGHT_KEY = b'block_height_key'

    def __init__(self, blockchain_db=None):
        # block db has [ block_hash - block | block_height - block_hash | BlockChain.LAST_BLOCK_KEY - block_hash ]
        self.__confirmed_block_db = blockchain_db

        if self.__confirmed_block_db is None:
            try:
                self.__confirmed_block_db = leveldb.LevelDB(conf.DEFAULT_LEVEL_DB_PATH)
            except leveldb.LevelDBError:
                raise leveldb.LevelDBError("Fail To Create Level DB(path): " + conf.DEFAULT_LEVEL_DB_PATH)

        # level DB에서 블럭을 읽어 들이며, 만약 levelDB에 블럭이 없을 경우 제네시스 블럭을 만든다
        try:
            last_block_key = self.__confirmed_block_db.Get(BlockChain.LAST_BLOCK_KEY, True)
        except KeyError:
            last_block_key = None
        logging.debug("LAST BLOCK KEY : %s", last_block_key)

        if last_block_key:
            # DB에서 마지막 블럭을 가져와서 last_block 에 바인딩
            self.last_block = Block()
            block_dump = self.__confirmed_block_db.Get(last_block_key)
            self.last_block.deserialize_block(block_dump)
            logging.debug("restore from last block hash(" + str(self.last_block.block_hash) + ")")
            logging.debug("restore from last block height(" + str(self.last_block.height) + ")")
        else:
            # 제네시스 블럭 생성
            self.__add_genesisblock()

        # 블럭의 높이는 마지막 블럭의 높이와 같음
        self.block_height = self.last_block.height

        # made block count as a leader
        self.__made_block_count = 0

    @property
    def made_block_count(self):
        return self.__made_block_count

    def increase_made_block_count(self):
        self.__made_block_count += 1

    def reset_made_block_count(self):
        self.__made_block_count = 0

    def rebuild_blocks(self):
        # Genesis block 까지 순회하며 Block 정보를 복원한다.
        logging.info("re-build blocks from DB....")

        block = Block()
        prev_block_hash = self.last_block.block_hash
        total_tx = 0

        while prev_block_hash != "":
            block_dump = self.__confirmed_block_db.Get(prev_block_hash.encode(encoding='UTF-8'))
            block.deserialize_block(block_dump)

            # Rebuild Block 코드 구간. 현재는 total_tx 만 구하고 있음
            # TODO 향후에도 rebuild_blocks가 total_tx만 구하는 경우 이 로직은 제거 하고 total_tx 는 다른 방식으로 구하도록 한다.
            # logging.debug("re-build block: " + str(block.block_hash))
            total_tx += block.confirmed_transaction_list.__len__()

            prev_block_hash = block.prev_block_hash

        logging.info("rebuilt blocks, total_tx: " + str(total_tx))
        logging.info("block hash("
                     + self.last_block.block_hash
                     + ") and height("
                     + str(self.last_block.height) + ")")

        return total_tx

    def __find_block_by_key(self, key):
        block = Block()

        try:
            block_bytes = self.__confirmed_block_db.Get(key)
            block.deserialize_block(block_bytes)
        except KeyError:
            block = None

        return block

    def find_block_by_hash(self, block_hash):
        """블럭체인 해쉬 키로 해당 블럭을 찾음

        :param block_hash: plain string,
        key 로 사용되기전에 함수내에서 encoding 되므로 미리 encoding 된 key를 parameter 로 사용해선 안된다.
        :return: None or Block
        """
        return self.__find_block_by_key(block_hash.encode(encoding='UTF-8'))

    def find_block_by_height(self, block_height):
        """find block by its height

        :param block_height: int,
        it convert to key of blockchain db in this method so don't try already converted key.
        :return None or Block
        """
        key = self.__confirmed_block_db.Get(BlockChain.BLOCK_HEIGHT_KEY +
                                            block_height.to_bytes(conf.BLOCK_HEIGHT_BYTES_LEN, byteorder='big'))
        return self.__find_block_by_key(key)

    def add_block(self, block):
        """
        인증된 블럭만 추가합니다.
        :param block: 인증완료된 추가하고자 하는 블럭
        :return:
        """

        # 인증되지 않은 블럭이면 추가 하지 않음
        try:
            block.validate()
        except Exception as e:
            logging.error(e)
            raise BlockchainError('Block is Not valid')

        if block.block_status is not BlockStatus.confirmed:
            raise BlockInValidError("미인증 블럭")
        elif self.last_block is not None and self.last_block.height > 0:
            if self.last_block.block_hash != block.prev_block_hash:
                # 마지막 블럭의 hash값이 추가되는 블럭의 prev_hash값과 다르면 추가 하지 않고 익셉션을 냅니다.
                logging.debug("self.last_block.block_hash: " + self.last_block.block_hash)
                logging.debug("block.prev_block_hash: " + block.prev_block_hash)
                raise BlockError("최종 블럭과 해쉬값이 다릅니다.")

        invoke_results = {}

        if ObjectManager().peer_service is None:
            # all results to success
            success_result = {'code': int(message_code.Response.success)}
            invoke_results = self.__create_invoke_result_specific_case(block.confirmed_transaction_list, success_result)
        else:
            try:
                invoke_results = ObjectManager().peer_service.score_invoke(block)

            except Exception as e:
                # When Grpc Connection Raise Exception
                # save all result{'code': ScoreResponse.SCORE_CONTAINER_EXCEPTION, 'message': str(e)}
                logging.error(f'Error While Invoke Score fail add block : {e}')
                score_container_exception_result = {'code': ScoreResponse.SCORE_CONTAINER_EXCEPTION, 'message': str(e)}
                invoke_results = self.__create_invoke_result_specific_case(block.confirmed_transaction_list
                                                                           , score_container_exception_result)

        self.__add_tx_to_block_db(block, invoke_results)
        self.__confirmed_block_db.Put(block.block_hash.encode(encoding='UTF-8'), block.serialize_block())
        self.__confirmed_block_db.Put(BlockChain.LAST_BLOCK_KEY, block.block_hash.encode(encoding='UTF-8'))
        self.__confirmed_block_db.Put(
            BlockChain.BLOCK_HEIGHT_KEY +
            block.height.to_bytes(conf.BLOCK_HEIGHT_BYTES_LEN, byteorder='big'),
            block.block_hash.encode(encoding='UTF-8'))

        self.last_block = block
        self.block_height = self.last_block.height

        # logging.debug("ADD BLOCK Height : %i", block.height)
        # logging.debug("ADD BLOCK Hash : %s", block.block_hash)
        # logging.debug("ADD BLOCK MERKLE TREE Hash : %s", block.merkle_tree_root_hash)
        # logging.debug("ADD BLOCK Prev Hash : %s ", block.prev_block_hash)
        logging.info("ADD BLOCK HEIGHT : %i , HASH : %s", block.height, block.block_hash)
        # 블럭의 Transaction 의 데이터를 저장 합니다.
        # Peer에서 Score를 파라미터로 넘김으로써 체인코드를 실행합니다.

        return True

    def __create_invoke_result_specific_case(self, confirmed_transaction_list, invoke_result):
        invoke_results = {}
        for tx in confirmed_transaction_list:
            invoke_results[tx.get_tx_hash()] = invoke_result
        return invoke_results

    def __add_tx_to_block_db(self, block, invoke_results):
        """block db 에 block_hash - block_object 를 저장할때, tx_hash - block_hash 를 저장한다.
        get tx by tx_hash 시 해당 block 을 효율적으로 찾기 위해서
        :param block:
        """
        # loop all tx in block
        logging.debug("try add all tx in block to block db, block hash: " + block.block_hash)

        for tx in block.confirmed_transaction_list:
            tx_hash = tx.get_tx_hash()

            invoke_result = dict()
            invoke_result = invoke_results[tx_hash]

            tx_info = dict()
            tx_info['block_hash'] = block.block_hash
            tx_info['result'] = invoke_result

            # logging.debug("tx hash: " + tx.get_tx_hash())
            self.__confirmed_block_db.Put(
                tx.get_tx_hash().encode(encoding=conf.HASH_KEY_ENCODING),
                json.dumps(tx_info).encode(encoding=conf.PEER_DATA_ENCODING))

    def find_tx_by_key(self, tx_hash_key):
        """tx 의 hash 로 저장된 tx 를 구한다.
        :param tx_hash_key: tx 의 tx_hash
        :return tx_hash_key 에 해당하는 transaction, 예외인 경우 None 을 리턴한다.
        """
        # levle db 에서 tx 가 저장된 block 의 hash 를 구한다.
        try:
            tx_info_json = self.__find_tx_info(tx_hash_key)
        except KeyError as e:
            # Client 의 잘못된 요청이 있을 수 있으므로 Warning 처리후 None 을 리턴한다.
            # 시스템 Error 로 처리하지 않는다.
            logging.warning("blockchain::find_tx_by_key KeyError: " + str(e))
            return None
        if tx_info_json is None:
            logging.warning("tx not found")
            return None
        block_key = tx_info_json['block_hash']
        logging.debug("block_key: " + str(block_key))

        # block 의 hash 로 block object 를 구한다.
        block = self.find_block_by_hash(block_key)
        logging.debug("block: " + block.block_hash)
        if block is None:
            logging.error("There is No Block, block_hash: " + block.block_hash)
            return None

        # block object 에서 저장된 tx 를 구한다.
        tx_index = block.find_transaction_index(tx_hash_key)
        logging.debug("tx_index: " + str(tx_index))
        if tx_index < 0:
            logging.error("block.find_transaction_index index error, index: " + tx_index)
            return None

        tx = block.confirmed_transaction_list[tx_index]
        logging.debug("find tx: " + tx.get_tx_hash())

        return tx

    def find_invoke_result_by_tx_hash(self, tx_hash):
        """ find invoke result matching tx_hash and return result if not in blockchain return code delay

        :param tx_hash: tx_hash
        :return: {"code" : "code", "error_message" : "`rror_message if not fail this is not exist"}
        """
        try:
            tx_info = self.__find_tx_info(tx_hash)
        except KeyError as e:
            # Client 의 잘못된 요청이 있을 수 있으므로 Warning 처리후 None 을 리턴한다.
            # 시스템 Error 로 처리하지 않는다.
            logging.warning("blockchain::find invoke_result KeyError: " + str(e))
            return {'code': ScoreResponse.NOT_INVOKED}

        return tx_info['result']

    def __find_tx_info(self, tx_hash_key):
        try:
            tx_info = self.__confirmed_block_db.Get(
                tx_hash_key.encode(encoding=conf.HASH_KEY_ENCODING))
            tx_info_json = json.loads(tx_info, encoding=conf.PEER_DATA_ENCODING)

        except UnicodeDecodeError as e:
            logging.warning("blockchain::find_tx_by_key UnicodeDecodeError: " + str(e))
            return None

        return tx_info_json

    def __add_genesisblock(self):
        """
        제네시스 블럭을 추가 합니다.
        :return:
        """
        logging.info("Make Genesis Block....")
        block = Block()
        block.block_status = BlockStatus.confirmed
        block.generate_block()
        # 제네시스 블럭을 추가 합니다.
        self.add_block(block)
        # 제네시스 블럭의 HASH 값은 af5570f5a1810b7af78caf4bc70a660f0df51e42baf91d4de5b2328de0e83dfc
        # 으로 일정 합니다.

    def add_unconfirm_block(self, unconfirmed_block):
        """
        인증되지 않은 Unconfirm블럭을 추가 합니다.
        :param unconfirmed_block: 인증되지 않은 Unconfirm블럭
        :return:인증값 : True 인증 , False 미인증
        """
        # confirm 블럭
        if (self.last_block.height + 1) != unconfirmed_block.height:
            logging.error("블럭체인의 높이가 다릅니다.")
            return False, "block_height"
        elif unconfirmed_block.prev_block_hash != self.last_block.block_hash:
            logging.error("마지막 블럭의 해쉬값이 다릅니다. %s vs %s ", unconfirmed_block.prev_block_hash, self.last_block.block_hash)
            return False, "prev_block_hash"
        elif unconfirmed_block.block_hash != unconfirmed_block.generate_block(self.last_block):
            logging.error("%s의 값이 재생성한 블럭해쉬와 같지 않습니다.", unconfirmed_block.block_hash)
            return False, "generate_block_hash"
        # Save unconfirmed_block
        self.__confirmed_block_db.Put(BlockChain.UNCONFIRM_BLOCK_KEY, unconfirmed_block.serialize_block())
        return True, "No reason"

    def confirm_block(self, confirmed_block_hash):
        """인증완료후 Block을 Confirm해 줍니다.
        :param confirmed_block_hash: 인증된 블럭의 hash
        :return: Block 에 포함된 tx 의 갯수를 리턴한다.
        """
        logging.debug("BlockChain::confirm_block")

        try:
            unconfirmed_block_byte = self.__confirmed_block_db.Get(BlockChain.UNCONFIRM_BLOCK_KEY)
        except KeyError:
            except_msg = f"there is no unconfirmed block in this peer block_hash({confirmed_block_hash})"
            logging.warning(except_msg)
            raise BlockchainError(except_msg)

        unconfirmed_block = Block()
        unconfirmed_block.deserialize_block(unconfirmed_block_byte)

        if unconfirmed_block.block_hash != confirmed_block_hash:
            logging.warning("It's not possible to add block while check block hash is fail-")
            raise BlockchainError('확인하는 블럭 해쉬 값이 다릅니다.')

        logging.debug("unconfirmed_block.block_hash: " + unconfirmed_block.block_hash)
        logging.debug("confirmed_block_hash: " + confirmed_block_hash)
        logging.debug("unconfirmed_block.prev_block_hash: " + unconfirmed_block.prev_block_hash)

        unconfirmed_block.block_status = BlockStatus.confirmed
        # Block Validate and save Block
        self.add_block(unconfirmed_block)
        self.__confirmed_block_db.Delete(BlockChain.UNCONFIRM_BLOCK_KEY)

        return unconfirmed_block.confirmed_transaction_list.__len__()
