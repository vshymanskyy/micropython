import gc
import vfs
from flashbdev import bdev

try:
    if bdev:
        vfs.mount(bdev, "/")
except OSError:
    # This is handled later via FS recovery
    pass

__import__("_preinit")

del vfs, bdev
gc.collect()
