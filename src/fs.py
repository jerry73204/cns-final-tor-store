import os
import re
import shutil
from json import JSONEncoder, JSONDecoder
import multiprocessing as mp
import asyncio
import sys

from logzero import logger


class VFS:
    def __init__(self, data_size=800, replica_factor=1, max_workers=None, buf_size=2**30):
        assert data_size / 8 == data_size // 8
        self.re_slash = re.compile('/+')
        self.block_length = data_size // 8
        self.replica_factor = replica_factor
        self.buf_size = buf_size
        self.fs = dict()

        if max_workers is None:
            max_workers = mp.cpu_count() * 2

        self.queue = asyncio.Queue(maxsize=max_workers)

    def parse_path(self, path):
        path = self.re_slash.sub('/', path)
        tokens = path.split('/')

        normalized_tokens = list()

        for tk in tokens:
            if not tk:
                raise VFSError('Invalid path %s' % path)
            elif tk == '.':
                continue
            elif tk == '..':
                if normalized_tokens:
                    normalized_tokens.pop()
            else:
                normalized_tokens.append(tk)

        return normalized_tokens

    def traverse(self, path, tokens):
        parent_handle = self.fs
        handle = self.fs

        for tk in tokens:
            if isinstance(handle, FileHandle):
                raise VFSError('%s is not a file or directory' % path)
            elif tk not in handle:
                raise VFSError('%s is not a file or directory' % path)
            else:
                parent_handle = handle
                handle = handle[tk]

        return parent_handle, handle

    def list(self, path):
        tokens = self.parse_path(path)
        parent_handle, handle = self.traverse(path, tokens)

        if isinstance(handle, FileHandle):
            return [path]
        else:
            assert isinstance(handle, dict)
            return list(handle.keys())

    def find(self, path):
        tokens = self.parse_path(path)
        parent_handle, handle = self.traverse(path, tokens)

        def recursive_list(prefix, h):
            if isinstance(h, FileHandle):
                return [prefix]
            else:
                assert isinstance(h, dict)
                ret = [prefix]
                for name, child in h.items():
                    child_path = '%s/%s' % (prefix, name)
                    ret += recursive_list(child_path, child)
                return ret

        result = recursive_list(path, handle)
        return result

    def touch(self, path):
        tokens = self.parse_path(path)
        parent_handle, handle = self.traverse(path, tokens[:-1])

        if isinstance(handle, FileHandle):
            raise VFSError('%s is not valid' % path)
        elif tokens[-1] not in handle:
            handle[tokens[-1]] = FileHandle(
                block_length=self.block_length,
                replica_factor=self.replica_factor,
                queue=self.queue,
            )

    def mkdir(self, path):
        tokens = self.parse_path(path)
        parent_handle, handle = self.traverse(path, tokens[:-1])

        if isinstance(handle, FileHandle):
            raise VFSError('%s is not valid' % path)
        elif tokens[-1] in handle:
            raise VFSError('%s already exists' % path)
        else:
            handle[tokens[-1]] = dict()

    def remove(self, path, recursive=False):
        tokens = self.parse_path(path)
        parent_handle, handle = self.traverse(path, tokens)

        if not recursive and isinstance(handle, dict):
            raise VFSError('%s is not a file' % path)

        if tokens:
            parent_handle.pop(tokens[-1], None)
        else:
            self.fs = dict()

    async def copy(self, from_path, to_path):
        from_outer = False
        if from_path[0] == '@':
            from_path = from_path[1:]
            from_outer = True
        else:
            from_tokens = self.parse_path(from_path)
            _, from_handle = self.traverse(from_path, from_tokens)
            if not isinstance(from_handle, FileHandle):
                raise VFSError('Cannot copy from %s' % from_path)

        to_outer = False
        if to_path[0] == '@':
            to_path = to_path[1:]
            to_outer = True
        else:
            to_tokens = self.parse_path(to_path)
            _, to_parent_handle = self.traverse(to_path, to_tokens[:-1])
            if not isinstance(to_parent_handle, dict):
                raise VFSError('Cannot copy to %s' % to_path)

            to_handle = FileHandle(
                block_length=self.block_length,
                replica_factor=self.replica_factor,
                queue=self.queue,
            )
            to_parent_handle[to_tokens[-1]] = to_handle

        if from_outer:
            if to_outer:
                shutil.copyfile(from_path, to_path)
            else:
                with open(from_path, 'rb') as from_file:
                    offset = 0
                    while True:
                        buf = from_file.read(self.buf_size)
                        if not buf:
                            break
                        await to_handle.write(offset, buf)
                        offset += len(buf)

        else:
            if to_outer:
                with open(to_path, 'wb') as to_file:
                    for offset in range(0, from_handle.file_length, self.buf_size):
                        buf = await from_handle.read(offset, self.buf_size)
                        if not buf:
                            raise VFSError('Unexpected EOF')
                        to_file.write(buf)
            else:
                for offset in range(0, from_handle.file_length, self.buf_size):
                    buf = await from_handle.read(offset, self.buf_size)
                    await to_handle.write(offset, buf)

    def stat(self, path):
        tokens = self.parse_path(path)
        _, handle = self.traverse(path, tokens)

        if isinstance(handle, FileHandle):
            return {
                'type': 'file',
                'size': handle.file_length,
                'tor_addresses': handle.block_store,
            }
        else:
            assert isinstance(handle, dict)
            return {
                'type': 'directory',
            }

    def open(self, path):
        tokens = self.parse_path(path)
        _, handle = self.traverse(path, tokens)

        if not isinstance(handle, FileHandle):
            raise VFSError('%s is not a file' % path)

        return handle


