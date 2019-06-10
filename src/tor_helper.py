#!/usr/bin/env python3
import argparse
import sys
import os

import logzero

import tor_utils


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('COMMAND', choices=['store', 'load'])
    parser.add_argument('KEY_SIZE', type=int)
    parser.add_argument('DATA_SIZE', type=int)
    parser.add_argument('NONCE_SIZE', type=int)
    args = parser.parse_args()

    # Configure logger
    if 'LOGLEVEL' in os.environ:
        logzero.loglevel(os.environ['LOGLEVEL'])

    # Parse arguments
    data_length = args.DATA_SIZE // 8
    assert args.DATA_SIZE / 8 == data_length

    if args.COMMAND == 'load':
        addr = input()
        block = tor_utils.load_block(
            addr,
            key_size=args.KEY_SIZE,
            data_size=args.DATA_SIZE,
            nonce_size=args.NONCE_SIZE,
        )
        if block is not None:
            sys.stdout.buffer.write(block)
        else:
            exit(1)

    elif args.COMMAND == 'store':
        block = sys.stdin.buffer.read(data_length)
        addr = tor_utils.store_block(
            block,
            key_size=args.KEY_SIZE,
            data_size=args.DATA_SIZE,
            nonce_size=args.NONCE_SIZE,
        )
        if addr is not None:
            print(addr)
        else:
            exit(1)

    else:
        raise ValueError('Command %s is not understood' % args.COMMAND)


if __name__ == '__main__':
    main()
