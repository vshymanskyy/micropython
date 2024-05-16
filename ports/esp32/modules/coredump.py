# SPDX-FileCopyrightText: 2024 Volodymyr Shymanskyy for Blynk Technologies Inc.
# SPDX-License-Identifier: Apache-2.0
#
# The software is provided "as is", without any warranties or guarantees (explicit or implied).
# This includes no assurances about being fit for any specific purpose.
#
# Simulate crash:   mpremote exec "import machine; machine.WDT(timeout=100)"
# Print coredump:   mpremote exec "import coredump; coredump.dump()" > crash.b64
# Decode:           espcoredump.py info_corefile -d 3 -c b64 -c crash.b64 -rom-elf micropython.elf > crash.log

__copyright__ = "2024 Volodymyr Shymanskyy for Blynk Technologies Inc."
__license__ = "Apache-2.0"

from esp32 import Partition
import struct, binascii

SUBTYPE_COREDUMP = 0x03

dev = Partition.find(type=Partition.TYPE_DATA, subtype=SUBTYPE_COREDUMP)
dev = dev[0] if dev else None

class Splitter:
    def __init__(self, stream, width=120):
        self._s = stream
        self._w = width
        self._b = bytearray(self._w)
        self._p = 0

    def write(self, data):
        data_len = len(data)
        data_pos = 0

        while data_pos < data_len:
            # Calculate how much data to copy into the buffer
            l = min(data_len - data_pos, self._w - self._p)
            self._b[self._p:self._p + l] = data[data_pos:data_pos + l]
            self._p += l
            data_pos += l
            # If buffer is full, write it
            if self._p == self._w:
                self._s.write(self._b[:self._p])
                self._s.write(b"\n")
                self._p = 0

    def flush(self):
        if self._p > 0:
            self._s.write(self._b[:self._p])
            self._p = 0
        self._s.flush()

class Base64Encoder:
    def __init__(self, stream):
        self._d = bytearray()
        self._s = stream

    def write(self, data):
        # Append new data to the buffer
        self._d.extend(data)

        # Calculate how many bytes can be encoded in this chunk (multiples of 3)
        l = len(self._d) // 3 * 3
        if l:
            chunk = self._d[:l]
            self._d = self._d[l:]
            self._s.write(binascii.b2a_base64(chunk, newline=0))

    def flush(self):
        if len(self._d):
            self._s.write(binascii.b2a_base64(self._d, newline=0))
            self._d = bytearray()
        self._s.flush()

def available():
    if not dev:
        return 0
    buf = bytearray(8)
    dev.readblocks(0, buf)
    sz, ver = struct.unpack("<II", buf)
    part_size = dev.info()[3]
    if sz > part_size:
        return 0
    return sz

def erase():
    if dev:
        ret = dev.ioctl(6, 0) # Erase block 0
        if ret != 0:
            raise OSError(ret)

def dump(stream=None, encoding=None):
    if not stream:
        import sys
        stream = sys.stdout

    rem = available()
    if not rem:
        stream.write(b"No coredump found\n")
        return

    if not encoding or encoding == "b64":
        stream = Base64Encoder(Splitter(stream))
    elif encoding == "raw":
        pass
    else:
        raise ValueError("encoding")

    bs = dev.ioctl(5, 0)  # block size
    buf = bytearray(bs)
    pos = 0
    while rem > 0:
        if (rem < len(buf)):
             buf = bytearray(rem)
        dev.readblocks(pos, buf)
        stream.write(buf)
        pos += 1
        rem -= len(buf)
    stream.flush()
