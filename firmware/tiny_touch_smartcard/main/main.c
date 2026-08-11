#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs_flash.h"

#include "fingerprint.h"
#include "config_console.h"
#include "device_config.h"
#include "piv.h"
#include "touch_pin_hid.h"
#include "usb_ccid.h"

void app_main(void) {
  esp_err_t nvs_result = nvs_flash_init();
  if (nvs_result == ESP_ERR_NVS_NO_FREE_PAGES ||
      nvs_result == ESP_ERR_NVS_NEW_VERSION_FOUND) {
    ESP_ERROR_CHECK(nvs_flash_erase());
    nvs_result = nvs_flash_init();
  }
  ESP_ERROR_CHECK(nvs_result);
  fingerprint_init();
  device_config_init();
  piv_init();
  usb_ccid_start(piv_handle_apdu);
  config_console_start();
  touch_pin_hid_start();

  while (true) {
    usb_ccid_task();
    vTaskDelay(pdMS_TO_TICKS(1));
  }
}
