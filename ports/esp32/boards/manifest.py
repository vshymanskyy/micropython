freeze("$(PORT_DIR)/modules")
include("$(MPY_DIR)/extmod/asyncio")

# Useful networking-related packages.
require("mip")
require("requests")
require("ssl")

# Require some micropython-lib modules.
require("logging")
require("tarfile")
require("aioble")
require("aioespnow")
require("dht")
require("ds18x20")
require("neopixel")
require("onewire")
require("upysh")
