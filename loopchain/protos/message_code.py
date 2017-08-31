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
""" A massage class for the loopchain """

from enum import IntEnum


class Method:
    """gRPC interface names

    """
    request = "Request"


class Request(IntEnum):
    status = 1
    stop = -9

    score_load = 200
    score_invoke = 201
    score_query = 202
    score_set = 203  # just for test, set score by peer_service
    score_connect = 204  # make stub of peer_service on score_service for IPC

    peer_peer_list = 600
    peer_get_leader = 601  # get leader peer object
    peer_complain_leader = 602  # complain leader peer is no response

    rs_get_configuration = 800
    rs_set_configuration = 801

    tx_create = 900  # create tx to inner tx service
    tx_connect_to_leader = 901  # connect to leader
    tx_connect_to_inner_peer = 902  # connect to mother peer service in same inner gRPC micro service network

    broadcast_subscribe = 1000  # subscribe for broadcast
    broadcast_unsubscribe = 1001  # unsubscribe for broadcast
    broadcast = 1002  # broadcast message


class MetaParams:
    class ScoreLoad:
        repository_path = "repository_path"
        score_package = "score_package"
        base = "base"
        peer_id = "peer_id"

    class ScoreInfo:
        score_id = "score_id"
        score_version = "score_version"


# gRPC Response Code ###
class Response(IntEnum):
    success = 0
    success_validate_block = 1
    success_announce_block = 2
    fail = -1
    fail_validate_block = -2
    fail_announce_block = -3
    fail_wrong_block_hash = -4
    fail_no_leader_peer = -5
    fail_validate_params = -6
    fail_made_block_count_limited = -7
    fail_wrong_subscribe_info = -8
    fail_connect_to_leader = -9
    fail_add_tx_to_leader = -10
    timeout_exceed = -900
    not_treat_message_code = -999


responseCodeMap = {
    Response.success:                   (Response.success,                      "success"),
    Response.success_validate_block:    (Response.success_validate_block,       "success validate block"),
    Response.success_announce_block:    (Response.success_announce_block,       "success announce block"),
    Response.fail:                      (Response.fail,                         "fail"),
    Response.fail_validate_block:       (Response.fail_validate_block,          "fail validate block"),
    Response.fail_announce_block:       (Response.fail_announce_block,          "fail announce block"),
    Response.fail_wrong_block_hash:     (Response.fail_wrong_block_hash,        "fail wrong block hash"),
    Response.fail_no_leader_peer:       (Response.fail_no_leader_peer,          "fail no leader peer"),
    Response.fail_validate_params:      (Response.fail_validate_params,         "fail validate params"),
    Response.fail_wrong_subscribe_info: (Response.fail_wrong_subscribe_info,    "fail wrong subscribe info"),
    Response.fail_connect_to_leader:    (Response.fail_connect_to_leader,       "fail connect to leader"),
    Response.fail_add_tx_to_leader:     (Response.fail_add_tx_to_leader,        "fail add tx to leader"),
    Response.timeout_exceed:            (Response.timeout_exceed,               "timeout exceed")
}


def get_response_code(code):
    return responseCodeMap[code][0]


def get_response_msg(code):
    return responseCodeMap[code][1]


def get_response(code):
    return responseCodeMap[code][0], responseCodeMap[code][1]
