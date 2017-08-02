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
"""User Score Sample"""

import logging
import sqlite3
import loopchain.utils as util

from loopchain.blockchain import ScoreBase


class UserScore(ScoreBase):
    """ 체인코드 샘플
        체인코드의 샘플이므로 invoke 시에 블럭의 tx를 그냥 저장하는 역활만 합니다.
    """

    def __init__(self):
        self.sample_db = None
        self.cursor = None

    def test(self):
        """file path 로 부터 UserScore 가 불려졌는지를 확인한다.
        :return: 궁극의 질문에 대한 대답
        """
        logging.info("Call Test from User Chain Code")
        return "user sample"

    def set_db(self, db_name):
        self.sample_db = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.sample_db.cursor()
        try:
            self.cursor.execute("CREATE TABLE IF NOT EXISTS BLOCK_TX(Tx_Data text, Tx_hash text, Block_hash text)")
            self.cursor.execute("DELETE FROM BLOCK_TX")
        except sqlite3.OperationalError:
            exit_msg = "Server Stop by database locked, db_name is: " + db_name
            logging.error(exit_msg)
            exit(exit_msg)

    def check_db(self):
        if self.sample_db is None:
            self.set_db('sample_score')

    def invoke(self, block):
        self.check_db()

        block_tx_list = []
        block_hash = block.block_hash
        for tx in block.confirmed_transaction_list:
            tx_data = str(tx.get_data(), 'utf-8')
            tx_hash = tx.get_tx_hash()
            block_tx_list.append((tx_data, tx_hash, block_hash))

        self.cursor.executemany("INSERT INTO BLOCK_TX VALUES(?, ?, ?)", block_tx_list)
        self.sample_db.commit()

    def query(self, **kwargs):
        # TODO 현재 구현은 내부 테스용으로
        # json string in/out rule 을 따르지 않는다.
        # ScoreBase 를 상속받은 query 구현은
        # in/out 을 json string 으로 처리하여야 한다.

        self.check_db()

        f = kwargs.get('function')
        if f == 'block_data':
            block_hash = kwargs.get('block_hash')
            return self.cursor.execute('SELECT * FROM BLOCK_TX WHERE Block_hash = ?', [block_hash])
        else:
            return None

    def info(self):
        # TODO Score info (package.json) 을 로드하여 json object 를 리턴하여야 한다.
        return None
