#!/usr/bin/env python3
import argparse
import os, sys
import shutil
import base64
import random

import gmpy2
import asn1
from Crypto.PublicKey import RSA
from stem.control import Controller


def main(name):
    controller = Controller.from_port()
    controller.authenticate()
    a = str(controller.get_hidden_service_descriptor(name))
    public = a[a.find('PUBLIC KEY-----')+15:a.find('-----END')].replace('\n', '')
    decoder = asn1.Decoder()
    decoder.start(base64.b64decode(public))
    decoder.start(decoder.read()[1])
    data = data_from_public_key(decoder.read()[1])
    print(base64.b64encode(data).decode())

DATA_LEN = 800
NONCE_LEN = 200
KEY_LEN = 1024

def data_from_public_key(n):
    data_num = (n - (1 << (KEY_LEN - 1))) >> (KEY_LEN - 1 - DATA_LEN)
    return data_num.to_bytes(DATA_LEN // 8, 'little')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(sys.argv[0], '[hidden service name]')
        sys.exit(1)
    main(sys.argv[1])
