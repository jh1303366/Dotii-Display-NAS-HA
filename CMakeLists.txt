cmake_minimum_required(VERSION 3.16)

# The repository snapshot omits zlib's generated header. The locked registry
# package contains the exact same bytes as zconf.h.in; restore them only when
# their SHA-256 matches that package, without changing third-party code.
set(DOTII_ZLIB_DIR "${CMAKE_CURRENT_LIST_DIR}/managed_components/espressif__zlib/zlib")
if(EXISTS "${DOTII_ZLIB_DIR}/zconf.h.in" AND NOT EXISTS "${DOTII_ZLIB_DIR}/zconf.h")
    file(SHA256 "${DOTII_ZLIB_DIR}/zconf.h.in" DOTII_ZCONF_HASH)
    if(NOT DOTII_ZCONF_HASH STREQUAL "cb7c2c84211473b4699223edd363d3207b43b9578e739b5bf638f42204ea6e0f")
        message(FATAL_ERROR "zlib template differs from the locked component; restore it through Component Manager")
    endif()
    configure_file("${DOTII_ZLIB_DIR}/zconf.h.in" "${DOTII_ZLIB_DIR}/zconf.h" COPYONLY)
endif()

set(IDF_TARGET "esp32s3")
set(PROJECT_VER "1.3.0-ha")
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
idf_build_set_property(MINIMAL_BUILD ON)
project(state_display)
