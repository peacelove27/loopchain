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
""" A class for authorization of Peer """

import logging
import datetime
import loopchain.utils as util
from cryptography.hazmat.primitives.asymmetric import rsa, padding, ec
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import PublicFormat
from cryptography.exceptions import InvalidSignature
from os.path import join


class PeerAuthorization:
    """
    Peer의 인증을 처리한다.
    """
    # 인증서/개인키 파일명
    CERT_FILE = "cert.pem"
    PRI_FILE = "key.pem"

    # Peer 보관 CA 인증서 파일명
    PEER_CA_CERT_NAME = "ca.der"

    __peer_cert = None
    __peer_pri = None
    __ca_cert = None
    __token = None

    # RequestPeer 요청 생성 시 저장 정보
    __peer_info = None

    def __init__(self):
        pass

    def load_pki(self, cert_path, cert_pass):
        """
        인증서 추가

        :param cert_path: 인증서 경로
        :param cert_pass: 개인키 패스워드
        :return:
        """
        cert_file = join(cert_path, self.CERT_FILE)
        pri_file = join(cert_path, self.PRI_FILE)
        ca_cert_file = join(cert_path, self.PEER_CA_CERT_NAME)

        # 인증서/개인키 로드
        with open(cert_file, "rb") as der:
            cert_bytes = der.read()
            self.__peer_cert = x509.load_pem_x509_certificate(cert_bytes, default_backend())
        with open(pri_file, "rb") as der:
            private_bytes = der.read()
            try:
                self.__peer_pri = serialization.load_pem_private_key(private_bytes, cert_pass, default_backend())
            except ValueError:
                util.exit_and_msg("Invalid Password")

        # CA 인증서 로드
        with open(ca_cert_file, "rb") as der:
            cert_bytes = der.read()
            self.__ca_cert = x509.load_pem_x509_certificate(cert_bytes, default_backend())

        # 키 쌍 검증
        sign = self.sign_data(b'TEST')
        if self.verify_data(b'TEST', sign) is False:
            util.exit_and_msg("Invalid Signature(Peer Certificate load test)")

    def set_peer_info(self, peer_id, peer_target, group_id, peer_type):
        self.__peer_info = b''.join([peer_id.encode('utf-8'),
                                     peer_target.encode('utf-8'),
                                     group_id.encode('utf-8')]) + bytes([peer_type])

    def add_token(self, token):
        """
        인증토큰 추가

        :param token: 인증토큰
        """
        self.__token = token

    def get_token(self):
        """
        인증토큰
        :return:
        """
        return self.__token

    def get_cert_bytes(self):
        """
        인증서 DER Bytes
        :return:
        """
        return self.__peer_cert.public_bytes(
                encoding=serialization.Encoding.DER,
        )

    def sign_data(self, data):
        """인증서 개인키로 DATA 서명
        :param data: 서명 대상 원문
        :return: 서명 데이터
        """
        if isinstance(self.__peer_pri, ec.EllipticCurvePrivateKeyWithSerialization):
            signer = self.__peer_pri.signer(ec.ECDSA(hashes.SHA256()))
            signer.update(data)
            return signer.finalize()
        elif isinstance(self.__peer_pri, rsa.RSAPrivateKeyWithSerialization):
            return self.__peer_pri.sign(
                data,
                padding.PKCS1v15(),
                hashes.SHA256()
            )
        else:
            logging.debug("Unknown PrivateKey Type : %s", type(self.__peer_pri))
            return None

    def verify_data(self, data, signature):
        """
        개인키로 서명한 데이터 검증
        :param data: 서명 대상 원문
        :param signature: 서명 데이터
        :return: 서명 검증 결과(True/False)
        """
        pub_key = self.__peer_cert.public_key()
        return self.verify_data_with_publickey(public_key=pub_key, data=data, signature=signature)

    def verify_data_with_publickey(self, public_key, data, signature):
        """
        서명한 DATA검증
        :param public_key: 검증용 공개키
        :param data: 서명 대상 원문
        :param signature: 서명 데이터
        :return: 서명 검증 결과(True/False)
        """
        if isinstance(public_key, ec.EllipticCurvePublicKeyWithSerialization):
            try:
                public_key.verify(
                    signature=signature,
                    data=data,
                    signature_algorithm=ec.ECDSA(hashes.SHA256())
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
                    hashes.SHA256()
                )
                return True
            except InvalidSignature:
                logging.debug("InvalidSignatureException_RSA")
        else:
            logging.debug("Unknown PublicKey Type : %s", type(public_key))

        return False

    def generate_request_sign(self, rand_key):
        """
        RequestPeer 서명을 생성한다.
        set_peer_info 함수가 우선 실행되어야 한다.
        sign_peer(peer_id || peer_target || group_id || peet_type || rand_key)
        :param rand_key: 서버로 부터 수신한 랜덤
        :return: 서명
        """
        tbs_data = self.__peer_info + bytes.fromhex(rand_key)
        return self.sign_data(tbs_data)

    def get_token_time(self, token):
        """
        Token의 유효시간을 검증하고 토큰을 검증하기 위한 데이터를 반환한다.
        :param token: 검증 대상 Token
        :return: 검증 실패 시 None, 성공 시 토큰 검증을 위한 데이터
        """
        token_time = token[2:18]
        token_date = int(token_time, 16)
        current_date = int(datetime.datetime.now().timestamp() * 1000)
        if current_date < token_date:
            return bytes.fromhex(token_time)

        return None

    def verify_token(self, token):
        """
        RequestPeer 응답에 포함된 Token의 유효성을 검증한다.
        :param token: 서버로 부터 수신한 토큰
        :return: 토큰 검증 결과
        """
        logging.debug("Current Token:%s", self.__token)
        if token == self.__token:
            logging.debug("Current Token is available")
            return True

        peer_pub = self.__peer_cert.public_key().public_bytes(encoding=serialization.Encoding.DER,
                                                              format=PublicFormat.SubjectPublicKeyInfo)

        return self.__verify_token(self.__peer_info, peer_pub, token)

    def __verify_token(self, peer_info, peer_pub, peer_token):
        date = self.get_token_time(peer_token)
        if date is None:
            logging.debug("Expired Token")
            return False

        token_sign = peer_token[18:]
        token_bytes = peer_info + date + peer_pub
        signature = bytes.fromhex(token_sign)

        return self.verify_data_with_publickey(public_key=self.__ca_cert.public_key(),
                                               data=token_bytes,
                                               signature=signature)

    def verify_new_peer(self, peer, peer_type):
        peer_info = b''.join([peer.peer_id.encode('utf-8'),
                              peer.target.encode('utf-8'),
                              peer.group_id.encode('utf-8')]) + bytes([peer_type])

        if peer.auth is None:
            logging.debug("New Peer Certificate is None")
            return False

        if peer.token is None:
            logging.debug("New Peer Token is None")
            return False

        peer_cert = x509.load_der_x509_certificate(bytes.fromhex(peer.auth), default_backend())
        peer_pub = peer_cert.public_key().public_bytes(encoding=serialization.Encoding.DER,
                                                       format=PublicFormat.SubjectPublicKeyInfo)

        return self.__verify_token(peer_info, peer_pub, peer.token)

    @property
    def is_secure(self):
        """
        보안설정 여부

        :return: 보안설정여부
        """
        return self.__peer_cert is not None and self.__peer_pri is not None

