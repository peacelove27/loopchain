#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from loopchain.blockchain import ScoreBase


class UserScore(ScoreBase):
    """Score Container 의 오류를 유발하기 위한 의도된 Black Score
    
    """
    def invoke(self, transaction, block):
        logging.debug("in black score invoke...")
        print[]  # intended error

    def query(self, params):
        logging.debug("in black score query...")
        return params

    def info(self):
        # TODO Score info (package.json) 을 로드하여 json object 를 리턴하여야 한다.
        return None
