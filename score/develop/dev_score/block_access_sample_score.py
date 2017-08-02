#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import json
import loopchain.configure as conf
from loopchain.blockchain import ScoreBase


class UserScore(ScoreBase):
    """ peer service, score service 연동 샘플 스코어
    마지막 블럭 해시를 구한 다음 전체 블럭을 조회해서 순회하는 샘플 코드
    run this: ./peer.py -d -p 7100 -c develop/dev_score
    
    """
    def invoke(self, transaction, block):
        logging.debug("in block access sample score invoke...")

        # block loop sample by hash
        logging.debug("::block loop sample by hash")

        block_hash = self._score_service.get_last_block_hash()
        total_tx = 0
        total_height = -1

        logging.debug("get last block hash: " + block_hash)

        while block_hash is not None:
            response = self._score_service.get_block_by_hash(block_hash)
            logging.debug("block is: " + str(response))

            if len(response.block_data_json) > 0:
                block_data = json.loads(response.block_data_json)
                logging.debug("[block height: " + str(block_data["height"]) +
                              ", hash: " + str(block_data["block_hash"]) + "]")

                if len(response.tx_data_json) == 1:
                    tx_data = json.loads(response.tx_data_json[0])
                    logging.debug("has tx: " + str(tx_data["tx_hash"]))
                else:
                    logging.debug("has tx: " + str(len(response.tx_data_json)))

                total_height += 1
                total_tx += len(response.tx_data_json)
                block_hash = block_data["prev_block_hash"]

                if int(block_data["height"]) == 0:
                    block_hash = None
            else:
                block_hash = None

        logging.debug("\nblock chain height: " + str(total_height) + ", total tx: " + str(total_tx))

        # block loop sample by height
        logging.debug("::block loop sample by height")

        response = self._score_service.get_block()  # null request, return last block
        total_tx = 0
        total_height = -1

        if response.response_code == message_code.Response.success:
            logging.debug("block is: " + str(response))

            block_data = json.loads(response.block_data_json)
            logging.debug("[block height: " + str(block_data["height"]) +
                          ", hash: " + str(block_data["block_hash"]) + "]")
            logging.debug("get last block height: " + str(block_data["height"]))
            block_height = int(block_data["height"])

            logging.debug("block_data_json: " + response.block_data_json)

            while block_height >= 0:
                response = self._score_service.get_block_by_height(block_height)
                logging.debug("in while, block is: " + str(response))

                if len(response.block_data_json) > 0:
                    block_data = json.loads(response.block_data_json)
                    logging.debug("[block height: " + str(block_data["height"]) +
                                  ", hash: " + str(block_data["block_hash"]) + "]")

                    if len(response.tx_data_json) == 1:
                        tx_data = json.loads(response.tx_data_json[0])
                        logging.debug("has tx: " + str(tx_data["tx_hash"]))
                    else:
                        logging.debug("has tx: " + str(len(response.tx_data_json)))

                    total_height += 1
                    total_tx += len(response.tx_data_json)
                    block_height = int(block_data["height"]) - 1
                else:
                    block_height = -1

        logging.debug("\nblock chain height: " + str(total_height) + ", total tx: " + str(total_tx))

    def query(self, params):
        logging.debug("in block access sample score query...")
        return params

    def info(self):
        # TODO Score info (package.json) 을 로드하여 json object 를 리턴하여야 한다.
        return None
