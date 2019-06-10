#!/usr/bin/env python3
import argparse
import readline
import os
import atexit
import json
import pprint
import asyncio

import logzero

import fs


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--histfile', default='.torfs_history')
    parser.add_argument('--vfs', default='.torfs_vfs')

    args = parser.parse_args()

    # Configure logger
    if 'LOGLEVEL' in os.environ:
        logzero.loglevel(os.environ['LOGLEVEL'])

    # Configure readline
    try:
        readline.read_history_file(args.histfile)
    except FileNotFoundError:
        pass

    readline.parse_and_bind('tab: complete')
    atexit.register(readline.write_history_file, args.histfile)

    # Load saved file system
    if os.path.isfile(args.vfs):
        with open(args.vfs, 'r') as file_vfs:
            vfs = json.load(file_vfs, cls=fs.VFSJsonDecoder)
    else:
        vfs = fs.VFS()

    open_files = dict()
    fd_count = 0

    # Serve user commands
    while True:
        try:
            command = input('torfs> ')
        except EOFError:
            break
        except KeyboardInterrupt:
            print()
            continue

        tokens = command.split()
        program = tokens[0]

        try:
            if program == 'ls':
                if len(tokens) > 2:
                    print('Invalid arguments')
                    continue

                if len(tokens) == 2:
                    path = tokens[1]
                else:
                    path = '.'

                for name in vfs.list(path):
                    print(name)

            elif program == 'find':
                if len(tokens) > 2:
                    print('Invalid arguments')
                    continue

                if len(tokens) == 2:
                    path = tokens[1]
                else:
                    path = '.'

                for name in vfs.find(path):
                    print(name)

            elif program == 'touch':
                if len(tokens) != 2:
                    print('Invalid arguments')
                    continue

                path = tokens[1]
                vfs.touch(path)

            elif program == 'mkdir':
                if len(tokens) != 2:
                    print('Invalid arguments')
                    continue

                path = tokens[1]
                vfs.mkdir(path)

            elif program == 'rm':
                if len(tokens) != 2:
                    print('Invalid arguments')
                    continue

                path = tokens[1]
                vfs.remove(path)

            elif program == 'rmdir':
                if len(tokens) != 2:
                    print('Invalid arguments')
                    continue

                path = tokens[1]
                vfs.remove(path, recursive=True)

            elif program == 'cp':
                if len(tokens) != 3:
                    print('Invalid arguments')
                    continue

                from_path = tokens[1]
                to_path = tokens[2]
                await vfs.copy(from_path, to_path)

            elif program == 'stat':
                if len(tokens) != 2:
                    print('Invalid arguments')
                    continue

                path = tokens[1]
                file_stat = vfs.stat(path)
                pprint.pprint(file_stat)

            elif program == 'open':
                if len(tokens) != 2:
                    print('Invalid arguments')
                    continue

                path = tokens[1]
                fp = vfs.open(path)
                open_files[fd_count] = fp
                print('fd = %d' % fd_count)
                fd_count += 1

            elif program == 'fd':
                if len(tokens) != 1:
                    print('"fd" command has no arguments')
                    continue

                for fd in open_files.keys():
                    print(fd)

            elif program == 'close':
                if len(tokens) != 2:
                    print('Invalid arguments')
                    continue

                try:
                    fd = int(tokens[1])
                except ValueError:
                    print('Invalid arguments')
                    continue

                if fd not in open_files:
                    print('Invalid arguments')

                open_files.remove(fd)

            elif program == 'read':
                if len(tokens) != 4:
                    print('Invalid arguments')
                    continue

                try:
                    fd = int(tokens[1])
                    offset = int(tokens[2])
                    length = int(tokens[3])
                except ValueError:
                    print('Invalid arguments')
                    continue

                if fd not in open_files:
                    print('Invalid arguments')
                    continue

                fp = open_files[fd]
                buf = await fp.read(offset, length)
                print(buf)

            elif program == 'write':
                if len(tokens) != 4:
                    print('Invalid arguments')
                    continue

                try:
                    fd = int(tokens[1])
                    offset = int(tokens[2])
                    data = eval(tokens[3])
                except ValueError:
                    print('Invalid arguments')
                    continue

                if isinstance(data, bytes):
                    print('Invalid arguments')
                    continue

                if fd not in open_files:
                    print('Invalid arguments')
                    continue

                fp = open_files[fd]
                buf = await fp.write(offset, data)

            elif program == 'exit':
                exit(0)

            elif program == 'help':
                if len(tokens) != 1:
                    print('"help" command has no arguments')
                    continue

                print(r'''ls [PATH]
    List directory.

find [PATH]
    Recursively list files and directories.

touch PATH
    Create empty file.

mkdir PATH
    Create directory.

rm PATH
    Delete file.

rmdir PATH
    Recursively delete directory.


cp FROM_PATH TO_PATH
    Copy files.
    If FROM_PATH or TO_PATH is prefixed with '@', it indicates
    the path on host. For example, "cp @from.jpg to.jpg" reads
    "from.jpg" from host, and copies to "to.jpg" in TorFS.

stat PATH
    Show file information.

open PATH
    Open a file in TorFS and allocate a file descriptor.

fd
    List open files.

close FD
    Close a file descriptor.

read FD OFFSET LENGTH
    Read data with LENGTH in size starting from OFFSET on FD.

write FD OFFSET DATA
    Write data starting from OFFSET on FD. The DATA is encoded
    in Python bytes representation (b'\x00\x01...').
''')

            else:
                print('Invalid command')

        except fs.VFSError as e:
            print('Error:', e)

    # Save file system state
    with open(args.vfs, 'w') as file_vfs:
        json.dump(vfs, file_vfs, cls=fs.VFSJsonEncoder)


if __name__ == '__main__':
    asyncio.run(main())
