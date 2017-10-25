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
"""Test Manage Process"""

import logging
import unittest
import time

import loopchain.utils as util
from loopchain import configure as conf
from loopchain.baseservice import ManageProcess
from loopchain.baseservice import CommonThread

util.set_log_level_debug()


class SampleThread(CommonThread):
    def __init__(self):
        self.__run_times = 0
        self.__var = 0

    def set_var(self, var):
        self.__var = var

    def get_run_times(self):
        return self.__run_times

    def run(self):
        while self.is_run:
            time.sleep(conf.SLEEP_SECONDS_IN_SERVICE_LOOP)
            self.__run_times += 1
            logging.debug("SampleThread, I have: " + str(self.__var))


class SampleManageProcess(ManageProcess):

    def process_loop(self, manager_dic, manager_list):
        run_times = 0
        command = None

        while command != ManageProcess.QUIT_COMMAND:
            if not manager_list:
                time.sleep(conf.SLEEP_SECONDS_IN_SERVICE_LOOP)
            else:
                # packet must be a tuple (command, param)
                command, param = manager_list.pop()
                if param is not None:
                    run_times += 1
                    print("SampleManageProcess, I got: " + str(param))
                    manager_dic[str(param)] = int(param) * 10


class TestManageProcess(unittest.TestCase):

    def test_manage_process(self):
        # GIVEN
        sample_process1 = SampleManageProcess()
        sample_process1.start()

        times = 0
        while times < 2:
            logging.debug("wait process running...")
            sample_process1.send_to_process(("times", times))
            time.sleep(1)
            times += 1

        # WHEN
        result = sample_process1.get_receive()
        logging.debug(f"result from process({result})")

        result1 = sample_process1.get_receive('1')
        logging.debug(f"result1({result1})")

        result = sample_process1.get_receive()
        logging.debug(f"result from process after get result({result})")

        result2 = sample_process1.pop_receive('1')
        logging.debug(f"result2({result2})")

        result = sample_process1.get_receive()
        logging.debug(f"result from process after pop result({result})")

        sample_process1.stop()
        sample_process1.wait()

        # THEN
        self.assertEqual(result1, 10)


if __name__ == '__main__':
    unittest.main()
