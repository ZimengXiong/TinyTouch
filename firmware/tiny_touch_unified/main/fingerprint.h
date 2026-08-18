#pragma once

#include <stdbool.h>
#include <stdint.h>

void fingerprint_init(void);
bool fingerprint_present_hint(void);
void fingerprint_led_idle(void);
bool fingerprint_authorize_poll_once(void);
bool fingerprint_authorize_once(void);
int fingerprint_count(void);
bool fingerprint_enroll(uint16_t slot, void (*prompt)(const char *message));
bool fingerprint_delete(uint16_t slot);
bool fingerprint_delete_all(void);
