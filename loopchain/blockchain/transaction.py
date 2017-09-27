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
"""A module about Transaction object"""

import hashlib
import collections
import logging
import struct
import time
import loopchain.utils as util
from enum import Enum
from loopchain import configure as conf
from loopchain.tools import PublicVerifierContainer


class TransactionStatus(Enum):
    unconfirmed = 1
    confirmed = 2


class TransactionType(Enum):
    general = 1
    peer_list = 2


class Transaction:
    """Transaction 거래 내용
    Peer에서 데이터를 받으면 새로운 트랜잭션을 생성하며, 생성된 트랜잭션은
    바로 BlockGenerator 에게 전달 된다
    """
    PEER_ID_KEY = 'peer_id'
    SCORE_ID_KEY = 'score_id'
    SCORE_VERSION_KEY = 'score_version'
    CHANNEL_KEY = 'channel_name'

    def __init__(self):
        # TODO Client 의 Sign이나 인증에 대한 내용을 트랜잭션에 넣어야 하지 않을까?
        self.__transaction_status = TransactionStatus.unconfirmed
        self.__transaction_type = TransactionType.general
        self.__meta = collections.OrderedDict()  # peer_id, score_id, score_ver ...
        self.__data = []
        self.__time_stamp = 0
        self.__transaction_hash = ""
        self.__public_key = b""
        self.__signature = b""

    @property
    def tx_hash(self):
        return self.__transaction_hash

    @property
    def status(self):
        return self.__transaction_status

    @status.setter
    def status(self, tx_status):
        self.__transaction_status = tx_status

    @property
    def type(self):
        return self.__transaction_type

    @type.setter
    def type(self, tx_type):
        self.__transaction_type = tx_type

    @property
    def signature(self):
        return self.__signature

    @property
    def public_key(self):
        return self.__public_key

    @property
    def meta(self):
        return self.__meta.copy()

    def put_meta(self, key, value):
        """Tx 의 meta 정보를 구성한다.
        tx 의 put_data 발생시 tx 의 hash 를 생성하게 되며 이때 meta 정보를 hash 계산에 사용하게 되므로
        meta 정보의 구성은 put_data 이전에 완료하거나 혹은 put_data 후에 meta 정보를 추가하게 된다면
        hash 를 다시 생성하여야 한다.

        :param key:
        :param value:
        :return:
        """
        self.__meta[key] = value

    def init_meta(self, peer_id, score_id, score_ver, channel_name: str=conf.LOOPCHAIN_DEFAULT_CHANNEL):
        """Tx 의 meta 정보 중 Peer 에 의해서 초기화되는 부분을 집약하였댜.
        tx 의 put_data 발생시 tx 의 hash 를 생성하게 되며 이때 meta 정보를 hash 계산에 사용하게 되므로
        meta 정보의 구성은 put_data 이전에 완료하거나 혹은 put_data 후에 meta 정보를 추가하게 된다면
        hash 를 다시 생성하여야 한다.

        :param peer_id:
        :param score_id:
        :param score_ver:
        :param channel_name:
        :return:
        """
        self.put_meta(Transaction.PEER_ID_KEY, peer_id)
        self.put_meta(Transaction.SCORE_ID_KEY, score_id)
        self.put_meta(Transaction.SCORE_VERSION_KEY, score_ver)
        self.put_meta(Transaction.CHANNEL_KEY, channel_name)

    def get_data(self):
        """트랜잭션 데이터를 리턴합니다.

        :return 트랜잭션 데이터:
        """
        return self.__data

    def get_data_string(self):
        return self.__data.decode(conf.PEER_DATA_ENCODING)

    def put_data(self, data, time_stamp=None):
        """데이터 입력
        data를 받으면 해당 시간의 Time stamp와 data를 가지고 Hash를 생성해서 기록한다.

        :param data: Transaction에 넣고 싶은 data. data가 스트링인 경우 bytearray로 변환한다.
        :param time_stamp:
        :return Transaction의 data를 가지고 만든 Hash값:
        """
        if isinstance(data, str):
            self.__data = bytearray(data, 'utf-8')
        else:
            self.__data = data

        if time_stamp is None:
            self.__time_stamp = int(time.time()*1000000)
        else:
            self.__time_stamp = time_stamp

        # logging.debug("transaction Time %s , time_stamp Type %s", self.__time_stamp, type(self.__time_stamp))

        return self.__generate_hash()

    def get_timestamp(self):
        """트랜잭션 timeStamp를 반환
        """
        return self.__time_stamp

    def __generate_hash(self):
        """트랜잭션의 hash를 생성한다.

        :return Transaction의 data를 가지고 만든 Hash값:
        """
        # self.__transaction_hash = Transaction.generate_transaction_hash(self)

        _meta_byte = util.dict_to_binary(self.__meta)
        _time_byte = struct.pack('Q', self.__time_stamp)
        _txByte = b''.join([_meta_byte, self.__data, _time_byte])
        self.__transaction_hash = hashlib.sha256(_txByte).hexdigest()

        # logging.debug("__generate_hash \ntx hash : " + self.__transaction_hash +
        #               "\ntx meta : " + str(self.__meta) +
        #               "\ntx data : " + str(self.__data))

        return self.__transaction_hash

    # TODO property.tx_hash 로 대체할 것
    def get_tx_hash(self):
        """트랜잭션의 해쉬 값을 리턴합니다

        :return: 트랜잭션의 해쉬 값
        """
        return self.__transaction_hash

    @staticmethod
    def generate_transaction_hash(tx):
        """트랜잭션 Hash 생성

        :param tx: 트랜잭션
        :return: 트랜잭션 Hash
        """
        _meta_byte = util.dict_to_binary(tx.meta)
        _data_byte = tx.get_data()
        _time_byte = struct.pack('Q', tx.get_timestamp())
        _txByte = b''.join([_meta_byte, _data_byte, _time_byte])
        _txhash = hashlib.sha256(_txByte).hexdigest()
        # logging.debug("__generate_hash \ntx hash : " + _txhash +
        #               "\ntx meta : " + str(tx.meta) +
        #               "\ntx data : " + str(tx.get_data()))

        return _txhash

    def sign_hash(self, peer_authorization) -> bool:
        """sign to signature hash

        :param peer_authorization: peer_authorization for sign
        :return: if sign success return true, else return false
        """
        signature = peer_authorization.sign_data(self.tx_hash, is_hash=True)
        self.__public_key = peer_authorization.get_public_der()

        if signature:
            self.__signature = signature
            return True
        else:
            logging.error(f"sign transaction {self.tx_hash} fail")
            return False

    @staticmethod
    def validate(tx, is_exception_log=True) -> bool:
        """validate tx(hash, signature)

        :param tx: transaction
        :return: validate result
        """
        # HASH Validate
        # logging.debug("Transaction Hash %s", tx.get_tx_hash())
        try:
            if Transaction.generate_transaction_hash(tx) != tx.get_tx_hash():
                Transaction.__logging_tx_validate("hash validate fail", tx)
                return False

            # Get Cert Verifier for signature verify
            public_verifier = PublicVerifierContainer.get_public_verifier(tx.public_key)

            # Signature Validate
            if public_verifier.verify_hash(tx.get_tx_hash(), tx.signature):
                return True
            else:
                if is_exception_log:
                    Transaction.__logging_tx_validate("signature validate fail", tx)
                return False

        except Exception as e:
            # logging.exception(e)
            if is_exception_log:
                Transaction.__logging_tx_validate(str(e), tx)
            return False

    @staticmethod
    def __logging_tx_validate(fail_message, tx):
        logging.error("validate tx fail \ntx hash : " + tx.get_tx_hash() +
                      "\ntx meta : " + str(tx.meta) +
                      "\ntx data : " + str(tx.get_data()) +
                      "\ntx signature : " + str(tx.signature) +
                      "\n cause by : " + fail_message)
