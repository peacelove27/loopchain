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
""" A class for Radio station"""

from loopchain import configure as conf


class RadioStation:
    """ Peer들을 등록, 삭제등 전체적인 관리를 담당
    """

    def __init__(self):
        # {group_id:[ {peer_id:IP} ] }로 구성된 dictionary
        self.peer_groups = {conf.ALL_GROUP_ID: []}

        # Peer의 보안을 담당
        self.auth = {}

    def __del__(self):
        pass

    def launch_block_generator(self):
        pass

    def get_group_id(self):
        # TODO: 외부 관리 interface에 의해서 Group을 관리하는 기능을 만들어야 한다. 현재는 고정된 한개 Group만.
        return conf.ALL_GROUP_ID

    def validate_group_id(self, group_id: str):
        # TODO group id 를 검사하는 새로운 방법이 필요하다, 현재는 임시로 모두 통과 시킨다.
        return 0, "It's available group ID:"+group_id

        # if group_id == conf.TEST_GROUP_ID:
        #     return 0, "It's available group ID:"+group_id
        # else:
        #     return -1, "Not available group ID:"+group_id
