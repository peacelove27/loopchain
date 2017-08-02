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
"""A module of exceptions for errors on block chain"""


# BlockChain 관련 Exception
class TransactionInValidError(Exception):
    """트랜잭션 검증오류
    트랜잭션의 데이터와 트랜잭션 hash의 값이 다르다면 오류를 일으킨다
    """
    pass


class BlockInValidError(Exception):
    """블럭 검증오류
    검증되지 않은 블럭이 블럭체인에 추가되거나, 검증시 hash값이 다르다면 발생한다
    """
    pass


class BlockError(Exception):
    """블럭의 구성이 완벽하지 않거나, 구성요소의 일부분이 없을때 발생
    """
    pass


class BlockchainError(Exception):
    """블럭체인상에서 문제가 발생했을때 발생하는 에러
    """
    pass


class ScoreInvokeError(Exception):
    """Error While Invoke Score
    """
