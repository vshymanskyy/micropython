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

class Base64Encoder:
    def __init__(self):
        self._d = bytearray()

    def encode(self, data):
        # Append new data to the buffer
        self._d.extend(data)

        # Calculate how many bytes can be encoded in this chunk (multiples of 3)
        l = len(self._d) // 3 * 3
        chunk = self._d[:l]

        # Store remaining bytes
        self._d = self._d[l:]

        return binascii.b2a_base64(chunk, newline=False)

    def finalize(self):
        if len(self._d):
            return binascii.b2a_base64(self._d, newline=False)
        return b""

class BinaryEncoder:
    def encode(self, data):
        return data
    def finalize(self):
        return b""

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
        enc = Base64Encoder()
    elif encoding == "raw":
        enc = BinaryEncoder()
    else:
        raise ValueError("encoding")

    bs = dev.ioctl(5, 0)  # block size
    buf = bytearray(bs)
    pos = 0
    while rem > 0:
        if (rem < len(buf)):
             buf = bytearray(rem)
        dev.readblocks(pos, buf)
        stream.write(enc.encode(buf))
        #stream.write(b"\n")
        pos += 1
        rem -= len(buf)
    stream.write(enc.finalize())
