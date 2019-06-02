#!/usr/bin/env python3
import argparse
import os
import shutil

from Crypto.PublicKey import RSA
from stem.control import Controller


def main():
    arg_parser = argparse.ArgumentParser()
    # arg_parser.add_argument('--service-dir', required=True)
    args = arg_parser.parse_args()


    # TODO How to publish hidden service without setting exact service?
    # with Controller.from_port() as controller:
    #     controller.authenticate()
    #     response = controller.create_ephemeral_hidden_service(
    #         {80: 5000},
    #         await_publication=True,
    #         key_type='RSA1024',
    #         key_content='RSA1024',
    #     )
    #     print(response.service_id)


def forge_rsa_key(data: bytes, size=1024):
    n = int.from_bytes(data, 'little')
    e = 65537
    assert n < 2 ** 1024

    key = RSA.construct(
        (n, e),
        consistency_check=False,
    )
    der = key.export_key('DER')
    return der


if __name__ == '__main__':
    main()
