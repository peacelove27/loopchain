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
"""Test Crypto functions"""

import base64
import datetime
import logging
import unittest

import OpenSSL
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa, padding
from cryptography.x509.oid import NameOID

import loopchain.utils as util
import testcase.unittest.test_util as test_util

util.set_log_level_debug()


class TestCrypto(unittest.TestCase):

    def setUp(self):
        test_util.print_testname(self._testMethodName)

    def tearDown(self):
        pass

    def test_ecc_key(self):
        """
        ECC 키쌍을 생성하여 인증서 생성, ECDSA 서명/검증 테스트
        """
        logging.debug("----- ECDSA Test Start -----")
        # 키쌍 생성
        pri_key = ec.generate_private_key(ec.SECP256K1(), default_backend())
        pub_key = pri_key.public_key()

        pri_der = pri_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            # encryption_algorithm=serialization.NoEncryption()
            encryption_algorithm=serialization.BestAvailableEncryption(password=b'qwer1234')
        )

        pub_der = pub_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        pri_b64 = base64.b64encode(pri_der, altchars=None)
        pub_b64 = base64.b64encode(pub_der, altchars=None)

        logging.debug("Private Key : \n%s", pri_b64)
        logging.debug("Public  Key : \n%s", pub_b64)

        # 인증서 생성
        cert = self._generate_cert(pub_key=pub_key, issuer_key=pri_key, subject_name="test")
        cert_key = cert.public_key()

        # ECDSA 서명 생성 및 검증 테스트
        data = b"test"
        signature = self._generate_sign(pri_key=pri_key, data=data)

        sign_b64 = base64.b64encode(signature, altchars=None)
        logging.debug("Sign : %s", sign_b64)

        validation_result = self._verify_signature(pub_key=cert_key, data=data, signature=signature)
        logging.debug("Verify : %s", validation_result)
        self.assertEqual(validation_result, True)

        # ECDSA 서명을 생성하는 다른 방법
        signature = pri_key.sign(
            data,
            ec.ECDSA(hashes.SHA256())
        )

        validation_result = self._verify_signature(pub_key=cert_key, data=data, signature=signature)
        logging.debug("----- ECDSA Test End -----\n")
        self.assertTrue(validation_result)

    def test_rsa_key(self):
        """
        RSA 키쌍을 생성하여 인증서 생성, RSA 서명/검증 테스트
        :return:
        """
        logging.debug("----- RSA Test Start -----")
        # 키 쌍 생성
        pri_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        pub_key = pri_key.public_key()

        pri_der = pri_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        pub_der = pub_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        pri_b64 = base64.b64encode(pri_der, altchars=None)
        pub_b64 = base64.b64encode(pub_der, altchars=None)

        logging.debug("Private Key : \n%s", pri_b64)
        logging.debug("Public  Key : \n%s", pub_b64)

        # 인증서 생성
        cert = self._generate_cert(pub_key=pub_key, issuer_key=pri_key, subject_name="test")
        cert_key = cert.public_key()

        # RSA 서명 생성 및 검증 테스트
        data = b"test"
        signature = self._generate_sign(pri_key=pri_key, data=data)
        sign_b64 = base64.b64encode(signature, altchars=None)
        logging.debug("Sign : %s", sign_b64)

        validation_result = self._verify_signature(pub_key=cert_key, data=data, signature=signature)

        logging.debug("----- RSA Test End -----\n")
        self.assertTrue(validation_result)

    def test_pkcs12_format(self):
        """
        PKCS12 형식으로 인증서/개인키 저장을 위한 코드
        """
        logging.debug("----- PKCS12 Test Start -----")
        # ECC 키 쌍 생성
        pri_key = ec.generate_private_key(ec.SECP256K1(), default_backend())
        pub_key = pri_key.public_key()

        logging.debug("Key_Type : %s", type(pri_key))

        # 인증서 생성
        cert = self._generate_cert(pub_key=pub_key, issuer_key=pri_key, subject_name="test")

        cert_pem = cert.public_bytes(
            encoding=serialization.Encoding.DER
        )
        key_pem = pri_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        # 인증서/개인키를 OpenSSL Key로 변환
        crypto = OpenSSL.crypto
        cert_ssl_key = crypto.load_certificate(
            type=crypto.FILETYPE_ASN1,
            buffer=cert_pem
        )
        priv_ssl_key = crypto.load_privatekey(
            type=crypto.FILETYPE_ASN1,
            buffer=key_pem,
            passphrase=None
        )

        logging.debug("Key_Type : %s", type(priv_ssl_key))

        # 변환한 인증서개인키를 PKCS12형식으로 변환
        p12 = OpenSSL.crypto.PKCS12()
        p12.set_privatekey(priv_ssl_key)
        p12.set_certificate(cert_ssl_key)
        pfx = p12.export()

        pfx_b64 = base64.b64encode(pfx, altchars=None)
        logging.debug("%s", pfx_b64)

    def _generate_cert(self, pub_key, issuer_key, subject_name):
        """
        서명용 인증서 생성

        :param pub_key: 공개키
        :param issuer_key: 인증서 생성용 발급자 개인키
        :param subject_name: 생성될 인증서 주체명
        :return: 인증서
        """
        builder = x509.CertificateBuilder()
        # 주체 이름 설정
        builder = builder.subject_name(
            x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, subject_name),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Theloop CA"),
                x509.NameAttribute(NameOID.COUNTRY_NAME, "kr")
            ])
        )

        # 발급자 이름 설정
        builder = builder.issuer_name(
            x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, subject_name),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Theloop CA"),
                x509.NameAttribute(NameOID.COUNTRY_NAME, "kr")
            ])
        )

        # 유효기간 설정
        builder = builder.not_valid_before(datetime.datetime.today())
        builder = builder.not_valid_after(datetime.datetime.today() + datetime.timedelta(1, 0, 0))

        # 인증서 일련번호 설정
        builder = builder.serial_number(1)

        # 공개키 설정
        builder = builder.public_key(pub_key)

        # 인증서 용도 설정(서명용)
        builder = builder.add_extension(
            x509.KeyUsage(digital_signature=True, content_commitment=True,
                          key_encipherment=False, data_encipherment=False, key_agreement=False,
                          key_cert_sign=False, crl_sign=False,
                          encipher_only=False, decipher_only=False),
            critical=True
        )

        # 인증서 생성(서명)
        cert = builder.sign(
            private_key=issuer_key,
            algorithm=hashes.SHA256(),
            backend=default_backend()
        )

        cert_der = cert.public_bytes(
            encoding=serialization.Encoding.DER
        )

        cert_b64 = base64.b64encode(cert_der, altchars=None)
        logging.debug("Certificate : %s", cert_b64)

        # 생성된 인증서에 포함된 서명을 추출하여 검증
        # 생성된 인증서는 Self-Signed 인증서이므로 인증서에 포함된 공개키를 이용하여 검증
        cert_sign = cert.signature
        cert_data = cert.tbs_certificate_bytes
        if self._verify_cert_signature(pub_key=cert.public_key(), data=cert_data, signature=cert_sign):
            logging.debug("Certificate Signature Validation Success")
        else:
            logging.debug("Certificate Signature Validation Fail")
            return None

        return cert

    def _generate_sign(self, pri_key, data):
        """
        서명 데이터 생성

        :param pri_key: 서명용 개인키
        :param data: 서명 원문 데이터
        :return: 생성된 서명 데이터
        """
        _signature = None
        # 개인키의 Type(RSA, ECC)에 따라 서명 방식 분리
        if isinstance(pri_key, ec.EllipticCurvePrivateKeyWithSerialization):
            # ECDSA 서명
            logging.debug("Sign ECDSA")

            signer = pri_key.signer(ec.ECDSA(hashes.SHA256()))
            signer.update(data)
            _signature = signer.finalize()
        elif isinstance(pri_key, rsa.RSAPrivateKeyWithSerialization):
            # RSA 서명
            logging.debug("Sign RSA")

            _signature = pri_key.sign(
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
        else:
            logging.debug("Unknown PrivateKey Type : %s", type(pri_key))

        return _signature

    def _verify_signature(self, pub_key, data, signature):
        """
        서명 데이터 검증

        :param pub_key: 검증용 공개키
        :param data: 서명 원문 데이터
        :param signature: 서명 데이터
        :return: 서명 검증 결과(True/False)
        """
        validation_result = False
        # 공개키의 Type(RSA, ECC)에 따라 검증 방식 분리
        if isinstance(pub_key, ec.EllipticCurvePublicKeyWithSerialization):
            # ECDSA 서명
            logging.debug("Verify ECDSA")

            try:
                pub_key.verify(
                    signature,
                    data,
                    ec.ECDSA(hashes.SHA256())
                )
                validation_result = True
            except InvalidSignature:
                logging.debug("InvalidSignature_ECDSA")
        elif isinstance(pub_key, rsa.RSAPublicKeyWithSerialization):
            # RSA 서명
            logging.debug("Verify RSA")

            try:
                pub_key.verify(
                    signature,
                    data,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
                validation_result = True
            except InvalidSignature:
                logging.debug('InvalidSignature_RSA')

        else:
            logging.debug("Unknown PublicKey Type : %s", type(pub_key))

        return validation_result

    def _verify_cert_signature(self, pub_key, data, signature):
        """
        인증서에 포함된 서명 검증

        :param pub_key: 인증서 발급자의 공개키
        :param data: 인증서 내의 서명 원문 데이터(TBSCertificate)
        :param signature: 인증서 내의 서명 데이터
        :return: 서명 검증 결과(True/False)
        """
        validation_result = False
        # 공개키의 Type(RSA, ECC)에 따라 검증 방식 분리
        # 인증서 서명의 경우 AlgorithmOID에 따라서 판단해야 하지만
        # 파이선 라이브러리에서 사용하는 알고리즘으로 고정
        if isinstance(pub_key, ec.EllipticCurvePublicKeyWithSerialization):
            # ECDSA 서명
            logging.debug("Verify ECDSA")

            try:
                pub_key.verify(
                    signature,
                    data,
                    ec.ECDSA(hashes.SHA256())
                )
                validation_result = True
            except InvalidSignature:
                logging.debug("InvalidSignature_ECDSA")
        elif isinstance(pub_key, rsa.RSAPublicKeyWithSerialization):
            # RSA 서명
            logging.debug("Verify RSA")

            try:
                # 데이터 서명할 때와는 Padding 방식이 다름
                pub_key.verify(
                    signature,
                    data,
                    padding.PKCS1v15(),
                    hashes.SHA256()
                )
                validation_result = True
            except InvalidSignature:
                logging.debug('InvalidSignature_RSA')

        else:
            logging.debug("Unknown PublicKey Type : %s", type(pub_key))

        return validation_result


if __name__ == '__main__':
    unittest.main()
