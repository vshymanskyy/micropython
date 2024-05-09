# SPDX-FileCopyrightText: 2024 Volodymyr Shymanskyy for Blynk Technologies Inc.
# SPDX-License-Identifier: Apache-2.0
#
# The software is provided "as is", without any warranties or guarantees (explicit or implied).
# This includes no assurances about being fit for any specific purpose.

### SYS PATH

import sys
sys.path = ["", "/lib", ".frozen"]

### LOG

import time
import logging

try:
    from sysconfig import sysconfig
    _logcfg = sysconfig["log"]
except:
    _logcfg = {}

_lvlfmt = {
    logging.CRITICAL: ("C", "\033[31m"),
    logging.ERROR:    ("E", "\033[91m"),
    logging.WARNING:  ("W", "\033[93m"),
    logging.INFO:     ("I", ""),
    logging.DEBUG:    ("D", "\033[38;5;248m"),
}
_lvlfmt.setdefault((" ", ""))

_loglvl = {
    "none":     1000,
    "critical": logging.CRITICAL,
    "error":    logging.ERROR,
    "warning":  logging.WARNING,
    "info":     logging.INFO,
    "debug":    logging.DEBUG,
}.get(_logcfg.get("level"), logging.INFO)

class SimpleLogFormatter:
    def format(self, r):
        lvl, _ = _lvlfmt[r.levelno]
        return f"{time.ticks_ms():6d} {lvl} {r.name:12s} {r.message}"

class ColorLogFormatter:
    def format(self, r):
        lvl, color = _lvlfmt[r.levelno]
        return f"{color}{time.ticks_ms():6d} {lvl} {r.name:12s} {r.message}\033[0m"

lh = logging.StreamHandler()
lh.setLevel(_loglvl)
if _logcfg.get("color"):
    lh.setFormatter(ColorLogFormatter())
else:
    lh.setFormatter(SimpleLogFormatter())
log = logging.getLogger()
log.handlers.clear()
log.addHandler(lh)
log.setLevel(_loglvl)

### OTA

import os, json

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

def _pairwise(t):
    it = iter(t)
    return zip(it, it)

def _parse_tag(tag):
    taginfo = tag.split(b"\0")
    taginfo = list(map(lambda x: x.decode("utf-8"), taginfo))
    return dict(_pairwise(taginfo[1:-2]))

def _load_fw_info(fw_info):
    res = {}
    t = _parse_tag(fw_info)
    v = t.get("fw-type")
    if v:
        res["type"] = v
    v = t.get("mcu")
    if v:
        res["ver"] = v
    v = t.get("build")
    if v:
        res["build"] = v
    return res

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
                # Skip
                continue

            if i.name == "fw_info.bin":
                # Save as config
                src = tar.extractfile(i)
                fw = _load_fw_info(src.read())
                with open("cfg/fw.json", "w") as dst:
                    json.dump(fw, dst, separators=(",", ":"))
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

    import tarfile

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

import vfs

if sys.platform == "esp32":
    from flashbdev import bdev
elif sys.platform == "rp2":
    import rp2
    bdev = rp2.Flash()

def format_fs():
    log.info("Formatting FS...")
    try:
        vfs.umount("/")
    except:
        pass
    if sys.platform == "esp32":
        if bdev.info()[4] == "vfs":
            vfs.VfsLfs2.mkfs(bdev)
            fs = vfs.VfsLfs2(bdev)
        elif bdev.info()[4] == "ffat":
            vfs.VfsFat.mkfs(bdev)
            fs = vfs.VfsFat(bdev)
    elif sys.platform == "rp2":
        vfs.VfsLfs2.mkfs(bdev, progsize=256)
        fs = vfs.VfsLfs2(bdev, progsize=256)
    vfs.mount(fs, "/")

def install_recovery():
    f = None
    if sys.platform == "esp32":
        from esp32 import Partition
        p = Partition.find(Partition.TYPE_DATA, label="recovery")
        if len(p):
            log.warning(".:[ Recovery from partition ]:.")
            f = PartitionReader(p[0])

    if not f:
        # No recovery partition, try importing .frozen recovery
        try:
            import _recovery
            log.warning(".:[ Recovery from .frozen ]:.")
            f = _recovery.data()
        except:
            format_fs()
            log.info("No recovery image")
            with open("boot.py", "w") as out:
                out.write("# This file is executed on every boot (including wake-boot from deepsleep)\n")
            with open("main.py", "w") as out:
                out.write("# Put your main code here\n")
            return

    import tarfile
    from deflate import DeflateIO

    with DeflateIO(f) as gz:
        buf = memoryview(bytearray(280))
        gz.readinto(buf)
    f.seek(0)

    if buf[8:16] == b"littlefs":
        imgtype = "lfs"
    elif buf[257:262] == b"ustar":
        imgtype = "tar"
    else:
        raise RuntimeError("Recovery image not recognized")

    if imgtype == "lfs":
        log.info("Inflating FS...")
        try:
            vfs.umount("/")
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
        #vfs.mount(bdev, "/")
        sys.stdout.write(b"\n")
    else:
        format_fs()
        os.mkdir("/lib")   # TODO
        os.mkdir("/cfg")   # TODO
        os.mkdir("/cert")  # TODO
        with DeflateIO(f) as gz:
            with tarfile.TarFile(fileobj=gz) as tar:
                _process_tar(tar)
        os.sync()

def check_btn_press():
    import machine
    button = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP)
    press_time = None
    t = time.ticks_ms()
    start_time = t
    while time.ticks_diff(t, start_time) < 500:
        pressed = (button.value() == 0)
        if pressed:
            if press_time is None:
                press_time = t
            if time.ticks_diff(t, press_time) > 100:
                return True
        else:
            press_time = None
        time.sleep_ms(10)
        t = time.ticks_ms()
    return False

if not os.listdir() or check_btn_press():
    install_recovery()

### MAIN APP

#if file_exists("code.py") or file_exists("code.mpy"):
#    import code
#else:
#    print("No code.py found")
