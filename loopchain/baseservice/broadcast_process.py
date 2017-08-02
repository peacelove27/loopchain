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
"""gRPC broadcast process"""

import json
import logging
import time

from loopchain import configure as conf
from loopchain.baseservice import ManageProcess, StubManager
from loopchain.protos import loopchain_pb2_grpc, message_code


class BroadcastProcess(ManageProcess):
    """broadcast to peer.
    It's a separated process from main peer process, so It has own peer list.
    """
    PROCESS_INFO_KEY = "process_info"

    def process_loop(self, manager_dic, manager_list):
        logging.info("Broadcast Process Start.")

        command = None

        # for bloadcast(announce) peer Dic ( key=peer_target, value=stub(gRPC) )
        __audience = {}

        def __broadcast_run(method_name, method_param):
            """call gRPC interface of audience
            
            :param method_name: gRPC interface
            :param method_param: gRPC message
            """

            for peer_target in list(__audience):
                logging.debug("peer_target: " + peer_target)
                stub_item = __audience[peer_target]
                try:
                    # logging.debug("method_name: " + method_name)
                    response = stub_item.call_async(method_name, method_param)
                    # logging.info("broadcast response: " + str(response))
                except Exception as e:
                    logging.warning("gRPC Exception: " + str(e))
                    logging.warning(f"Fail broadcast({method_name}) to: " + peer_target)

        def __handler_subscribe(subscribe_peer_target):
            logging.debug("BroadcastProcess received subscribe command peer_target: " + str(subscribe_peer_target))
            stub_manager = StubManager.get_stub_manager_to_server(
                subscribe_peer_target, loopchain_pb2_grpc.PeerServiceStub,
                is_allow_null_stub=True
            )
            __audience[subscribe_peer_target] = stub_manager

        def __handler_unsubscribe(unsubscribe_peer_target):
            logging.debug("BroadcastProcess received unsubscribe command peer_target: " + str(unsubscribe_peer_target))
            try:
                del __audience[unsubscribe_peer_target]
            except KeyError:
                logging.warning("Already deleted peer: " + str(unsubscribe_peer_target))

        def __handler_broadcast(broadcast_param):
            logging.debug("BroadcastProcess received broadcast command")
            broadcast_method_name = broadcast_param[0]
            broadcast_method_param = broadcast_param[1]
            logging.debug("BroadcastProcess method name: " + broadcast_method_name)
            # logging.debug("BroadcastProcess method param: " + str(broadcast_method_param))
            __broadcast_run(broadcast_method_name, broadcast_method_param)

        def __handler_status(status_param):
            logging.debug("BroadcastProcess Status, param: " + str(status_param))
            logging.debug("Audience: " + str(len(__audience)))

            status = dict()
            status['result'] = message_code.get_response_msg(message_code.Response.success)
            status['Audience'] = str(len(__audience))
            status_json = json.dumps(status)

            # return way of manage_process
            manager_dic["status"] = status_json

        __handler_map = {
            "subscribe": __handler_subscribe,
            "unsubscribe": __handler_unsubscribe,
            "broadcast": __handler_broadcast,
            "status": __handler_status
        }

        while command != ManageProcess.QUIT_COMMAND:
            # logging.debug(f"manager list: {manager_list}")
            try:
                if not manager_list:
                    time.sleep(conf.SLEEP_SECONDS_IN_SERVICE_LOOP)
                else:
                    # packet must be a tuple (command, param)
                    command, param = manager_list.pop()

                    if command in __handler_map.keys():
                        __handler_map[command](param)
                        continue

                    if command == ManageProcess.QUIT_COMMAND:
                        logging.debug(f"BroadcastProcess peer({manager_dic[self.PROCESS_INFO_KEY]}) will quit soon.")
                    else:
                        logging.error("BroadcastProcess received Unknown command: " +
                                      str(command) + " and param: " + str(param))
            except Exception as e:
                time.sleep(conf.SLEEP_SECONDS_IN_SERVICE_LOOP)
                logging.error(f"broadcast process not available reason({e})")

        logging.info("Broadcast Process Ended.")
