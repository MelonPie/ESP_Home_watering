# ESP32 Irrigation Controller

ESP32-based irrigation controller using [ESPHome](https://esphome.io/), integrated with [Home Assistant](https://www.home-assistant.io/). Controls up to 20 solenoid valve zones sequentially with liter-based flow control and time-based safety timeout. Includes an OLED status display and a companion KiCad 9 PCB design.

## Features

- **20 independent zones** controlled sequentially via 3 chained SN74HC595 shift registers and ULN2003 drivers
- **Dual watering control** — primary liter target with duration-based safety timeout fallback
- **Shared pulse-counter flow sensor** for accurate volume measurement
- **SSD1306 OLED display** showing WiFi/HA status, active zone progress, and next scheduled run
- **Home Assistant integration** with per-zone controls for duration, liter target, and on/off
- **Scheduled watering** via comma-separated times stored in a Home Assistant `input_text` entity
- **Offline resilience** — watering continues even if Home Assistant connection drops

## Hardware

| Component | Details |
|---|---|
| MCU | ESP32-WROOM-32 DevKit |
| Shift registers | 3x SN74HC595 (GPIO14 data, GPIO13 clock, GPIO12 latch) |
| Valve drivers | 3x ULN2003 Darlington arrays driving 12V solenoids |
| Flow sensor | FS300A (open-collector NPN, 5V supply) on GPIO34, scaled by a 1.8k/3.3k divider (R1/R2) — node sits at 3.24V high / ~0V low |
| Display | SSD1306 128x64 OLED via I2C (0x3C) on GPIO21/GPIO22 |
| Power | Two external rails: **+12V** (solenoid valves) and **+5V** (logic + ESP32 VIN + flow sensor). +3.3V is generated on the ESP32 dev board's onboard regulator and exported on its 3V3 pin (used by the OLED). |

## Project Structure

```
├── esphome/
│   ├── irrigation-micr-2.yaml   # Main ESPHome configuration
│   ├── irrigation.h             # C++ zone control logic
│   └── slkscr.ttf               # OLED display font
├── PCB/
│   └── esp_watering/
│       ├── generate_schematic.py # KiCad 9 schematic generator
│       ├── esp_watering.kicad_sch
│       ├── esp_watering.kicad_pcb
│       └── esp_watering.kicad_pro
└── old_version/                  # Previous iteration for reference
```

## How It Works

### Zone Control

Each zone has a **virtual template switch** and a **GPIO switch**. When a zone is activated, the virtual switch checks if a liter target or duration is set. If neither is configured, it skips to the next enabled zone. Only one zone runs at a time since all zones share a single flow sensor.

### Watering Logic

1. A zone starts and snapshots the current flow total
2. Every 5 seconds, `zone_tick()` checks liters watered and remaining time
3. The zone stops when the liter target is reached or the safety timeout expires
4. `advance_to_next_zone()` scans forward for the next enabled zone
5. The cycle ends when no more enabled zones remain

### Scheduling

Watering times are stored as comma-separated `HH:MM` strings in a Home Assistant `input_text` entity (e.g., `"08:00,14:00,20:00"`). A cron-like trigger checks every 2 minutes and starts the zone sequence if a scheduled time matches.

## Per-Zone Home Assistant Entities

| Entity | Type | Description |
|---|---|---|
| `irrigation_zoneN_duration` | Number (0–60) | Safety timeout in minutes |
| `irrigation_zoneN_liters_target` | Number (0–100) | Primary liter target |
| `irrigation_zoneN_remaining` | Sensor | Minutes remaining (read-only) |
| `irrigation_zoneN_liters_remaining` | Sensor | Liters remaining (read-only) |
| `irrigation_zoneN` | Switch | Zone on/off control |

## Build & Deploy

Requires [ESPHome CLI](https://esphome.io/guides/installing_esphome).

```bash
# Validate config
esphome config esphome/irrigation-micr-2.yaml

# Compile firmware
esphome compile esphome/irrigation-micr-2.yaml

# Compile and upload via USB
esphome run esphome/irrigation-micr-2.yaml

# OTA upload (device on network)
esphome run esphome/irrigation-micr-2.yaml --device irrigation-micro-2.local

# View live logs
esphome logs esphome/irrigation-micr-2.yaml
```

### PCB Schematic

The KiCad schematic can be regenerated from pin mappings:

```bash
python3 PCB/esp_watering/generate_schematic.py
```

## Configuration

To adapt for a new device, update the `substitutions:` block and `esphome: name:` field in the YAML config. Key substitutions include device name, friendly name, and the Home Assistant entity for schedule times.
