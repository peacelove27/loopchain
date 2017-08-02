# Copyright [theloop]
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
""" A library module for development of Score"""

import sqlite3
import logging
import leveldb
import os
import os.path as osp
from enum import Enum
from loopchain.baseservice import ObjectManager
from loopchain import configure as conf


class ScoreDatabaseType(Enum):
    sqlite3 = 'sqlite3'
    leveldb = 'leveldb'


class ScoreHelper:
    """
    Score 를 개발하기 위한 라이브러리
    """
    loopchain_objects = None
    __connection = None
    __cursor = None
    __SCORE_DATABASE_STORAGE = conf.DEFAULT_SCORE_STORAGE_PATH
    __peer_id = None

    def __init__(self):
        logging.debug("ScoreHelper init")
        self.loopchain_objects = ObjectManager()

    def validate_block(self, score, block):
        pass

    def load_database(self, score_id, database_type=ScoreDatabaseType.sqlite3):
        """Score Database Load

        :param score:
        :param database_type:
        :return:
        """
        # peer_id 별로 databases 를 변경 할 것인지?
        connection = None

        # Peer의 정보
        # TODO 차후 Plugin 혹은 모듈 방식으로 변경
        if database_type is ScoreDatabaseType.sqlite3:
            return self.__sqlite3_database(score_id)
        elif database_type is ScoreDatabaseType.leveldb:
            return self.__leveldb_database(score_id)
        else:
            logging.error("Did not find score database type")

        return connection

    def __load_peer_id(self):
        # DEFAULT peer status
        peer_id = 'local'

        if self.loopchain_objects.score_service is not None:
            peer_id = self.loopchain_objects.score_service.get_peer_id()
        return peer_id

    def __db_filepath(self, peer_id, score_id):
        """make Database Filepath

        :param peer_id: peer ID
        :param score_id: score ID
        :return: score database filepath
        """
        _score_database = osp.join(self.__SCORE_DATABASE_STORAGE, peer_id)
        _score_database = osp.abspath(_score_database)
        if not osp.exists(_score_database):
            os.makedirs(_score_database)
        _score_database = osp.join(_score_database, score_id)
        return _score_database

    def __sqlite3_database(self, score_id):
        """Sqlite3용 Database 생성

        :param score_info:
        :return:
        """
        peer_id = self.__load_peer_id()
        _score_database = self.__db_filepath(peer_id , score_id)
        connect = sqlite3.connect(_score_database, check_same_thread=False)
        return connect

    def __leveldb_database(self, score_id):
        """Leveldb 용 Database 생성


        :param score_info:
        :return:
        """
        peer_id = self.__load_peer_id()
        _score_database = self.__db_filepath(peer_id, score_id)
        try:
            return leveldb.LevelDB(_score_database, create_if_missing=True)
        except leveldb.LevelDBError:
            raise leveldb.LevelDBError("Fail To Create Level DB(path): %s", _score_database)
