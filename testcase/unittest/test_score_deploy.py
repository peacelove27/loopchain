#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
"""Test Score Deploy"""

import logging
import os.path as osp
import shutil
import unittest

from git import Repo

import loopchain.configure as conf
import loopchain.utils as util
import testcase.unittest.test_util as test_util
from loopchain.baseservice import PeerScore

util.set_log_level_debug()


class TestScoreDeploy(unittest.TestCase):
    __deploy_path = osp.join(osp.dirname(__file__), "../../resources/test_score_deploy")
    __deploy_path = osp.abspath(__deploy_path)
    __base = 'git@repo.theloop.co.kr'
    __package_name = 'score/chain_message_score'
    __repo_url = __base+':'+__package_name+'.git'
    __repository_path = osp.join(__deploy_path, __package_name)
    __repo = None
    conf.DEFAULT_SCORE_BRANCH = 'master'

    @classmethod
    def setUpClass(cls):
        # Deploy path 에 clone 한다
        if osp.exists(cls.__repository_path):
            shutil.rmtree(cls.__repository_path, True)
        cls.__repo = Repo.clone_from(cls.__repo_url, cls.__repository_path, branch='master')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.__deploy_path, True)

    @unittest.skip("git config")
    def test_global_config(self):
        # global git 설정 확인
        # global gitignore

        repo = Repo(self.__repository_path)
        logging.debug(repo.config_level)
        config_reader = repo.config_reader("global")
        # global git username
        user = {}

        user['name'] = config_reader.get_value('user', "name")
        user['email'] = config_reader.get_value('user', 'email')
        logging.debug("user Name"+str(user))

        config_reader = repo.config_reader("repository")
        remote_url = config_reader.get_value('remote "origin"', 'url')
        self.assertIsNotNone(remote_url)
        logging.debug("remote : "+str(remote_url))

    @unittest.skip("skip history")
    def test_deploy_remote_repository(self):
        # check version in master
        repo = Repo(self.__repository_path)
        # Deploy path 하위에 deploy 디렉토리를 만든다
        deploy_path = osp.join(self.__repository_path, 'deploy')

        # get history hash for branch
        history_sha = repo.git.rev_list('master', '--first-parent').split()
        logging.debug(history_sha)

        # all version deploy
        for version in history_sha:
            version_path = osp.join(deploy_path, version)
            # Deploy path 하위의 deploy 디렉토리 하위에 버젼별로 deploy_path 의 하위버젼을 클로닝 한다
            version_repo = repo.clone(version_path)
            # 해당 버젼으로 체크아웃을 한다
            version_repo.git.checkout(version)

    @unittest.skip("check is git")
    def test_is_git_repository(self):
        repo = git.repo.fun.is_git_dir(conf.DEFAULT_SCORE_REPOSITORY_PATH)

    @unittest.skip("git reset config")
    def test_deploy_dirty(self):
        # make some file
        with open(self.__repository_path+'/test.txt', "a") as myfile:
            myfile.write("appended text")
            myfile.close()

        repo = Repo(self.__repository_path)
        if repo.is_dirty(True, True, True):
            logging.debug("repo is dirty")
            repo.git.reset('--hard')

        self.assertFalse(repo.is_dirty(), 'repository is dirty')

    @unittest.skip("git deploy lasthash")
    def test_deploy_lasthash(self):
        last_hash = Repo(self.__repository_path).git.rev_parse('HEAD')
        logging.debug(last_hash)
        self.assertIsNotNone(last_hash)

    @unittest.skip("git deploy pull")
    def test_deploy_pull(self):
        Repo(self.__repository_path).git.pull('origin', 'develop')

    def test_score_manager_default(self):
        """
        score manager 기본 Score 로드

        :return:
        """
        ps = PeerScore()
        self.assertIsNotNone(ps.last_version(), 'load default package is fail')

    def test_filename_validate(self):
        """패키지 파일에 대한 테스트를 진행

        :return:
        """
        package = 'loopchain/default'
        convert_package = util.get_valid_filename(package)
        logging.debug(convert_package)
        self.assertEqual(convert_package, 'loopchain_default', 'package name is convert to file')

    def test_score_manager(self):
        # test remote repository
        ps = PeerScore(self.__deploy_path, self.__package_name)
        logging.debug(ps.last_version())

        all_version = ps.all_version()
        first_version = ps.score_version(all_version[0])
        logging.debug("first version :"+str(first_version.info()))

        logging.debug(ps.last_version())

        self.assertIsNotNone(ps.last_version())

    def test_score_manager_by_remote(self):
        shutil.rmtree(self.__deploy_path, True)
        self.test_score_manager()


