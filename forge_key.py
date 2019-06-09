#!/usr/bin/env python3
import argparse
import os
import shutil
import base64
import random

import gmpy2
from Crypto.PublicKey import RSA
from stem.control import Controller


def main():
    arg_parser = argparse.ArgumentParser()
    args = arg_parser.parse_args()

    # Generate RSA key pair
    data_len = 61
    data = random.getrandbits(data_len * 8).to_bytes(data_len, 'little')
    key = forge_rsa_key(data)

    # Public hidden service
    with Controller.from_port() as controller:
        controller.authenticate()
        response = controller.create_ephemeral_hidden_service(
            {80: 5000},
            await_publication=True,
            key_type='RSA1024',
            key_content=key,
        )
        print(response.service_id)

def crypto_prime(num):
    i = 2
    for x in range(64): # 2^(-128) false
        if not gmpy2.is_strong_prp(num, i): return False
        i = gmpy2.next_prime(i)
    return True

def next_prime(num):
    while True:
        num = gmpy2.next_prime(num)
        # ensure a sufficient is-prime confidence
        if crypto_prime(num): return int(num)

DATA_LEN = 488

def forge_rsa_key(data: bytes, key_size = 1024):
    # By Cramer's conjecture (which is likely to be true),
    #  the maximum prime gap for a 512-bit number should be around 10**5.
    #  Thus, we choose 488-bit for our data size, which allows a maximum
    #  gap of 2^(511-488) ~ 5*10**6.
    # There is no need of a nonce, since there is enough randomness in the
    #  chosen prime factor.
    assert(len(data) == DATA_LEN // 8)
    # let the highest bit be 1
    n_expect = 1 << 1023 | int.from_bytes(data, 'little') << (1023 - DATA_LEN)
    while True:
        p = next_prime(random.getrandbits(512))
        q = next_prime((n_expect - 1) // p + 1)
        n = p * q
        # final (paranoid) correctness check,
        #  should be true given the conjecture is true
        if (n >> (1023 - DATA_LEN)) == (n_expect >> (1023 - DATA_LEN)): break
        print('meow')

    # Compute RSA components
    e = 65537
    d = int(gmpy2.invert(e, (p - 1) * (q - 1)))

    # Library reference
    # https://pycryptodome.readthedocs.io/en/latest/src/public_key/rsa.html
    key = RSA.construct(
        (n, e, d),
        consistency_check=True,
    )

    # Tor accepts DER-encoded, then base64 encoded RSA key
    # https://github.com/torproject/tor/blob/a462ca7cce3699f488b5e2f2921738c944cb29c7/src/feature/control/control_cmd.c#L1968
    der = key.export_key('DER', pkcs=1)
    ret = str(base64.b64encode(der), 'ASCII')
    return ret

def data_from_public_key(n):
    data_num = (n - (1 << 1023)) >> (1023 - DATA_LEN)
    return data_num.to_bytes(DATA_LEN // 8, 'little')

if __name__ == '__main__':
    main()
