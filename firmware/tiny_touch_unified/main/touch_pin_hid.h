#pragma once

#include <stdbool.h>

void touch_pin_hid_start(void);
bool touch_pin_hid_submit_response(const char *response);