class FileHandle:
    def __init__(self, block_length, queue, replica_factor=1):
        self.block_length = block_length
        self.replica_factor = replica_factor
        self.block_store = dict()
        self.file_length = 0
        self.queue = queue
        self.tor_helper_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'tor_helper.py',
        )

    async def load_block(self, index, check_boundary=True):
        logger.debug('load_block(%d, check_consistency=%d)', index, check_boundary)
        assert index >= 0

        if index in self.block_store:
            # Load from one of its replica
            for addr in self.block_store[index]:
                logger.info('Loading replica from Onion address %s.onion', addr)
                await self.queue.put(None)  # Constraint # of concurrent workers
                proc = await asyncio.create_subprocess_exec(
                    sys.executable,
                    self.tor_helper_path,
                    'load',
                    '1024',
                    '800',
                    '200',
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                )
                proc.stdin.write(bytes('%s\n' % addr, 'ASCII'))
                block = await proc.stdout.read(100)
                await proc.wait()
                await self.queue.get()

                if block:
                    assert len(block) == self.block_length
                    return block
                else:
                    logger.warning('Failed to load replica from Onion address %s.onion', addr)

            raise VFSError("Fail to load block at index %d" % index)

        elif check_boundary:
            raise VFSError("Index out of bound")

        else:
            return b'\x00' * self.block_length

    async def store_block(self, index, block):
        logger.debug('store_block(%d, ..)', index)
        assert index >= 0 and len(block) <= self.block_length

        # Pad block
        if len(block) < self.block_length:
            block = block + b'\x00' * (self.block_length - len(block))

        futures = list()
        processes = list()

        for replica_index in range(self.replica_factor):
            logger.info('Storing replica %d/%d for block index %d', replica_index + 1, self.replica_factor, index)

            await self.queue.put(None)  # Constraint # of concurrent workers
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                self.tor_helper_path,
                'store',
                '1024',
                '800',
                '200',
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
            )
            proc.stdin.write(block)
            addr_future = proc.stdout.readline()
            futures.append((proc, addr_future))

        addresses = list()
        for proc, addr_future in futures:
            addr = str(await addr_future, 'ASCII')[:-1]  # Strip '\n'
            addresses.append(addr)
            await proc.wait()
            await self.queue.get()

        self.block_store[index] = addresses

    async def read(self, offset, length):
        begin_offset = offset
        end_offset = offset + length

        # Sanitize boundary
        if begin_offset >= self.file_length:
            return b''

        if end_offset > self.file_length:
            end_offset = self.file_length

        begin_index = begin_offset // self.block_length
        end_index = end_offset // self.block_length

        has_front = begin_offset / self.block_length != begin_index
        has_tail = end_offset / self.block_length != end_index

        # Single block case
        if begin_index == end_index:
            block = await self.load_block(begin_index)
            front_strip = begin_offset - self.block_length * begin_index
            tail_strip = self.block_length * (end_index + 1) - end_offset
            return block[front_strip:-tail_strip] if tail_strip > 0 \
                else block[front_strip:]

        # Load first block
        if has_front:
            block = await self.load_block(begin_index)
            front_length = self.block_length * (begin_index + 1) - begin_offset
            assert front_length > 0
            front_block = block[:-front_length]
            begin_index += 1
        else:
            front_block = b''

        # Load last block
        if has_tail:
            block = await self.load_block(end_index)
            tail_length = end_offset - self.block_length * end_index
            assert tail_length > 0
            tail_block = block[:tail_length]
        else:
            tail_block = b''

        # Load intermediate blocks
        data = front_block

        for index in range(begin_index, end_index):
            block = await self.load_block(index)
            data += block

        data += tail_block
        return data

    async def write(self, offset, data):
        length = len(data)
        begin_offset = offset
        end_offset = offset + length

        # Update file size
        if end_offset > self.file_length:
            self.file_length = end_offset

        begin_index = begin_offset // self.block_length
        end_index = end_offset // self.block_length

        has_front = begin_offset / self.block_length != begin_index
        has_tail = end_offset / self.block_length != end_index

        # Single block case
        if begin_index == end_index:
            block = await self.load_block(begin_index, check_boundary=False)
            front_strip = begin_offset - begin_index * self.block_length
            tail_strip = self.block_length - (front_strip + self.block_length)
            front_block = block[:front_strip]
            tail_block = block[-tail_strip:] if tail_strip > 0 else b''
            new_block = front_block + data + tail_block
            await self.store_block(begin_index, new_block)
            return

        # Store blocks asynchrnously
        futures = list()

        # Update first block
        if has_front:
            block = await self.load_block(begin_index, check_boundary=False)
            front_length = self.block_length * (begin_index + 1) - begin_offset
            assert front_length > 0

            new_block = block[:-front_length] + data[:front_length]
            future = self.store_block(begin_index, new_block)
            futures.append(future)
            begin_index += 1
        else:
            front_length = 0

        # Update last block
        if has_tail:
            block = await self.load_block(end_index, check_boundary=False)
            tail_length = end_offset - self.block_length * end_index
            assert tail_length > 0

            new_block = data[-tail_length:] + block[tail_length:]
            future = self.store_block(end_index, new_block)
            futures.append(future)
        else:
            tail_length = 0

        # Update intermediate blocks
        for index in range(begin_index, end_index):
            begin_data_offset = front_length + self.block_length * (index - begin_index)
            end_data_offset = begin_data_offset + self.block_length

            new_block = data[begin_data_offset:end_data_offset]
            future = self.store_block(index, new_block)
            futures.append(future)

        await asyncio.gather(*futures)


