set(SDKCONFIG_DEFAULTS
    ${SDKCONFIG_DEFAULTS}
    boards/sdkconfig.spiram
    boards/ESP32_GENERIC/sdkconfig.ota
    boards/sdkconfig.esp32cam
)

list(APPEND MICROPY_DEF_BOARD
    MICROPY_HW_BOARD_NAME="Generic ESP32 module with SPIRAM"
    MODULE_CAMERA_ENABLED=1
)
