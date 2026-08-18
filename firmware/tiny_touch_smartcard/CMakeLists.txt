cmake_minimum_required(VERSION 3.16)

option(TINYTOUCH_RECOVERY_BUILD "Build one-time destructive recovery firmware" OFF)

file(READ "${CMAKE_CURRENT_LIST_DIR}/../../VERSION" TINYTOUCH_VERSION)
string(STRIP "${TINYTOUCH_VERSION}" TINYTOUCH_VERSION)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(tiny_touch_smartcard)
