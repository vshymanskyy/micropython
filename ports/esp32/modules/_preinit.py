
### SYS PATH

import sys
sys.path = ["", "/lib", ".frozen"]

### LOG

import time

#print(time.ticks_ms(), "Set up logging")

import logging

_lvlfmt = {
    logging.CRITICAL: ("C", "\033[31m"),
    logging.ERROR:    ("E", "\033[91m"),
    logging.WARNING:  ("W", "\033[93m"),
    logging.INFO:     ("I", ""),
    logging.DEBUG:    ("D", "\033[38;5;248m"),
}
_lvlfmt.setdefault((" ", ""))

class LogFormatter:
    def format(self, r):
        lvl, fmt = _lvlfmt[r.levelno]
        return f"{fmt}{time.ticks_ms():6d} {lvl} {r.name:12s} {r.message}\033[0m"

lh = logging.StreamHandler()
lh.setLevel(logging.DEBUG)
lh.setFormatter(LogFormatter())
log = logging.getLogger()
log.handlers.clear()
log.addHandler(lh)
log.setLevel(logging.DEBUG)

### OTA

import os

def dir_exists(fn):
    try:
        return (os.stat(fn)[0] & 0x4000) != 0
    except OSError:
        return False

def file_exists(fn):
    try:
        return (os.stat(fn)[0] & 0x4000) == 0
    except OSError:
        return False

def file_copy(src, dst, block=512):
    buf = bytearray(block)
    while True:
        sz = src.readinto(buf)
        if not sz:
            break
        if sz == block:
            dst.write(buf)
        else:
            b = memoryview(buf)[:sz]
            dst.write(b)

def _process_tar(tar):
    for i in tar:
        if i.isdir():
            log.info("Dir %s", i.name)
            if i.name != "./":
                p = i.name.strip("/")
                if not dir_exists(p):
                    os.mkdir(p)
        else:
            if any(s in i.name for s in ["././@PaxHeader", "/PaxHeaders/", "/PaxHeaders."]):
                continue
            log.info("Writing %s [%d bytes]...", i.name, i.size)
            # TODO: check that first file is a tag
            # TODO: verify fw-type

            # Remove old files (MicroPython prefers loading .py over .mpy)
            rmfn = None
            if i.name.endswith(".mpy"):
                rmfn = i.name.replace(".mpy", ".py")
            elif i.name.endswith(".py"):
                rmfn = i.name.replace(".py", ".mpy")
            if rmfn and file_exists(rmfn):
                os.remove(rmfn)

            # Extract new file
            src = tar.extractfile(i)
            with open(i.name, "wb") as dst:
                file_copy(src, dst)

def install_pending():
    try:
        files = os.listdir("ota")
        if not len(files):
            raise RuntimeError()
    except:
        #log.debug("No packages to install")
        return

    import tarfile, machine

    files = list(map(lambda x: "ota/" + x, files))
    installed = False
    for fn in files:
        try:
            with open(fn, "rb") as f:
                log.info("Installing OTA package: %s", fn)
                if fn.endswith(".tar.gz"):
                    from deflate import DeflateIO
                    with DeflateIO(f) as gz:
                        with tarfile.TarFile(fileobj=gz) as tar:
                            _process_tar(tar)
                elif fn.endswith(".tar"):
                    with tarfile.TarFile(fileobj=f) as tar:
                        _process_tar(tar)
                else:
                    raise Exception("Unknown file format")
            installed = True
        except Exception as e:
            log.exception("Cannot install", exc_info=e)

    # Cleanup
    for fn in files:
        if file_exists(fn):
            os.remove(fn)

    if installed:
        os.sync()
        log.info("Rebooting...")
        machine.reset()

install_pending()

### RECOVERY

import io

class PartitionReader(io.IOBase):
    def __init__(self, p):
        super().__init__()
        self._p = p
        self._pos = 0
        #self._bc = p.ioctl(4, 0)       # block count
        self._bs = p.ioctl(5, 0)        # block size
        self._cs = 0                    # cache start
        self._cd = memoryview(bytearray(self._bs))
        p.readblocks(0, self._cd)

    def readinto(self, buf):
        ret = len(buf)
        # Read from cache
        if self._pos >= self._cs and self._pos + ret <= self._cs + len(self._cd):
            cpos = self._pos - self._cs
            buf[:] = self._cd[cpos:cpos+ret]
            self._pos += ret
            return ret
        # Update cache
        block, off = divmod(self._pos, self._bs)
        self._cs = block * self._bs
        self._p.readblocks(block, self._cd)
        if self._pos >= self._cs and self._pos + ret <= self._cs + len(self._cd):
            cpos = self._pos - self._cs
            buf[:] = self._cd[cpos:cpos+ret]
        else:
            self._p.readblocks(block, buf, off)
        self._pos += ret
        return ret

    def seekable(self):
        return True

    def seek(self, offset, whence=0):
        if whence == 0:
            self._pos = offset
        elif whence == 1:
            self._pos += offset
        elif whence == 2:
            self._pos = self._bc * self._bs + offset

def install_recovery():
    log.warning(".:[ Loading from recovery ]:.")

    from esp32 import Partition
    p = Partition.find(Partition.TYPE_DATA, label="recovery")
    if not p:
        raise RuntimeError("No recovery partition")
    p = p[0]

    import tarfile, machine
    from flashbdev import bdev
    from deflate import DeflateIO

    f = PartitionReader(p)
    with DeflateIO(f) as gz:
        buf = memoryview(bytearray(280))
        gz.readinto(buf)
    f.seek(0)

    if buf[8:16] == b"littlefs":
        imgtype = "lfs"
    elif buf[257:262] == b"ustar":
        imgtype = "tar"
    else:
        raise RuntimeError("No recovery image")

    if imgtype == "lfs":
        log.info("Inflating FS...")
        try:
            os.umount("/")
        except:
            pass
        with DeflateIO(f) as gz:
            bc = bdev.ioctl(4, 0)
            bs = bdev.ioctl(5, 0)
            buf = memoryview(bytearray(bs))
            pos = 0
            while pos < bc:
                ret = gz.readinto(buf)
                bdev.writeblocks(pos, buf[:ret])
                sys.stdout.write(b".")
                pos += 1
                if ret < bs:
                    break
        #os.mount(bdev, "/")
        sys.stdout.write(b"\n")
    else:
        log.info("Formatting FS...")
        os.umount("/")
        os.VfsLfs2.mkfs(bdev)
        os.mount(bdev, "/")
        os.mkdir("/lib")  # TODO
        with DeflateIO(f) as gz:
            with tarfile.TarFile(fileobj=gz) as tar:
                _process_tar(tar)
        os.sync()

    log.info("Rebooting...")
    machine.reset()

if not os.listdir():
    install_recovery()

### MAIN APP

#if file_exists("code.py") or file_exists("code.mpy"):
#    import code
#else:
#    print("No code.py found")
