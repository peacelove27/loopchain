#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import logging
from loopchain.blockchain import ScoreBase


class UserScore(ScoreBase):
    """ {"data":"exception"} 이 들어오면 exception을 뿜는 SCORE
    """
    def invoke(self, transaction, block=None):
        """if tx.get_data_string == {"data":"exception"} or tx is not json or not have data throw exception

        :param transaction:
        :param block:
        :return:
        """
        tx_json = json.loads(transaction.get_data_string())
        method = tx_json['method']
        if method == 'exception':
            raise Exception('exception')
        return {'code': 0}

    def query(self, params):
        logging.debug("in UserScore Query...")
        return params

    def info(self):
        # TODO Score info (package.json) 을 로드하여 json object 를 리턴하여야 한다.
        return None
