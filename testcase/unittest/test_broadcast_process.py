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
"""Test Broadcast Process"""

import logging
import time
import unittest

import loopchain.utils as util
from loopchain.baseservice import BroadcastProcess
from loopchain.protos import message_code

util.set_log_level_debug()


class TestBroadcastProcess(unittest.TestCase):

    def test_broadcast_process(self):
        # TODO base 클래스가 변경되어 테스트 재작성 필요함
        ## GIVEN
        broadcast_process = BroadcastProcess()
        broadcast_process.start()

        ## WHEN
        result = ""
        times = 0
        while times < 2:
            broadcast_process.send_to_process(("status", "param"))
            # result = broadcast_process.recv_from_process()
            # logging.debug("broadcast_process status: " + result)
            time.sleep(1)
            times += 1

        broadcast_process.stop()
        broadcast_process.wait()

        ## THEN
        # self.assertEqual(result, message_code.get_response_msg(message_code.Response.success))


if __name__ == '__main__':
    unittest.main()
