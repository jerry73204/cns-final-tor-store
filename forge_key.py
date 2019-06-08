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
    # arg_parser.add_argument('--service-dir', required=True)
    args = arg_parser.parse_args()

    data = random.getrandbits(31 * 8).to_bytes(31, 'little')
    key = forge_rsa_key(data)

    # TODO How to publish hidden service without setting exact service?
    with Controller.from_port() as controller:
        controller.authenticate()
        response = controller.create_ephemeral_hidden_service(
            {80: 5000},
            await_publication=True,
            key_type='RSA1024',
            key_content=key,
        )
        print(response.service_id)


def forge_rsa_key(data: bytes, key_size=1024, data_size=254):
    prime_size = key_size // 2                # Size of p and q
    assert (data_size + 2) <= prime_size      # Reserve MSB and LSB bits
    assert len(data) * 8 <= data_size         # Data size sanity check
    data = int.from_bytes(data, 'little')

    while True:
        # Generate random p. Set LSB and MSB to 1
        p = random.getrandbits(prime_size) | (2 ** (prime_size - 1) + 1)
        if not gmpy2.is_strong_prp(p, 2):
            continue

        # q suffix, or lower bits of q, are derived from data and p
        # q prefix, or higher bits of q, are randomly selected
        q_suffix_size = data_size + 1
        q_prefix_size = prime_size - q_suffix_size

        m = 2 ** q_suffix_size
        p_inv = int(gmpy2.invert(p, m))
        q_suffix = (((data << 1) | 1) * p_inv) % m
        assert (q_suffix & 1) == 1

        # Generate random q prefix and run prime test
        found = False
        for _ in range(1024):
            q_prefix = random.getrandbits(q_prefix_size) | (2 ** (q_prefix_size - 1))
            q = (q_prefix << q_suffix_size) | q_suffix

            if gmpy2.is_strong_prp(q, 2):
                found = True
                break

        if found:
            break

    n = p * q
    e = 65537
    d = int(gmpy2.invert(e, (p - 1) * (q - 1)))

    # Test correctness
    recovered_data = (n >> 1) & (2 ** data_size - 1)
    assert gmpy2.is_strong_prp(p, 2) and gmpy2.is_strong_prp(q, 2)
    assert data == recovered_data
    # print('p', bin(p))
    # print('q', bin(q))
    # print('n', bin(p * q))
    # print('d', bin(data))
    # print('r', bin(recovered_data))
    # print('d', bin(data))

    key = RSA.construct(
        (n, e, d),
        consistency_check=True,
    )
    der = key.export_key('DER')
    ret = base64.b64encode(der)
    return ret


if __name__ == '__main__':
    main()
