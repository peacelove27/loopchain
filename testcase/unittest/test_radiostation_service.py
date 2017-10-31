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
"""Test RadioStation Service"""
import unittest

import loopchain.utils as util
from loopchain import configure as conf
from loopchain.radiostation import RadioStationService

util.set_log_level_debug()


class TestRadioStationService(unittest.TestCase):

    def test_random_generate(self):
        """GIVEN Random Seed and conf.RANDOM_NUM, conf.KMS = True
        WHEN 2 RadioStationService init params seed
        THEN RadioStationService.__random_table size is conf.RANDOM_TABLE_SIZE
        and each RadioStationService has same random table
        """

        # GIVEN
        seed = 123456

        # default must be False
        self.assertFalse(conf.ENABLE_KMS)
        conf.ENABLE_KMS = True

        # WHEN THEN
        random_table = TestRadioStationService.create_rand_table(seed)
        random_table2 = TestRadioStationService.create_rand_table(seed)

        self.assertEqual(len(random_table), conf.RANDOM_TABLE_SIZE)

        for i in range(len(random_table)):
            random_data: int = random_table[i]
            self.assertEqual(random_data, random_table2[i])

        conf.ENABLE_KMS = False

    @staticmethod
    def create_rand_table(seed) -> list:
        # WHEN
        rs_service = RadioStationService(rand_seed=seed)
        return rs_service._RadioStationService__random_table


if __name__ == '__main__':
    unittest.main()
