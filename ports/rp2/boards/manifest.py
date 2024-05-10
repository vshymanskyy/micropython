freeze("$(PORT_DIR)/modules")
include("$(MPY_DIR)/extmod/asyncio")

# Require some micropython-lib modules.
require("logging")
require("tarfile")
require("dht")
require("ds18x20")
require("neopixel")
require("onewire")
require("upysh")
