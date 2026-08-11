#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef enum {
  DEVICE_MODE_PIV = 0,
  DEVICE_MODE_HID = 1,
} device_mode_t;

void device_config_init(void);
device_mode_t device_config_mode(void);
const char *device_config_mode_name(void);
bool device_config_set_mode(device_mode_t mode);
bool device_config_hid_key_configured(void);
bool device_config_get_hid_key(uint8_t key[32]);
bool device_config_set_hid_key(const uint8_t key[32]);
void device_config_reload(void);
