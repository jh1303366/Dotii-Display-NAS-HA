#pragma once
#include "app_state.h"
#include "lvgl.h"
lv_obj_t *ha_ui_create(bool (*touch_allowed)(void));
void ha_ui_update(const codex_snapshot_t *snapshot);
void ha_ui_tick(void);
void ha_ui_back(void);
void ha_ui_page(int delta);
bool ha_ui_detail_active(void);
