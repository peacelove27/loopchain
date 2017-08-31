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
"""base class for sub processes with 'multiprocessing.Manager'"""

import logging
import multiprocessing
from abc import abstractmethod

import loopchain.utils as util
from loopchain.baseservice import CommonThread

util.set_log_level()


class ManageProcess(CommonThread):
    """BaseClass for MultiProcess Architecture.
    It has same interface name as CommonThread for easy conversion.
    """
    QUIT_COMMAND = "quit"

    def __init__(self):
        # logging.debug("ManageProcess Init")
        manager = multiprocessing.Manager()
        self.__manager_dic = manager.dict()
        self.__manager_list = manager.list()
        self.__run_process = None

    def is_run(self):
        return self.__run_process.is_alive()

    def run(self):
        # logging.debug("run by CommonTread.start")
        self.__run_process = multiprocessing.Process(
            target=self.process_loop,
            args=(self.__manager_dic, self.__manager_list)
        )
        self.__run_process.start()

    def stop(self):
        # logging.debug("try stop process...")

        # When the process starts, the value setting through the method does not work. (Differences from threads)
        #  Communication is possible only through process_queue.
        self.send_to_process(("quit", None))
        super().stop()

    def wait(self):
        # logging.debug("wait process...")
        self.__run_process.join()
        super().wait()

    def send_to_process(self, job):
        try:
            # logging.debug(f"add job to manage list job :{job}")
            self.__manager_list.append(job)
            # logging.debug(f'manage list append : {self.__manager_list}')
            # logging.debug(f'manage list append : {str(id(self.__manager_list))}')
            return True
        except ConnectionRefusedError as e:
            if job[0] == ManageProcess.QUIT_COMMAND:
                logging.debug(f"Process is already quit.")
                return True

            logging.warning(f"Process is not available. job({job}) error({e})")
            return False

    def set_to_process(self, key, value):
        """Set process manager_dic for communication via IPC

        :param key:
        :param value:
        :return:
        """
        self.__manager_dic[key] = value

    def pop_receive(self, request_id):
        """Use manager_dic for return from process
        manager_dic = {'request_id':'request_result from process'}
        pop_receive get result and remove it from manager dic

        """
        if request_id in self.__manager_dic:
            return self.__manager_dic.pop(request_id)

        return None

    def get_receive(self, request_id=None):
        """Use manager_dic for return from process
        manager_dic = {'request_id':'request_result from process'}
        get_receive get result and keep it in manager dic

        :param request_id: request_id for result. If it is None, this method return manager_dic itself.
        """
        if request_id in self.__manager_dic:
            return self.__manager_dic[request_id]

        if request_id is None:
            return self.__manager_dic

        return None

    @abstractmethod
    def process_loop(self, manager_dic, manager_list):
        """멀티 프로세스로 동작할 루프를 정의한다.

        sample 구현을 참고한다.
        """
        # # sample 구현
        # command = None
        #
        # def __handler_some(status_param):
        #     pass
        #
        # __handler_map = {
        #     "command-some": __handler_some
        # }
        #
        # while command != ManageProcess.QUIT_COMMAND:
        #     # logging.debug(f"manager list: {manager_list}")
        #     if not manager_list:
        #         time.sleep(conf.SLEEP_SECONDS_IN_SERVICE_LOOP)
        #     else:
        #         # packet must be a tuple (command, param)
        #         command, param = manager_list.pop()
        #
        #         if command in __handler_map.keys():
        #             __handler_map[command](param)
        #             continue
        #
        #         if command == "quit":
        #             logging.debug("process will quit soon.")
        #         else:
        #             logging.error("process received Unknown command: " +
        #                           str(command) + " and param: " + str(param))
        #
        pass
