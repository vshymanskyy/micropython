set(IDF_TARGET esp32s3)

set(SDKCONFIG_DEFAULTS
    boards/sdkconfig.base
    ${SDKCONFIG_IDF_VERSION_SPECIFIC}
    boards/sdkconfig.usb
    boards/sdkconfig.ble
    boards/sdkconfig.spiram_sx
    boards/sdkconfig.esp32cam
    boards/ESP32_GENERIC_S3/sdkconfig.board
)

list(APPEND MICROPY_DEF_BOARD
    MODULE_CAMERA_ENABLED=1
)
