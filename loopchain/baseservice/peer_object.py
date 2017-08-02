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
"""Peer Objects"""

import datetime
from enum import IntEnum


class PeerStatus(IntEnum):
    unknown = 0
    connected = 1
    disconnected = 2


class Peer:
    # TODO Peer 관련 메소드 중복된 코드를 이 오브젝트로 옮겨서 중복 제거 검토
    """Peer Object

    """
    def __init__(self):
        # TODO self.var -> self.__var and use @property 바꾸기~~ ^^
        self.order = 0
        self.peer_id = ""
        self.group_id = ""
        self.target = ""
        self.auth = ""
        self.token = ""
        self.status_update_time = datetime.datetime.now()

        self.__status = PeerStatus.unknown

        # TODO Peer 가 Stub manager 를 가지고 pickle dump 가 되는지 확인 필요
        # self.__stub_manager = None

    @property
    def status(self):
        return self.__status

    @status.setter
    def status(self, status):
        if self.__status != status:
            self.status_update_time = datetime.datetime.now()
            self.__status = status

    def get_token(self):
        return self.token

        # TODO is alive 를 Peer 에 구현하는 것으로 PeerManager 의 코드 중복을 줄일 수 있는지 검토후 작성할 것
        # def is_alive(self, peer_stub=None):
        #     pass

        # def dump(self):  # for debug
        #     """디버깅을 위한 함수로 평소에는 peer_list 덤프에 포함되지 않도록 주석처리 한다.
        #     """
        #     for attr in dir(self):
        #         logging.debug("Peer.%s = %s" % (attr, getattr(self, attr)))
