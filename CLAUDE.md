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

20 valve outputs via 3 chained SN74HC595 registers (GPIO23=data, GPIO18=clock, GPIO5=latch, GPIO16=/OE). GPIO switches `pin0`–`pin19` map to shift register outputs 0–19.

The data/clock/latch lines were originally on GPIO14/13/12, but those are unsuitable: GPIO12 is a strapping pin (flash voltage select) and GPIO14/15 emit bootloader debug pulses on reset, which clocked random data into the SRs and energized valves at boot. The `/OE` line on all three SRs is tied together and pulled up to +5V by a 10k resistor (R3); ESP32 GPIO16 drives it open-drain (`mode: { output: true, open_drain: true }`). While GPIO16 is in reset / high-Z the pull-up keeps `/OE` high, disabling all SR outputs. ESPHome's `sn74hc595` component releases `/OE` low only after shifting in zeros, so valves stay off through every reset.

### Scheduling

Watering times are stored as comma-separated `HH:MM` strings in a Home Assistant `input_text` entity (referenced via `$irrigation_times_entity` substitution). A cron-like `on_time` trigger checks every 2 minutes and starts zone 0 if a scheduled time matches.

### Hardware (I2C bus on GPIO21/GPIO22)

- **SSD1306 128x64 OLED** (0x3C) — shows WiFi/HA status, active zone progress (liters/target + timeout), or idle state with next scheduled time
- **Pulse counter flow sensor** on GPIO34 — FS300A (5V open-collector NPN). The signal is scaled to ESP32 levels by a passive divider: R1 (1.8k) pulls the node to +5V, R2 (3.3k) pulls it to GND, and the FS300A signal output + GPIO34 sit on the same node. When the sensor's transistor is open the node sits at 5V × 3.3/(1.8+3.3) ≈ 3.24V; when it conducts during a pulse, the node is pulled to ~0V. (Earlier revisions used an HW-221 active level shifter; it was a TXS0108E variant that latched up against the open-collector signal — the divider is the correct part for a unidirectional 5V→3.3V pulse input.)

### Power architecture

Two external rails enter the board:
- **+12V** (J22) — solenoid valves only (ULN2003 COM)
- **+5V** (J23) — logic rail: SR/ULN VCC, flow sensor supply, divider pull-up, and ESP32 VIN

The ESP32 dev board's onboard regulator generates **+3V3** from VIN; that rail is sourced by the ESP32's 3V3 pin and consumed by the OLED. **Do not feed +12V into ESP32 VIN** — the dev board's regulator dissipates the drop as heat and is not rated for it.

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

## Ignored Directories

- `old_version/` — Legacy code, no longer relevant. Do not read, reference, or modify.
