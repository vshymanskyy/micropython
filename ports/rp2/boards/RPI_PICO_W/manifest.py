include("$(PORT_DIR)/boards/manifest.py")

# Useful networking-related packages.
require("mip")
require("requests")

# Require some micropython-lib modules.
require("logging")
require("tarfile")

# Bluetooth
require("aioble")
