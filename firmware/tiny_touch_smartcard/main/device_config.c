#include "device_config.h"

#include <string.h>

#include "nvs.h"

static device_mode_t current_mode = DEVICE_MODE_PIV;
static uint8_t hid_key[32];
static bool has_hid_key;

void device_config_reload(void) {
  current_mode = DEVICE_MODE_PIV;
  memset(hid_key, 0, sizeof(hid_key));
  has_hid_key = false;

  nvs_handle_t handle;
  if (nvs_open("device", NVS_READONLY, &handle) != ESP_OK) return;

  uint8_t stored_mode = DEVICE_MODE_PIV;
  if (nvs_get_u8(handle, "mode", &stored_mode) == ESP_OK &&
      stored_mode <= DEVICE_MODE_HID) {
    current_mode = (device_mode_t)stored_mode;
  }

  size_t key_length = sizeof(hid_key);
  if (nvs_get_blob(handle, "hid_key", hid_key, &key_length) == ESP_OK &&
      key_length == sizeof(hid_key)) {
    has_hid_key = true;
  } else {
    memset(hid_key, 0, sizeof(hid_key));
  }
  nvs_close(handle);
}

void device_config_init(void) {
  device_config_reload();
}

device_mode_t device_config_mode(void) {
  return current_mode;
}

const char *device_config_mode_name(void) {
  return current_mode == DEVICE_MODE_HID ? "hid" : "piv";
}

bool device_config_set_mode(device_mode_t mode) {
  if (mode != DEVICE_MODE_PIV && mode != DEVICE_MODE_HID) return false;
  if (mode == DEVICE_MODE_HID && !has_hid_key) return false;

  nvs_handle_t handle;
  if (nvs_open("device", NVS_READWRITE, &handle) != ESP_OK) return false;
  esp_err_t result = nvs_set_u8(handle, "mode", (uint8_t)mode);
  if (result == ESP_OK) result = nvs_commit(handle);
  nvs_close(handle);
  if (result == ESP_OK) current_mode = mode;
  return result == ESP_OK;
}

bool device_config_hid_key_configured(void) {
  return has_hid_key;
}

bool device_config_get_hid_key(uint8_t key[32]) {
  if (!has_hid_key) return false;
  memcpy(key, hid_key, sizeof(hid_key));
  return true;
}

bool device_config_set_hid_key(const uint8_t key[32]) {
  nvs_handle_t handle;
  if (nvs_open("device", NVS_READWRITE, &handle) != ESP_OK) return false;
  esp_err_t result = nvs_set_blob(handle, "hid_key", key, 32);
  if (result == ESP_OK) result = nvs_commit(handle);
  nvs_close(handle);
  if (result == ESP_OK) {
    memcpy(hid_key, key, sizeof(hid_key));
    has_hid_key = true;
  }
  return result == ESP_OK;
}
