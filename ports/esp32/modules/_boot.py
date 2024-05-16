import gc
import vfs
from flashbdev import bdev
from config import sysconfig

try:
    if bdev:
        vfs.mount(bdev, "/")
except:
    # This is handled later via FS recovery
    pass

__import__("_preinit")

del vfs, bdev
gc.collect()
