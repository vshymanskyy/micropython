import gc
import vfs, rp2

bdev = rp2.Flash()
try:
    fs = vfs.VfsLfs2(bdev, progsize=256)
    vfs.mount(fs, "/")
except:
    # This is handled later via FS recovery
    pass

__import__("_preinit")

del vfs, bdev, fs
gc.collect()

# Import sysconfig after vfs was mounted
from config import sysconfig
