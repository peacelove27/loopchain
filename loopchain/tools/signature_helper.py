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
"""Signature Helper for Tx, Vote, Block Signature verify"""

import logging

import binascii
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils, rsa, padding
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicKey
from cryptography.x509 import Certificate


class PublicVerifier:
    """ provide singnature verify function using public key"""
    def __init__(self, public):
        """ set public key
        :param public: der or public Object
        """
        if isinstance(public, bytes):
            self.__public_key = serialization.load_der_public_key(
                public,
                backend=default_backend()
            )
        elif isinstance(public, EllipticCurvePublicKey):
            self.__public_key = public
        else:
            raise ValueError("public must bytes or public_key Object")

    def verify_data(self, data, signature) -> bool:
        """개인키로 서명한 데이터 검증

        :param data: 서명 대상 원문
        :param signature: 서명 데이터
        :return: 서명 검증 결과(True/False)
        """
        pub_key = self.__public_key
        return self.verify_data_with_publickey(public_key=pub_key, data=data, signature=signature)

    def verify_hash(self, digest, signature) -> bool:
        """개인키로 서명한 해시 검증

        :param digest: 서명 대상 해시
        :param signature: 서명 데이터
        :return: 서명 검증 결과(True/False)
        """
        # if hex string
        if isinstance(digest, str):
            try:
                digest = binascii.unhexlify(digest)
            except Exception as e:
                logging.warning(f"verify hash must hex or bytes {e}")
                return False

        return self.verify_data_with_publickey(public_key=self.__public_key,
                                               data=digest,
                                               signature=signature,
                                               is_hash=True)

    @staticmethod
    def verify_data_with_publickey(public_key, data: bytes, signature: bytes, is_hash: bool=False) -> bool:
        """서명한 DATA 검증

        :param public_key: 검증용 공개키
        :param data: 서명 대상 원문
        :param signature: 서명 데이터
        :param is_hash: 사전 hashed 여부(True/False
        :return: 서명 검증 결과(True/False)
        """
        hash_algorithm = hashes.SHA256()
        if is_hash:
            hash_algorithm = utils.Prehashed(hash_algorithm)

        if isinstance(public_key, ec.EllipticCurvePublicKeyWithSerialization):
            try:
                public_key.verify(
                    signature=signature,
                    data=data,
                    signature_algorithm=ec.ECDSA(hash_algorithm)
                )
                return True
            except InvalidSignature:
                logging.debug("InvalidSignatureException_ECDSA")

        elif isinstance(public_key, rsa.RSAPublicKeyWithSerialization):
            try:
                public_key.verify(
                    signature,
                    data,
                    padding.PKCS1v15(),
                    hash_algorithm
                )
                return True
            except InvalidSignature:
                logging.debug("InvalidSignatureException_RSA")
        else:
            logging.debug("Unknown PublicKey Type : %s", type(public_key))

        return False

    def get_public_der(self):
        """ convert public_key to der return public_key
        """
        return self.__public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )


class PublicVerifierContainer:
    """ PublicVerifier Container for many usaged """

    __public_verifier = {}

    # TODO Private BlockChain은 public key가 제한적이라 다 보관, 그러나 다른경우는 어떻게 해야할지 고민 필요
    # TODO 많이 쓰는 것만 남기는 로직을 추가하면 그 때 그떄 생성하는 것보다 더 느릴 수 있음

    @classmethod
    def get_public_verifier(cls, serialized_public: bytes) -> PublicVerifier:
        try:
            public_verifier = cls.__public_verifier[serialized_public]
        except KeyError as e:
            public_verifier = cls.__create_public_verifier(serialized_public)

        return public_verifier

    @classmethod
    def __create_public_verifier(cls, serialized_public: bytes) -> PublicVerifier:
        """ create Public Verifier use serialized_public
        deserialize public key
        :param serialized_public: der public key
        :return: PublicVerifier
        """

        public_verifier = PublicVerifier(serialized_public)
        cls.__public_verifier[serialized_public] = public_verifier

        return public_verifier