class VFSError(Exception):
    pass


class VFSJsonEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, VFS):
            return self.serialize_vfs(obj)
        elif isinstance(obj, FileHandle):
            return self.serialize_filehandle(obj)
        else:
            return super(VFSJsonEncoder, self).default(obj)

    def serialize_vfs(self, obj):
        assert isinstance(obj, VFS)

        def recursive_serialize_handle(handle):
            if isinstance(handle, FileHandle):
                return self.serialize_filehandle(handle)
            else:
                assert isinstance(handle, dict)
                result = dict()
                for name, child in handle.items():
                    result[name] = recursive_serialize_handle(child)
                return result

        fs_obj = recursive_serialize_handle(obj.fs)
        result = {
            '_type': 'VFS',
            'block_length': obj.block_length,
            'replica_factor': obj.replica_factor,
            'buf_size': obj.buf_size,
            'fs': fs_obj,
        }
        return result

    def serialize_filehandle(self, obj):
        result = {
            '_type': 'FileHandle',
            'block_length': obj.block_length,
            'replica_factor': obj.replica_factor,
            'file_length': obj.file_length,
            'block_store': obj.block_store,
        }
        return result


class VFSJsonDecoder(JSONDecoder):
    def __init__(self, *args, **kargs):
        JSONDecoder.__init__(self, object_hook=self.object_hook, *args, **kargs)

    def object_hook(self, obj):
        if '_type' not in obj:
            return obj

        type_ = obj['_type']

        if type_ == 'VFS':
            vfs = VFS()
            vfs.block_length = obj['block_length']
            vfs.replica_factor = obj['replica_factor']
            vfs.buf_size = obj['buf_size']

            def recursive_deserialize_handle(handle):
                if isinstance(handle, FileHandle):
                    handle.queue = vfs.queue
                    return handle
                else:
                    assert isinstance(handle, dict)
                    result = dict()
                    for name, child in handle.items():
                        result[name] = recursive_deserialize_handle(child)

                    return result

            vfs.fs = recursive_deserialize_handle(obj['fs'])
            return vfs

        elif type_ == 'FileHandle':
            return self.decode_filehandle(obj)

        return obj

    def decode_filehandle(self, obj):
        dummy_queue = None
        handle = FileHandle(obj['block_length'], dummy_queue, replica_factor=obj['replica_factor'])
        handle.file_length = obj['file_length']

        block_store = dict()
        for index, replicas in obj['block_store'].items():
            block_store[int(index)] = replicas

        handle.block_store = block_store
        return handle
