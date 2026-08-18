cmake_minimum_required(VERSION 3.16)

option(TINYTOUCH_RECOVERY_BUILD "Build one-time destructive recovery firmware" OFF)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)

# tinyTouch targets esp-idf 5.3.x, as declared in main/idf_component.yml.
#
# idf 6.0 ships mbedtls 4.x, which moved the legacy crypto modules into
# tf-psa-crypto and dropped the public headers. main/piv.c needs mbedtls/rsa.h
# and main/touch_pin_hid.c needs mbedtls/aes.h, so the build dies partway
# through compilation with a "missing header" hint that points at openthread's
# vendored copy of mbedtls. that message sends people the wrong way, so fail
# here instead with something actionable.
if(DEFINED IDF_VERSION_MAJOR AND DEFINED IDF_VERSION_MINOR)
  if(NOT (IDF_VERSION_MAJOR EQUAL 5 AND IDF_VERSION_MINOR EQUAL 3))
    message(FATAL_ERROR
      "tinyTouch needs esp-idf 5.3.x, but this is "
      "${IDF_VERSION_MAJOR}.${IDF_VERSION_MINOR}.${IDF_VERSION_PATCH}.\n"
      "install 5.3.x and source its export.sh:\n"
      "  git clone -b v5.3.3 --recursive "
      "https://github.com/espressif/esp-idf.git ~/esp/esp-idf-v5.3.3\n"
      "  cd ~/esp/esp-idf-v5.3.3 && ./install.sh esp32s3\n"
      "  source ~/esp/esp-idf-v5.3.3/export.sh\n"
      "then delete build/, sdkconfig, and dependencies.lock before rebuilding.")
  endif()
endif()

project(tiny_touch_smartcard)
