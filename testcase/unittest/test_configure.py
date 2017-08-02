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
"""Test Configure class"""

import logging
import sys
import unittest

sys.path.append('../')
from loopchain import configure as conf
from loopchain import configure_default as conf_default
import loopchain.utils as util

util.set_log_level_debug()


class TestConfigure(unittest.TestCase):

    def test_get_configure(self):
        logging.debug(f"conf.IP_LOCAL: {conf.IP_LOCAL}")
        self.assertEqual(conf.IP_LOCAL, conf_default.IP_LOCAL)

        logging.debug(f"conf.GRPC_TIMEOUT: {conf.GRPC_TIMEOUT}")
        self.assertTrue(isinstance(conf.GRPC_TIMEOUT, int))

        logging.debug(f"conf.LOG_LEVEL: {conf.LOG_LEVEL}")
        self.assertEqual(conf.LOG_LEVEL, conf_default.LOG_LEVEL)

        logging.debug(f"conf.LEVEL_DB_KEY_FOR_PEER_LIST: {conf.LEVEL_DB_KEY_FOR_PEER_LIST}")
        self.assertEqual(conf.LEVEL_DB_KEY_FOR_PEER_LIST, conf_default.LEVEL_DB_KEY_FOR_PEER_LIST)

        logging.debug(f"conf.TOKEN_TYPE_TOKEN: {conf.TOKEN_TYPE_TOKEN}")
        self.assertTrue(isinstance(conf.TOKEN_TYPE_TOKEN, str))


if __name__ == '__main__':
    unittest.main()
