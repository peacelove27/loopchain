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
"""base class for sub processes"""

import logging
import multiprocessing
from abc import abstractmethod

import loopchain.utils as util

util.set_log_level()


class CommonProcess:
    """BaseClass for MultiProcess Architecture.
    It has same interface name as CommonThread for easy conversion.
    """

    def __init__(self):
        self.__conn = None
        self.__run_process = None

    def is_run(self):
        return self.__run_process.is_alive()

    def start(self):
        parent_conn, child_conn = multiprocessing.Pipe()

        self.__conn = parent_conn
        self.__run_process = multiprocessing.Process(target=self.run, args=(child_conn, ))
        self.__run_process.start()

    def stop(self):
        logging.debug("try stop process...")

        # When the process starts, the value setting through the method does not work. (Differences from threads)
        #  Communication is possible only through process_queue.
        self.send_to_process(("quit", None))

    def wait(self):
        self.__run_process.join()

    def send_to_process(self, job):
        self.__conn.send(job)

    # pipe recv 는 안정성에 문제가 있는 것으로 파악됨
    # TODO pipe recv 대신 내부 process 는 메시지 리턴을 마더 프로세스의 gRPC Notify- 인터페이스를 이용하도록 수정한다.
    def recv_from_process(self):
        """process 에서 pipe 를 통해서 값을 구한다.
        pipe 는 속도면에서 queue 보다 빠르다.
        다량의 send 가 진행되는 상황에서 recv 로직이 에러를 발생한 적 있음 (fixed: LOOPCHAIN-117)
        현재는 process 시작을 확인 하는 용도로만 사용하고 있음!, 다른 용도로 사용하지 말것!
        그외의 상황에서도 recv 가 오류를 발생함.

        :return:
        """
        try:
            return self.__conn.recv()
        except EOFError:
            logging.error("fail recv from process!")
            return None

    @abstractmethod
    def run(self, child_conn):
        """멀티 프로세스로 동작할 루프를 정의한다.
        sample 구현을 참고한다.
        """
        # # sample 구현
        # command = None
        # while command != "quit":
        #     command, param = conn.recv()  # Pipe 에 내용이 들어올 때까지 여기서 대기 된다. 따라서 Sleep 이 필요 없다.
        pass
