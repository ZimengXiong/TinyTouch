cmake_minimum_required(VERSION 3.16)

option(TINYTOUCH_RECOVERY_BUILD "Build one-time destructive recovery firmware" OFF)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(tiny_touch_smartcard)
