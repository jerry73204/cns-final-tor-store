import re
import tor_utils


class VFS:
    def __init__(self, data_size=800, replica_factor=3):
        assert data_size / 8 == data_size // 8
        self.fs = dict()
        self.re_slash = re.compile('/+')
        self.block_size = data_size // 8
        self.replica_factor = replica_factor

    def open(self, path):
        path = self.re_slash.sub('/', path)
        tokens = path.split('/')
        handle = self.fs

        for tk in tokens[:-1]:
            if not tk:
                raise ValueError('Invalid path %s' % path)
            handle = handle.get(tk, dict())
            if not isinstance(handle, dict):
                raise ValueError('%s is not valid' % path)

        default_file_handle = FileHandle(
            block_size=self.block_size,
            replica_factor=self.replica_factor,
        )
        file_handle = handle.get(tokens[-1], default_file_handle)
        return file_handle


class FileHandle:
    def __init__(self, block_size, replica_factor):
        self.block_size = block_size
        self.replica_factor = replica_factor
        self.block_store = dict()

    def load_block(self, index, check_boundary=True):
        assert index >= 0

        if index in self.block_store:
            # Load from one of its replica
            for addr in self.block_store[index]:
                block = tor_utils.load_block(addr)
                if block is not None:
                    return block

            # Fail
            raise ValueError("Fail to load block at index %d" % index)

        elif check_boundary:
            raise ValueError("Index out of bound")

        else:
            return b'\x00' * self.block_size

    def store_block(self, index, block):
        assert index >= 0

        addresses = list()
        for _ in range(self.replica_factor):
            addr = tor_utils.store_block(block, self.block_size)
            addresses.append(addr)

        self.block_store[index] = addresses

    def read(self, offset, length):
        begin_offset = offset
        end_offset = offset + length

        begin_index = begin_offset // self.block_size
        end_index = end_offset // self.block_size

        # Load first block
        if begin_offset / self.block_size != begin_index:
            block = self.load_block(begin_index)
            front_length = self.block_size * (begin_index + 1) - begin_offset
            assert front_length > 0
            front_block = block[:-front_length]
            begin_index += 1
        else:
            front_length = 0
            front_block = b''

        # Load last block
        if end_offset / self.block_size != end_index:
            block = self.load_block(end_index)
            tail_length = self.block_size * (end_index) - end_offset
            assert tail_length > 0
            tail_block = block[:tail_length]
        else:
            tail_length = 0
            tail_block = b''

        # Load intermediate blocks
        data = front_block

        for index in range(begin_index, end_index):
            block = self.load_block(index)
            data += block

        data += tail_block
        return data

    def write(self, offset, data):
        length = len(data)
        begin_offset = offset
        end_offset = offset + length

        begin_index = begin_offset // self.block_size
        end_index = end_offset // self.block_size

        # Update first block
        if begin_offset / self.block_size != begin_index:
            block = self.load_block(begin_index)
            front_length = self.block_size * (begin_index + 1) - begin_offset
            assert front_length > 0

            new_block = block[:-front_length] + data[:front_length]
            self.store_block(begin_index, new_block)
            begin_index += 1
        else:
            front_length = 0

        # Update last block
        if end_offset / self.block_size != end_index:
            block = self.load_block(end_index)
            tail_length = self.block_size * (end_index) - end_offset
            assert tail_length > 0

            new_block = data[-tail_length:] + block[:tail_length]
            self.store_block(end_index, new_block)
        else:
            tail_length = 0

        # Update intermediate blocks
        for index in range(begin_index, end_index):
            begin_data_offset = front_length + self.block_size * (index - begin_index)
            end_data_offset = begin_data_offset + self.block_size

            new_block = data[begin_data_offset:end_data_offset]
            self.store_block(index, new_block)
