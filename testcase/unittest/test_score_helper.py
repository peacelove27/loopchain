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
"""Test Score Helper"""

import unittest
from unittest.mock import patch
import json
import loopchain.utils as util
import os.path as osp
import shutil
import loopchain.configure as conf
from loopchain.baseservice import ObjectManager
from loopchain.tools.score_helper import ScoreHelper, ScoreDatabaseType

util.set_log_level_debug()


class TestScoreHelper(unittest.TestCase):
    conf = None
    __repository_path = osp.join(osp.dirname(__file__), 'db_')
    @classmethod
    def setUpClass(cls):
        conf.DEFAULT_SCORE_REPOSITORY_PATH = cls.__repository_path
        # Deploy path 에 clone 한다
        if osp.exists(cls.__repository_path):
            shutil.rmtree(cls.__repository_path, True)

    @classmethod
    def tearDownClass(cls):
        #shutil.rmtree(cls.__repository_path, True)
        pass

    @patch('loopchain.container.ScoreService')
    def test_score_helper_load_databases(self, score_service_mock):
        # get peer status Mockup
        score_service_mock.get_peer_status = lambda: json.loads(
            '{"total_tx": "0", "block_height": "0", \
            "status": {"peer_type": "0", "total_tx": 0, "consensus": "siever", "status": "Service is online: 0", \
            "block_height": 0, "audience_count": 0, "peer_id": "d3694dcc-24ff-11e7-b0d1-0242ac110001"}}'
        )
        score_service_mock.get_peer_id = lambda: 'test_score_helper_load_databases'

        ObjectManager().score_service = score_service_mock

        helper = ScoreHelper()
        sqlite_conn = helper.load_database('sqlite_test')
        self.assertIsNotNone(sqlite_conn)
        self.assertIsNotNone(sqlite_conn.cursor())

        leveldb_conn = helper.load_database('leveldb_test', ScoreDatabaseType.leveldb)
        self.assertIsNotNone(leveldb_conn)
        self.assertIsNotNone(sqlite_conn.cursor())


