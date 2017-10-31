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

import sys
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def main(argv):
    if len(argv) > 0:
        password = argv[0].encode()
    else:
        password = b'test'

    private_key = ec.generate_private_key(ec.SECP256K1(), default_backend())
    serialized_private = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(password)
    )

    serialized_public = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    private_key = serialization.load_der_private_key(serialized_private, password, default_backend())

    with open('resources/default_pki/private.der', 'wb') as private_file:
        private_file.write(serialized_private)

    with open('resources/default_pki/public.der', 'wb') as public_file:
        public_file.write(serialized_public)

    print('save pki in : resources/default_pki/')


if __name__ == "__main__":
    main(sys.argv[1:])
