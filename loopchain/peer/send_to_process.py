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
"""A util class for Sent to Process"""

import logging
import time
import queue

from loopchain.baseservice import CommonThread
from loopchain import configure as conf


class SendToProcess(CommonThread):
    def __init__(self):
        CommonThread.__init__(self)
        self.__job = queue.Queue()
        self.__process = None

    def set_process(self, process):
        self.__process = process

    def send_to_process(self, params):
        """return이 불필요한 process send를 비동기로 처리하기 위하여 queue in thread 방법을 사용한다.

        :param PeerProcess 에 전달하는 command 와 param 의 쌍
        """
        # logging.debug("send job queue add")
        self.__job.put(params)

    def run(self):
        while self.is_run:
            time.sleep(conf.SLEEP_SECONDS_IN_SERVICE_LOOP)

            param = None
            while not self.__job.empty():
                # logging.debug("Send to Process by thread.... remain jobs: " + str(self.__job.qsize()))

                param = self.__job.get()
                try:
                    self.__process.send_to_process(param)
                    param = None
                except Exception as e:
                    logging.warning(f"process not init yet... ({e})")
                    break

            if param is not None:
                self.__job.put(param)
