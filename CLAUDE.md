# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ESP32-based irrigation controller using ESPHome, integrated with Home Assistant. Controls up to 20 solenoid valve zones sequentially via a 3-chained SN74HC595 shift register, with liter-based flow control (primary) and time-based safety timeout (fallback). A single shared pulse-counter flow sensor sits before the valve manifold. Includes an SSD1306 OLED status display. A companion KiCad 9 PCB project lives in `PCB/`.

## Build & Deploy

```bash
# Validate the ESPHome YAML config
esphome config esphome/irrigation-micr-2.yaml

# Compile firmware
esphome compile esphome/irrigation-micr-2.yaml

# Compile and upload over USB
esphome run esphome/irrigation-micr-2.yaml

# OTA upload (device must be on the network)
esphome run esphome/irrigation-micr-2.yaml --device irrigation-micro-2.local

# View live logs
esphome logs esphome/irrigation-micr-2.yaml

# Regenerate KiCad schematic from pin mapping
python3 PCB/esp_watering/generate_schematic.py
```

## Architecture

### Two-layer switch design

Each zone has two switches: a **virtual template switch** (`irrigation_zoneN`) and a **GPIO switch** (`pinN`). The virtual switch checks whether `liters_target > 0` OR `duration > 0` before delegating to the GPIO switch. If neither is set, it calls `advance_to_next_zone(N)` to skip to the next enabled zone without breaking the chain. Zones run sequentially — only one zone is active at a time because a single flow sensor is shared.

### C++ control logic (`irrigation.h`)

All zone control logic lives in C++ rather than YAML lambdas. Key functions:
- **`irrigation_init()`** — Populates pointer arrays for all 20 zones' ESPHome components. Called from `on_boot`.
- **`start_zone(N)`** — Snapshots `flow_total` for liter tracking, sets safety timer from duration, publishes initial sensor states. Called from GPIO switch `on_turn_on`.
- **`stop_zone(N)`** — Zeros remaining sensors, updates next-time display. Called from GPIO switch `on_turn_off`.
- **`zone_tick()`** — Called every 5s from interval. For the active zone: decrements safety timer, computes liters watered since zone start, checks if liter target reached OR safety timeout hit. If done: turns off pin, calls `advance_to_next_zone()`.
- **`advance_to_next_zone(completed)`** — Scans forward for next zone with `liters_target > 0` or `duration > 0`, turns it on. If none found, cycle ends.
- **`scheduled_runtime()`** / **`update_next_runtime()`** — Schedule matching/display helpers (unchanged from original).

Static arrays (`liters_start[]`, `safety_remaining[]`, etc.) and pointer arrays (`zone_pin[]`, `zone_duration[]`, etc.) are indexed 0–19. The `active_zone` static int is -1 when idle.

### Shift register output

20 valve outputs via 3 chained SN74HC595 registers (GPIO19=data, GPIO18=clock, GPIO17=latch). GPIO switches `pin0`–`pin19` map to shift register outputs 0–19.

### Scheduling

Watering times are stored as comma-separated `HH:MM` strings in a Home Assistant `input_text` entity (referenced via `$irrigation_times_entity` substitution). A cron-like `on_time` trigger checks every 2 minutes and starts zone 0 if a scheduled time matches.

### Hardware (I2C bus on GPIO21/GPIO22)

- **SSD1306 128x64 OLED** (0x3C) — shows WiFi/HA status, active zone progress (liters/target + timeout), or idle state with next scheduled time
- **PCF8574 I/O expander** (0x20) — available for additional I/O
- **Pulse counter flow sensor** on GPIO34 — measures L/min (`flow_rate`) and total liters (`flow_total`)

### Per-zone entities exposed to Home Assistant

- `irrigation_zoneN_duration` — Safety timeout in minutes (number, 0–60)
- `irrigation_zoneN_liters_target` — Primary liter target (number, 0–100)
- `irrigation_zoneN_remaining` — Minutes remaining display sensor
- `irrigation_zoneN_liters_remaining` — Liters remaining display sensor
- `irrigation_zoneN` — Virtual on/off switch

### Resilience

WiFi `reboot_timeout: 0s` disables automatic rebooting when Home Assistant is unreachable, so an in-progress watering schedule runs to completion.

## Key Substitutions

The YAML uses ESPHome substitutions (`$friendly_name`, `$irrigation_times_entity`, etc.) defined near the top. When adapting for a new device, update the `substitutions:` block and the `esphome: name:` field.
