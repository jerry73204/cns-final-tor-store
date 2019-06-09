import base64
import random

import asn1
import gmpy2
from Crypto.PublicKey import RSA
from stem.control import Controller


def store_block(data, data_len=100):
    # Generate RSA key pair
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

    return response.service_id


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


def forge_rsa_key(data: bytes, key_size=1024, data_size=800, nonce_size=200):
    assert nonce_size + data_size < key_size
    assert data_size / 8 == data_size // 8
    assert(len(data) == data_size // 8)

    # Generate RSA key with p = 11.
    # By Cramer's conjecture (which is likely to be true),
    #  the maximum prime gap for a 1024-bit number should be around 500000.
    # We choose a 800-bit data size and a 200-bit nonce, which allows a maximum
    #  gap of 2^(1023-1000)/11 ~ 760000 and a collision probability of ~2^(-100).
    # let the highest bit be 1
    while True:
        n_expect = 1 << (key_size - 1) | \
                int.from_bytes(data, 'little') << (key_size - 1 - data_size) | \
                random.getrandbits(nonce_size) << (key_size - 1 - data_size - nonce_size)
        while True:
            p = 11
            q = next_prime((n_expect - 1) // p + 1)
            n = p * q
            # final (paranoid) correctness check,
            #  should be true given the conjecture is true
            if (n >> (key_size - 1 - data_size)) == \
                    (n_expect >> (key_size - 1 - data_size)): break
        # Compute RSA components
        e = 65537
        d = int(gmpy2.invert(e, (p - 1) * (q - 1)))
        # Library reference
        # https://pycryptodome.readthedocs.io/en/latest/src/public_key/rsa.html
        # if get an invalid key (prob ~1/11), retry with another nonce
        try:
            key = RSA.construct((n, e, d), consistency_check=True)
        except ValueError:
            continue
        break

    # Tor accepts DER-encoded, then base64 encoded RSA key
    # https://github.com/torproject/tor/blob/a462ca7cce3699f488b5e2f2921738c944cb29c7/src/feature/control/control_cmd.c#L1968
    der = key.export_key('DER', pkcs=1)
    ret = str(base64.b64encode(der), 'ASCII')
    return ret


def load_block(block_id, data_len=61):
    url = '%s.union' % block_id

    with Controller.from_port() as controller:
        controller.authenticate()
        try:
            descriptor = str(controller.get_hidden_service_descriptor(url))
        except ValueError:
            return None

    print(descriptor)

    # b = descriptor[descriptor.find('BEGIN'):descriptor.find('END')]
    # c = descriptor[descriptor.find('BEGIN MESSAGE'):descriptor.find('END MESSAGE')]
    #print(x, a)
    # print(x, hashlib.sha256((b + c).encode()).hexdigest())


def data_from_public_key(n, key_size=1024, data_size=488):
    data_num = (n - (1 << (key_size - 1))) >> ((key_size - 1) - data_size)
    return data_num.to_bytes(data_size // 8, 'little')


def load_block(name: str):
    with Controller.from_port() as controller:
        controller.authenticate()
        a = str(controller.get_hidden_service_descriptor(name))
        public = a[a.find('PUBLIC KEY-----')+15:a.find('-----END')].replace('\n', '')
        decoder = asn1.Decoder()
        decoder.start(base64.b64decode(public))
        decoder.start(decoder.read()[1])
        data = data_from_public_key(decoder.read()[1])
        return data

def data_from_public_key(n, key_size=1024, data_size=800, nonce_size=200):
    data_num = (n - (1 << (key_size - 1))) >> (key_size - 1 - data_size)
    return data_num.to_bytes(data_size // 8, 'little')
