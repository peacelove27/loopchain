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
"""Test OuterService"""
import unittest

import loopchain.utils as util
import testcase.unittest.test_util as test_util
from loopchain.radiostation import OuterService, RadioStationService, ChannelManager

util.set_log_level_debug()


class TestOuterService(unittest.TestCase):

    def setUp(self):
        test_util.print_testname(self._testMethodName)

    def tearDown(self):
        pass

    def test_when_peer_stub_manager_is_none_return_fail(self):
        rs_service = RadioStationService()
        channel_manager = ChannelManager(rs_service.common_service)
        rs_service._RadioStationService__channel_manager = channel_manager
        request = TestRequest('abcd', 'abcd', None)
        outer_service = OuterService()
        context = None
        response = outer_service.GetPeerStatus(request, context)
        self.assertEqual("fail", response.status)


class TestRequest:

    def __init__(self, peer_id, group_id, channel):
        self.peer_id = peer_id
        self.group_id = group_id
        self.channel = channel


if __name__ == '__main__':
    unittest.main()
