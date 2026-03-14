#!/usr/bin/env python3
"""Generate KiCad 9.0 schematic from ESPHome YAML analysis.

Architecture:
  ESP32 (GPIO19=data, GPIO18=clock, GPIO17=latch)
    -> 3x SN74HC595 shift registers (chained, 24 outputs, 20 used)
      -> 3x ULN2003 Darlington driver arrays (21 channels, 20 used)
        -> 20 solenoid valve connectors (+12V switched to GND)
  GPIO34: pulse-counter flow sensor
  GPIO21/22: I2C bus (SSD1306 OLED @ 0x3C, PCF8574 @ 0x20)
"""
import uuid

def uid():
    return str(uuid.uuid4())

# === Pin mapping from YAML ===
SHIFT_REG_DATA  = "GPIO19"
SHIFT_REG_CLOCK = "GPIO18"
SHIFT_REG_LATCH = "GPIO17"
NUM_ZONES = 20
NUM_SR = 3       # 3x SN74HC595
NUM_ULN = 3      # 3x ULN2003 (7 channels each = 21, using 20)

FLOW_PIN = "GPIO34"
I2C_SDA  = "GPIO21"
I2C_SCL  = "GPIO22"

# ESP32 DevKit pin definitions
ESP32_PINS_LEFT = [
    ("1",  "GND",       "power_in"),
    ("2",  "3V3",       "power_in"),
    ("3",  "GPIO36/VP", "bidirectional"),
    ("4",  "GPIO39/VN", "bidirectional"),
    ("5",  "GPIO34",    "bidirectional"),
    ("6",  "GPIO35",    "bidirectional"),
    ("7",  "GPIO32",    "bidirectional"),
    ("8",  "GPIO33",    "bidirectional"),
    ("9",  "GPIO25",    "bidirectional"),
    ("10", "GPIO26",    "bidirectional"),
    ("11", "GPIO27",    "bidirectional"),
    ("12", "GPIO14",    "bidirectional"),
    ("13", "GPIO13",    "bidirectional"),
    ("14", "GND2",      "power_in"),
    ("15", "VIN",       "power_in"),
]

ESP32_PINS_RIGHT = [
    ("16", "GND3",      "power_in"),
    ("17", "GPIO23",    "bidirectional"),
    ("18", "GPIO22",    "bidirectional"),
    ("19", "GPIO1/TX",  "bidirectional"),
    ("20", "GPIO3/RX",  "bidirectional"),
    ("21", "GPIO21",    "bidirectional"),
    ("22", "GPIO19",    "bidirectional"),
    ("23", "GPIO18",    "bidirectional"),
    ("24", "GPIO5",     "bidirectional"),
    ("25", "GPIO17",    "bidirectional"),
    ("26", "GPIO16",    "bidirectional"),
    ("27", "GPIO4",     "bidirectional"),
    ("28", "GPIO2",     "bidirectional"),
    ("29", "GPIO15",    "bidirectional"),
    ("30", "EN",        "input"),
]

ROOT_UUID = uid()
pwr_idx = 1  # global power symbol counter


# ============================================================
# Helper functions
# ============================================================
def make_pin(number, name, pin_type, x, y, angle, length=5.08):
    return f"""\t\t\t\t(pin {pin_type} line
\t\t\t\t\t(at {x} {y} {angle})
\t\t\t\t\t(length {length})
\t\t\t\t\t(name "{name}"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.016 1.016)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "{number}"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.016 1.016)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)"""


def make_wire(x1, y1, x2, y2):
    return f"""\t(wire
\t\t(pts
\t\t\t(xy {x1} {y1}) (xy {x2} {y2})
\t\t)
\t\t(stroke
\t\t\t(width 0)
\t\t\t(type default)
\t\t)
\t\t(uuid "{uid()}")
\t)"""


def make_global_label(text, x, y, angle=0, shape="bidirectional"):
    justify = "left" if angle == 0 else "right"
    return f"""\t(global_label "{text}"
\t\t(shape {shape})
\t\t(at {x} {y} {angle})
\t\t(effects
\t\t\t(font
\t\t\t\t(size 1.27 1.27)
\t\t\t)
\t\t\t(justify {justify})
\t\t)
\t\t(uuid "{uid()}")
\t\t(property "Intersheetrefs" "${{INTERSHEET_REFS}}"
\t\t\t(at 0 0 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t\t(hide yes)
\t\t\t)
\t\t)
\t)"""


def make_text(text, x, y, size=2.54):
    return f"""\t(text "{text}"
\t\t(exclude_from_sim no)
\t\t(at {x} {y} 0)
\t\t(effects
\t\t\t(font
\t\t\t\t(size {size} {size})
\t\t\t\t(bold yes)
\t\t\t)
\t\t)
\t\t(uuid "{uid()}")
\t)"""


def place_symbol(lib_id, ref, value, x, y, angle=0, mirror=False, pin_uuids=None, description=""):
    s_uuid = uid()
    mirror_str = "\n\t\t(mirror x)" if mirror else ""
    pins = ""
    if pin_uuids:
        for pnum, puuid in pin_uuids:
            pins += f'\t\t(pin "{pnum}"\n\t\t\t(uuid "{puuid}")\n\t\t)\n'
    return f"""\t(symbol
\t\t(lib_id "{lib_id}")
\t\t(at {x} {y} {angle}){mirror_str}
\t\t(unit 1)
\t\t(exclude_from_sim no)
\t\t(in_bom yes)
\t\t(on_board yes)
\t\t(dnp no)
\t\t(fields_autoplaced yes)
\t\t(uuid "{s_uuid}")
\t\t(property "Reference" "{ref}"
\t\t\t(at {x} {y - 5.08} 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t)
\t\t)
\t\t(property "Value" "{value}"
\t\t\t(at {x} {y + 5.08} 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t)
\t\t)
\t\t(property "Footprint" ""
\t\t\t(at {x} {y} 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t\t(hide yes)
\t\t\t)
\t\t)
\t\t(property "Datasheet" ""
\t\t\t(at {x} {y} 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t\t(hide yes)
\t\t\t)
\t\t)
\t\t(property "Description" "{description}"
\t\t\t(at {x} {y} 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t\t(hide yes)
\t\t\t)
\t\t)
{pins}\t\t(instances
\t\t\t(project ""
\t\t\t\t(path "/{ROOT_UUID}"
\t\t\t\t\t(reference "{ref}")
\t\t\t\t\t(unit 1)
\t\t\t\t)
\t\t\t)
\t\t)
\t)"""


def place_power(lib_id, ref, value, x, y, angle=0, description=""):
    global pwr_idx
    s_uuid = uid()
    result = f"""\t(symbol
\t\t(lib_id "{lib_id}")
\t\t(at {x} {y} {angle})
\t\t(unit 1)
\t\t(exclude_from_sim no)
\t\t(in_bom yes)
\t\t(on_board yes)
\t\t(dnp no)
\t\t(fields_autoplaced yes)
\t\t(uuid "{s_uuid}")
\t\t(property "Reference" "{ref}"
\t\t\t(at {x} {y - 3.81} 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t\t(hide yes)
\t\t\t)
\t\t)
\t\t(property "Value" "{value}"
\t\t\t(at {x} {y + 3.81} 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t)
\t\t)
\t\t(property "Footprint" ""
\t\t\t(at {x} {y} 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t\t(hide yes)
\t\t\t)
\t\t)
\t\t(property "Datasheet" ""
\t\t\t(at {x} {y} 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t\t(hide yes)
\t\t\t)
\t\t)
\t\t(property "Description" "{description}"
\t\t\t(at {x} {y} 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t\t(hide yes)
\t\t\t)
\t\t)
\t\t(pin "1"
\t\t\t(uuid "{uid()}")
\t\t)
\t\t(instances
\t\t\t(project ""
\t\t\t\t(path "/{ROOT_UUID}"
\t\t\t\t\t(reference "{ref}")
\t\t\t\t\t(unit 1)
\t\t\t\t)
\t\t\t)
\t\t)
\t)"""
    return result


def next_pwr(lib_id, value, x, y, angle=0, description=""):
    """Place a power symbol with auto-incrementing reference."""
    global pwr_idx
    ref = f"#PWR{pwr_idx:02d}"
    pwr_idx += 1
    return place_power(lib_id, ref, value, x, y, angle, description)


# ============================================================
# Build lib_symbols
# ============================================================
lib_symbols = []

# --- ESP32 DevKit Module ---
num_left = len(ESP32_PINS_LEFT)
num_right = len(ESP32_PINS_RIGHT)
max_pins = max(num_left, num_right)
esp_box_h = (max_pins + 1) * 2.54
esp_box_top = esp_box_h / 2
esp_box_bot = -esp_box_h / 2
esp_box_w = 20.32

esp_pins = []
for i, (num, name, ptype) in enumerate(ESP32_PINS_LEFT):
    y = esp_box_top - (i + 1) * 2.54
    esp_pins.append(make_pin(num, name, ptype, -(esp_box_w/2 + 5.08), y, 0))
for i, (num, name, ptype) in enumerate(ESP32_PINS_RIGHT):
    y = esp_box_top - (i + 1) * 2.54
    esp_pins.append(make_pin(num, name, ptype, (esp_box_w/2 + 5.08), y, 180))

lib_symbols.append(f"""\t\t(symbol "irrigation:ESP32-DevKit"
\t\t\t(pin_names
\t\t\t\t(offset 1.016)
\t\t\t)
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(property "Reference" "U"
\t\t\t\t(at 0 {esp_box_top + 2.54} 0)
\t\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t)
\t\t\t(property "Value" "ESP32-DevKit"
\t\t\t\t(at 0 {esp_box_bot - 2.54} 0)
\t\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t\t)
\t\t\t(property "Description" "ESP32 DevKit Module for Irrigation Controller"
\t\t\t\t(at 0 0 0)
\t\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t\t)
\t\t\t(symbol "ESP32-DevKit_0_1"
\t\t\t\t(rectangle
\t\t\t\t\t(start {-esp_box_w/2} {esp_box_top})
\t\t\t\t\t(end {esp_box_w/2} {esp_box_bot})
\t\t\t\t\t(stroke (width 0.254) (type default))
\t\t\t\t\t(fill (type background))
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "ESP32-DevKit_1_1"
{chr(10).join(esp_pins)}
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)""")

# --- SN74HC595 Shift Register ---
# Pinout: 1=QB, 2=QC, 3=QD, 4=QE, 5=QF, 6=QG, 7=QH, 8=GND,
#         9=QH'(ser out), 10=~SRCLR, 11=SRCLK, 12=RCLK, 13=~OE, 14=SER, 15=QA, 16=VCC
sr_pin_defs_left = [
    ("1",  "QB",     "output"),
    ("2",  "QC",     "output"),
    ("3",  "QD",     "output"),
    ("4",  "QE",     "output"),
    ("5",  "QF",     "output"),
    ("6",  "QG",     "output"),
    ("7",  "QH",     "output"),
    ("8",  "GND",    "power_in"),
]
sr_pin_defs_right = [
    ("16", "VCC",    "power_in"),
    ("15", "QA",     "output"),
    ("14", "SER",    "input"),
    ("13", "~{OE}",  "input"),
    ("12", "RCLK",   "input"),
    ("11", "SRCLK",  "input"),
    ("10", "~{SRCLR}", "input"),
    ("9",  "QH'",    "output"),
]

sr_pins = []
sr_box_h = 22.86  # 9 * 2.54
sr_box_top = sr_box_h / 2
sr_box_w = 12.7
for i, (num, name, ptype) in enumerate(sr_pin_defs_left):
    y = sr_box_top - (i + 1) * 2.54
    sr_pins.append(make_pin(num, name, ptype, -(sr_box_w/2 + 5.08), y, 0))
for i, (num, name, ptype) in enumerate(sr_pin_defs_right):
    y = sr_box_top - (i + 1) * 2.54
    sr_pins.append(make_pin(num, name, ptype, (sr_box_w/2 + 5.08), y, 180))

lib_symbols.append(f"""\t\t(symbol "irrigation:SN74HC595"
\t\t\t(pin_names (offset 1.016))
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(property "Reference" "U"
\t\t\t\t(at 0 {sr_box_top + 2.54} 0)
\t\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t)
\t\t\t(property "Value" "SN74HC595"
\t\t\t\t(at 0 {-sr_box_top - 2.54} 0)
\t\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t\t)
\t\t\t(property "Description" "8-bit Shift Register with Output Latch"
\t\t\t\t(at 0 0 0)
\t\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t\t)
\t\t\t(symbol "SN74HC595_0_1"
\t\t\t\t(rectangle
\t\t\t\t\t(start {-sr_box_w/2} {sr_box_top})
\t\t\t\t\t(end {sr_box_w/2} {-sr_box_top})
\t\t\t\t\t(stroke (width 0.254) (type default))
\t\t\t\t\t(fill (type background))
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "SN74HC595_1_1"
{chr(10).join(sr_pins)}
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)""")

# --- ULN2003 Darlington Driver Array ---
# Pinout: 1-7 = IN1-IN7, 8 = GND, 9 = COM, 10-16 = OUT7-OUT1
uln_pin_defs_left = [
    ("1", "IN1", "input"),
    ("2", "IN2", "input"),
    ("3", "IN3", "input"),
    ("4", "IN4", "input"),
    ("5", "IN5", "input"),
    ("6", "IN6", "input"),
    ("7", "IN7", "input"),
    ("8", "GND", "power_in"),
]
uln_pin_defs_right = [
    ("16", "OUT1", "open_collector"),
    ("15", "OUT2", "open_collector"),
    ("14", "OUT3", "open_collector"),
    ("13", "OUT4", "open_collector"),
    ("12", "OUT5", "open_collector"),
    ("11", "OUT6", "open_collector"),
    ("10", "OUT7", "open_collector"),
    ("9",  "COM",  "passive"),
]

uln_pins = []
uln_box_h = 22.86
uln_box_top = uln_box_h / 2
uln_box_w = 12.7
for i, (num, name, ptype) in enumerate(uln_pin_defs_left):
    y = uln_box_top - (i + 1) * 2.54
    uln_pins.append(make_pin(num, name, ptype, -(uln_box_w/2 + 5.08), y, 0))
for i, (num, name, ptype) in enumerate(uln_pin_defs_right):
    y = uln_box_top - (i + 1) * 2.54
    uln_pins.append(make_pin(num, name, ptype, (uln_box_w/2 + 5.08), y, 180))

lib_symbols.append(f"""\t\t(symbol "irrigation:ULN2003"
\t\t\t(pin_names (offset 1.016))
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(property "Reference" "U"
\t\t\t\t(at 0 {uln_box_top + 2.54} 0)
\t\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t)
\t\t\t(property "Value" "ULN2003"
\t\t\t\t(at 0 {-uln_box_top - 2.54} 0)
\t\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t\t)
\t\t\t(property "Description" "7-channel Darlington Driver Array"
\t\t\t\t(at 0 0 0)
\t\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t\t)
\t\t\t(symbol "ULN2003_0_1"
\t\t\t\t(rectangle
\t\t\t\t\t(start {-uln_box_w/2} {uln_box_top})
\t\t\t\t\t(end {uln_box_w/2} {-uln_box_top})
\t\t\t\t\t(stroke (width 0.254) (type default))
\t\t\t\t\t(fill (type background))
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "ULN2003_1_1"
{chr(10).join(uln_pins)}
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)""")

# --- Connector symbols ---
def make_conn_symbol(name, num_pins, description=""):
    pins_str = ""
    box_h = (num_pins + 1) * 2.54
    box_top = box_h / 2
    box_bot = -box_h / 2
    for i in range(num_pins):
        y = box_top - (i + 1) * 2.54
        pins_str += make_pin(str(i+1), f"Pin_{i+1}", "passive", -(5.08 + 2.54), y, 0, 5.08) + "\n"
    return f"""\t\t(symbol "irrigation:{name}"
\t\t\t(pin_names (offset 1.016))
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(property "Reference" "J"
\t\t\t\t(at 0 {box_top + 2.54} 0)
\t\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t)
\t\t\t(property "Value" "{name}"
\t\t\t\t(at 0 {box_bot - 2.54} 0)
\t\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t\t)
\t\t\t(property "Description" "{description}"
\t\t\t\t(at 0 0 0)
\t\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t\t)
\t\t\t(symbol "{name}_0_1"
\t\t\t\t(rectangle
\t\t\t\t\t(start -2.54 {box_top})
\t\t\t\t\t(end 2.54 {box_bot})
\t\t\t\t\t(stroke (width 0.254) (type default))
\t\t\t\t\t(fill (type background))
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "{name}_1_1"
{pins_str}\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)"""

lib_symbols.append(make_conn_symbol("Conn_01x02", 2, "2-pin connector"))
lib_symbols.append(make_conn_symbol("Conn_01x03", 3, "3-pin connector"))

# --- SSD1306 OLED module ---
oled_pins = []
oled_pin_names = [("1", "GND", "power_in"), ("2", "VCC", "power_in"),
                  ("3", "SCL", "input"), ("4", "SDA", "bidirectional")]
for i, (num, name, ptype) in enumerate(oled_pin_names):
    y = 5.08 - i * 2.54
    oled_pins.append(make_pin(num, name, ptype, -(5.08 + 2.54), y, 0, 5.08))

lib_symbols.append(f"""\t\t(symbol "irrigation:SSD1306_OLED"
\t\t\t(pin_names (offset 1.016))
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(property "Reference" "U"
\t\t\t\t(at 0 10.16 0)
\t\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t)
\t\t\t(property "Value" "SSD1306_128x64"
\t\t\t\t(at 0 -7.62 0)
\t\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t\t)
\t\t\t(property "Description" "SSD1306 128x64 OLED Display Module (I2C addr 0x3C)"
\t\t\t\t(at 0 0 0)
\t\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t\t)
\t\t\t(symbol "SSD1306_OLED_0_1"
\t\t\t\t(rectangle
\t\t\t\t\t(start -2.54 7.62)
\t\t\t\t\t(end 5.08 -5.08)
\t\t\t\t\t(stroke (width 0.254) (type default))
\t\t\t\t\t(fill (type background))
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "SSD1306_OLED_1_1"
{chr(10).join(oled_pins)}
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)""")

# --- PCF8574 I/O Expander ---
pcf_pin_defs = [
    ("1", "A0", "input"), ("2", "A1", "input"), ("3", "A2", "input"),
    ("4", "P0", "bidirectional"), ("5", "P1", "bidirectional"),
    ("6", "P2", "bidirectional"), ("7", "P3", "bidirectional"),
    ("8", "GND", "power_in"),
    ("9", "P4", "bidirectional"), ("10", "P5", "bidirectional"),
    ("11", "P6", "bidirectional"), ("12", "P7", "bidirectional"),
    ("13", "INT", "open_collector"),
    ("14", "SCL", "input"), ("15", "SDA", "bidirectional"),
    ("16", "VCC", "power_in"),
]
pcf_pins = []
for i in range(8):
    y = 10.16 - i * 2.54
    num, name, ptype = pcf_pin_defs[i]
    pcf_pins.append(make_pin(num, name, ptype, -(10.16 + 5.08), y, 0, 5.08))
for i in range(8):
    y = 10.16 - i * 2.54
    num, name, ptype = pcf_pin_defs[i + 8]
    pcf_pins.append(make_pin(num, name, ptype, (10.16 + 5.08), y, 180, 5.08))

lib_symbols.append(f"""\t\t(symbol "irrigation:PCF8574"
\t\t\t(pin_names (offset 1.016))
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(property "Reference" "U"
\t\t\t\t(at 0 15.24 0)
\t\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t)
\t\t\t(property "Value" "PCF8574"
\t\t\t\t(at 0 -12.7 0)
\t\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t\t)
\t\t\t(property "Description" "PCF8574 8-bit I/O Expander (I2C addr 0x20)"
\t\t\t\t(at 0 0 0)
\t\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t\t)
\t\t\t(symbol "PCF8574_0_1"
\t\t\t\t(rectangle
\t\t\t\t\t(start -10.16 12.7)
\t\t\t\t\t(end 10.16 -10.16)
\t\t\t\t\t(stroke (width 0.254) (type default))
\t\t\t\t\t(fill (type background))
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "PCF8574_1_1"
{chr(10).join(pcf_pins)}
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)""")

# --- Power symbols ---
def make_power_symbol(name, sym_name, description, is_gnd=False):
    if is_gnd:
        graphics = f"""\t\t\t(symbol "{sym_name}_0_1"
\t\t\t\t(polyline
\t\t\t\t\t(pts (xy 0 0) (xy 0 -1.27))
\t\t\t\t\t(stroke (width 0) (type default))
\t\t\t\t\t(fill (type none))
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts (xy -1.27 -1.27) (xy 1.27 -1.27))
\t\t\t\t\t(stroke (width 0.254) (type default))
\t\t\t\t\t(fill (type none))
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts (xy -0.762 -1.778) (xy 0.762 -1.778))
\t\t\t\t\t(stroke (width 0.254) (type default))
\t\t\t\t\t(fill (type none))
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts (xy -0.254 -2.286) (xy 0.254 -2.286))
\t\t\t\t\t(stroke (width 0.254) (type default))
\t\t\t\t\t(fill (type none))
\t\t\t\t)
\t\t\t)"""
        val_y = -3.81
    else:
        graphics = f"""\t\t\t(symbol "{sym_name}_0_1"
\t\t\t\t(polyline
\t\t\t\t\t(pts (xy -0.762 1.27) (xy 0 2.54))
\t\t\t\t\t(stroke (width 0) (type default))
\t\t\t\t\t(fill (type none))
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts (xy 0 2.54) (xy 0.762 1.27))
\t\t\t\t\t(stroke (width 0) (type default))
\t\t\t\t\t(fill (type none))
\t\t\t\t)
\t\t\t\t(polyline
\t\t\t\t\t(pts (xy 0 0) (xy 0 2.54))
\t\t\t\t\t(stroke (width 0) (type default))
\t\t\t\t\t(fill (type none))
\t\t\t\t)
\t\t\t)"""
        val_y = 3.556

    return f"""\t\t(symbol "power:{name}"
\t\t\t(power)
\t\t\t(pin_numbers (hide yes))
\t\t\t(pin_names (offset 0) (hide yes))
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(property "Reference" "#PWR"
\t\t\t\t(at 0 {-3.81 if not is_gnd else 3.81} 0)
\t\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t\t)
\t\t\t(property "Value" "{name}"
\t\t\t\t(at 0 {val_y} 0)
\t\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t\t)
\t\t\t(property "Description" "{description}"
\t\t\t\t(at 0 0 0)
\t\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t\t)
{graphics}
\t\t\t(symbol "{sym_name}_1_1"
\t\t\t\t(pin power_in line
\t\t\t\t\t(at 0 0 90)
\t\t\t\t\t(length 0)
\t\t\t\t\t(name "~" (effects (font (size 1.27 1.27))))
\t\t\t\t\t(number "1" (effects (font (size 1.27 1.27))))
\t\t\t\t)
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)"""

lib_symbols.append(make_power_symbol("+3V3", "+3V3", "Power symbol +3V3"))
lib_symbols.append(make_power_symbol("+5V", "+5V", "Power symbol +5V"))
lib_symbols.append(make_power_symbol("+12V", "+12V", "Power symbol +12V"))
lib_symbols.append(make_power_symbol("GND", "GND", "Power symbol GND", is_gnd=True))


# ============================================================
# Accumulator lists
# ============================================================
instances = []
labels = []
wires = []
texts = []

# Title
texts.append(make_text("ESP32 Irrigation Controller", 200, 20, 3.0))
texts.append(make_text("20 Zones: ESP32 -> 3x SN74HC595 -> 3x ULN2003 -> Solenoid Valves", 200, 27, 1.5))

# ============================================================
# ESP32 pin coordinate helpers
# ============================================================
esp_x, esp_y = 80.0, 100.0

def esp_left_pin_pos(i):
    rel_x = -(esp_box_w/2 + 5.08)
    rel_y = esp_box_top - (i + 1) * 2.54
    return (esp_x + rel_x, esp_y - rel_y)

def esp_right_pin_pos(i):
    rel_x = (esp_box_w/2 + 5.08)
    rel_y = esp_box_top - (i + 1) * 2.54
    return (esp_x + rel_x, esp_y - rel_y)

# Build GPIO lookup
gpio_to_esp = {}
for i, (num, name, ptype) in enumerate(ESP32_PINS_LEFT):
    if "GPIO" in name:
        gpio_to_esp[name.split("/")[0]] = ("left", i)
for i, (num, name, ptype) in enumerate(ESP32_PINS_RIGHT):
    if "GPIO" in name:
        gpio_to_esp[name.split("/")[0]] = ("right", i)

# ============================================================
# Place ESP32
# ============================================================
esp_pin_uuids = [(str(i+1), uid()) for i in range(30)]
instances.append(place_symbol("irrigation:ESP32-DevKit", "U1", "ESP32-DevKit",
    esp_x, esp_y, pin_uuids=esp_pin_uuids, description="ESP32 DevKit Module"))

# ESP32 power connections
# 3V3 = left pin 1
px, py = esp_left_pin_pos(1)
instances.append(next_pwr("power:+3V3", "+3V3", px - 2.54, py - 2.54))
wires.append(make_wire(px, py, px - 2.54, py))
wires.append(make_wire(px - 2.54, py, px - 2.54, py - 2.54))

# GND = left pin 0
px, py = esp_left_pin_pos(0)
instances.append(next_pwr("power:GND", "GND", px - 2.54, py + 2.54))
wires.append(make_wire(px, py, px - 2.54, py))
wires.append(make_wire(px - 2.54, py, px - 2.54, py + 2.54))

# VIN = left pin 14
px, py = esp_left_pin_pos(14)
instances.append(next_pwr("power:+12V", "+12V", px - 2.54, py - 2.54))
wires.append(make_wire(px, py, px - 2.54, py))
wires.append(make_wire(px - 2.54, py, px - 2.54, py - 2.54))

# GND = right pin 0
px, py = esp_right_pin_pos(0)
instances.append(next_pwr("power:GND", "GND", px + 2.54, py + 2.54))
wires.append(make_wire(px, py, px + 2.54, py))
wires.append(make_wire(px + 2.54, py, px + 2.54, py + 2.54))

# Shift register control labels on ESP32
for gpio_name, label_text in [
    (SHIFT_REG_DATA, "SR_DATA"), (SHIFT_REG_CLOCK, "SR_CLK"), (SHIFT_REG_LATCH, "SR_LATCH")
]:
    side, idx = gpio_to_esp[gpio_name]
    if side == "right":
        px, py = esp_right_pin_pos(idx)
        labels.append(make_global_label(label_text, px + 2.54, py, 0))
        wires.append(make_wire(px, py, px + 2.54, py))
    else:
        px, py = esp_left_pin_pos(idx)
        labels.append(make_global_label(label_text, px - 2.54, py, 180))
        wires.append(make_wire(px, py, px - 2.54, py))

# I2C labels on ESP32
for gpio_name, label_text in [(I2C_SDA, "SDA"), (I2C_SCL, "SCL")]:
    side, idx = gpio_to_esp[gpio_name]
    if side == "right":
        px, py = esp_right_pin_pos(idx)
        labels.append(make_global_label(label_text, px + 2.54, py, 0))
        wires.append(make_wire(px, py, px + 2.54, py))
    else:
        px, py = esp_left_pin_pos(idx)
        labels.append(make_global_label(label_text, px - 2.54, py, 180))
        wires.append(make_wire(px, py, px - 2.54, py))

# Flow sensor label on ESP32
side, idx = gpio_to_esp[FLOW_PIN]
if side == "left":
    px, py = esp_left_pin_pos(idx)
    labels.append(make_global_label("FLOW_PULSE", px - 2.54, py, 180))
    wires.append(make_wire(px, py, px - 2.54, py))
else:
    px, py = esp_right_pin_pos(idx)
    labels.append(make_global_label("FLOW_PULSE", px + 2.54, py, 0))
    wires.append(make_wire(px, py, px + 2.54, py))


# ============================================================
# SN74HC595 pin position helpers
# ============================================================
# Symbol-relative pin positions (same layout as lib symbol):
# Left pins: x = -(sr_box_w/2 + 5.08), y = sr_box_top - (i+1)*2.54
# Right pins: same y, x = +(sr_box_w/2 + 5.08)
def sr_left_pin_pos(cx, cy, i):
    """World position of left-side pin i for a SR placed at (cx, cy)."""
    rel_x = -(sr_box_w/2 + 5.08)
    rel_y = sr_box_top - (i + 1) * 2.54
    return (cx + rel_x, cy - rel_y)

def sr_right_pin_pos(cx, cy, i):
    rel_x = (sr_box_w/2 + 5.08)
    rel_y = sr_box_top - (i + 1) * 2.54
    return (cx + rel_x, cy - rel_y)

def uln_left_pin_pos(cx, cy, i):
    rel_x = -(uln_box_w/2 + 5.08)
    rel_y = uln_box_top - (i + 1) * 2.54
    return (cx + rel_x, cy - rel_y)

def uln_right_pin_pos(cx, cy, i):
    rel_x = (uln_box_w/2 + 5.08)
    rel_y = uln_box_top - (i + 1) * 2.54
    return (cx + rel_x, cy - rel_y)


# ============================================================
# Place 3x SN74HC595 + 3x ULN2003 + 20 valve connectors
# ============================================================
# Layout: SR and ULN side by side, repeated vertically for each group
# SR outputs QA-QH map to ULN inputs IN1-IN7 (7 channels per ULN)
# SR1: outputs 0-7   -> ULN1 (7 of 8) + ULN2 (1 of 7)
# Actually: 3x SR = 24 outputs, 3x ULN = 21 inputs. Using 20.
# Simpler mapping: SR output N -> ULN (N//7) input (N%7)
# SR1 QA-QG (0-6)  -> ULN1 IN1-IN7 (zones 0-6)
# SR1 QH (7)       -> ULN2 IN1     (zone 7)
# SR2 QA-QE (8-12) -> ULN2 IN2-IN6 (zones 8-12)
# SR2 QF (13)      -> ULN2 IN7     (zone 13)
# SR2 QG-QH+SR3... -> ULN3         (zones 14-19)
#
# Actually let's keep it simple and logical:
# ULN1: zones 0-6   (7 channels) fed from SR1 QA(15)-QG(6) = outputs 0-6
# ULN2: zones 7-13  (7 channels) fed from SR1 QH(7) + SR2 QA-QF(8-13)
# ULN3: zones 14-19 (6 channels) fed from SR2 QG-QH(14-15) + SR3 QA-QD(16-19)
#
# SR output mapping (SN74HC595 output bit -> pin):
#   Bit 0 = QA (pin 15), Bit 1 = QB (pin 1), Bit 2 = QC (pin 2),
#   Bit 3 = QD (pin 3),  Bit 4 = QE (pin 4), Bit 5 = QF (pin 5),
#   Bit 6 = QG (pin 6),  Bit 7 = QH (pin 7)
# Left side pins 0-7:  QB(1), QC(2), QD(3), QE(4), QF(5), QG(6), QH(7), GND(8)
# Right side pins 0-7: VCC(16), QA(15), SER(14), ~OE(13), RCLK(12), SRCLK(11), ~SRCLR(10), QH'(9)

# SR output indices for each SR (which left/right pin index for each output bit):
# QA = right index 1, QB = left index 0, QC = left index 1, QD = left index 2,
# QE = left index 3, QF = left index 4, QG = left index 5, QH = left index 6

texts.append(make_text("Shift Registers + Darlington Drivers", 230, 40, 2.0))

sr_base_x = 200.0
sr_base_y = 65.0
sr_vertical_spacing = 70.0
uln_offset_x = 80.0  # ULN placed to the right of SR

# Zone-to-SR-output mapping: zone N uses SR output N
# SR 0 handles outputs 0-7, SR 1 handles 8-15, SR 2 handles 16-23
# Each SR output bit -> pin on the SR:
#   bit 0 -> QA (right idx 1)
#   bit 1 -> QB (left idx 0)
#   bit 2 -> QC (left idx 1)
#   bit 3 -> QD (left idx 2)
#   bit 4 -> QE (left idx 3)
#   bit 5 -> QF (left idx 4)
#   bit 6 -> QG (left idx 5)
#   bit 7 -> QH (left idx 6)

def sr_output_pin_pos(sr_cx, sr_cy, bit):
    """Get world position of SR output for a given bit (0-7)."""
    if bit == 0:
        return sr_right_pin_pos(sr_cx, sr_cy, 1)  # QA = right index 1
    else:
        return sr_left_pin_pos(sr_cx, sr_cy, bit - 1)  # QB-QH = left index 0-6

# Zone-to-ULN mapping:
# ULN1: zones 0-6, ULN2: zones 7-13, ULN3: zones 14-19 (only 6 used)
zone_to_uln = []
for z in range(NUM_ZONES):
    uln_idx = z // 7
    uln_ch = z % 7  # 0-6 = IN1-IN7
    zone_to_uln.append((uln_idx, uln_ch))

# Place the 3 SR + 3 ULN groups
sr_positions = []
uln_positions = []
valve_connector_start_x = 370.0

for g in range(3):
    sr_cx = sr_base_x
    sr_cy = sr_base_y + g * sr_vertical_spacing
    sr_positions.append((sr_cx, sr_cy))

    sr_pin_uuids = [(str(i+1), uid()) for i in range(16)]
    instances.append(place_symbol("irrigation:SN74HC595", f"U{g+2}", f"SN74HC595_{g+1}",
        sr_cx, sr_cy, pin_uuids=sr_pin_uuids,
        description=f"Shift Register {g+1} of {NUM_SR}"))

    # SR power: VCC = right index 0, GND = left index 7
    px, py = sr_right_pin_pos(sr_cx, sr_cy, 0)  # VCC
    instances.append(next_pwr("power:+5V", "+5V", px + 2.54, py - 2.54))
    wires.append(make_wire(px, py, px + 2.54, py))
    wires.append(make_wire(px + 2.54, py, px + 2.54, py - 2.54))

    px, py = sr_left_pin_pos(sr_cx, sr_cy, 7)  # GND
    instances.append(next_pwr("power:GND", "GND", px - 2.54, py + 2.54))
    wires.append(make_wire(px, py, px - 2.54, py))
    wires.append(make_wire(px - 2.54, py, px - 2.54, py + 2.54))

    # ~OE tied to GND (always enabled) = right index 3
    px, py = sr_right_pin_pos(sr_cx, sr_cy, 3)  # ~OE
    instances.append(next_pwr("power:GND", "GND", px + 2.54, py + 2.54))
    wires.append(make_wire(px, py, px + 2.54, py))
    wires.append(make_wire(px + 2.54, py, px + 2.54, py + 2.54))

    # ~SRCLR tied to VCC (never clear) = right index 6
    px, py = sr_right_pin_pos(sr_cx, sr_cy, 6)  # ~SRCLR
    instances.append(next_pwr("power:+5V", "+5V", px + 2.54, py - 2.54))
    wires.append(make_wire(px, py, px + 2.54, py))
    wires.append(make_wire(px + 2.54, py, px + 2.54, py - 2.54))

    # SRCLK = right index 5 -> SR_CLK
    px, py = sr_right_pin_pos(sr_cx, sr_cy, 5)
    labels.append(make_global_label("SR_CLK", px + 2.54, py, 0))
    wires.append(make_wire(px, py, px + 2.54, py))

    # RCLK = right index 4 -> SR_LATCH
    px, py = sr_right_pin_pos(sr_cx, sr_cy, 4)
    labels.append(make_global_label("SR_LATCH", px + 2.54, py, 0))
    wires.append(make_wire(px, py, px + 2.54, py))

    # SER (data in) = right index 2
    px, py = sr_right_pin_pos(sr_cx, sr_cy, 2)  # SER
    if g == 0:
        # First SR gets data from ESP32
        labels.append(make_global_label("SR_DATA", px + 2.54, py, 0))
        wires.append(make_wire(px, py, px + 2.54, py))
    else:
        # Subsequent SRs get data from previous SR's QH'
        labels.append(make_global_label(f"SR{g}_TO_SR{g+1}", px + 2.54, py, 0))
        wires.append(make_wire(px, py, px + 2.54, py))

    # QH' (serial out) = right index 7
    px, py = sr_right_pin_pos(sr_cx, sr_cy, 7)  # QH'
    if g < NUM_SR - 1:
        labels.append(make_global_label(f"SR{g+1}_TO_SR{g+2}", px + 2.54, py, 0))
        wires.append(make_wire(px, py, px + 2.54, py))
    # Last SR's QH' is unused (no label needed)

    # --- ULN2003 for this group ---
    uln_cx = sr_cx + uln_offset_x
    uln_cy = sr_cy
    uln_positions.append((uln_cx, uln_cy))

    uln_pin_uuids = [(str(i+1), uid()) for i in range(16)]
    instances.append(place_symbol("irrigation:ULN2003", f"U{g+5}", f"ULN2003_{g+1}",
        uln_cx, uln_cy, pin_uuids=uln_pin_uuids,
        description=f"Darlington Driver {g+1} of {NUM_ULN}"))

    # ULN GND = left index 7
    px, py = uln_left_pin_pos(uln_cx, uln_cy, 7)
    instances.append(next_pwr("power:GND", "GND", px - 2.54, py + 2.54))
    wires.append(make_wire(px, py, px - 2.54, py))
    wires.append(make_wire(px - 2.54, py, px - 2.54, py + 2.54))

    # ULN COM = right index 7 -> +12V (freewheeling diode common for solenoids)
    px, py = uln_right_pin_pos(uln_cx, uln_cy, 7)
    instances.append(next_pwr("power:+12V", "+12V", px + 2.54, py - 2.54))
    wires.append(make_wire(px, py, px + 2.54, py))
    wires.append(make_wire(px + 2.54, py, px + 2.54, py - 2.54))

# Now wire SR outputs -> ULN inputs, and ULN outputs -> valve connectors
# Zone N: SR = N//8, bit = N%8; ULN = N//7, channel = N%7
valve_start_y = 50.0
valve_spacing = 12.7

texts.append(make_text("Valve Connectors", valve_connector_start_x, valve_start_y - 10, 2.0))

for zone in range(NUM_ZONES):
    sr_idx = zone // 8
    sr_bit = zone % 8
    uln_idx, uln_ch = zone_to_uln[zone]

    sr_cx, sr_cy = sr_positions[sr_idx]
    uln_cx, uln_cy = uln_positions[uln_idx]

    # Create net label for SR output -> ULN input connection
    net_name = f"SR_Q{zone}"

    # Label on SR output pin
    out_x, out_y = sr_output_pin_pos(sr_cx, sr_cy, sr_bit)
    if sr_bit == 0:
        # QA is on the right side — need to route right
        # But we want labels going left toward ULN... let's use global labels
        labels.append(make_global_label(net_name, out_x + 2.54, out_y, 0))
        wires.append(make_wire(out_x, out_y, out_x + 2.54, out_y))
    else:
        # QB-QH are on the left side
        labels.append(make_global_label(net_name, out_x - 2.54, out_y, 180))
        wires.append(make_wire(out_x, out_y, out_x - 2.54, out_y))

    # Label on ULN input pin (left side, index = uln_ch)
    in_x, in_y = uln_left_pin_pos(uln_cx, uln_cy, uln_ch)
    labels.append(make_global_label(net_name, in_x - 2.54, in_y, 180))
    wires.append(make_wire(in_x, in_y, in_x - 2.54, in_y))

    # Label on ULN output pin -> valve connector
    # ULN outputs: OUT1=right idx 0, OUT2=right idx 1, ... OUT7=right idx 6
    uln_out_x, uln_out_y = uln_right_pin_pos(uln_cx, uln_cy, uln_ch)
    valve_net = f"VALVE_{zone}"
    labels.append(make_global_label(valve_net, uln_out_x + 2.54, uln_out_y, 0))
    wires.append(make_wire(uln_out_x, uln_out_y, uln_out_x + 2.54, uln_out_y))

    # Place valve connector (2-pin: +12V, switched GND from ULN)
    jx = valve_connector_start_x
    jy = valve_start_y + zone * valve_spacing

    pin_uuids = [("1", uid()), ("2", uid())]
    instances.append(place_symbol("irrigation:Conn_01x02", f"J{zone+1}", f"Zone {zone}",
        jx, jy, pin_uuids=pin_uuids,
        description=f"Solenoid valve connector zone {zone}"))

    # Pin positions for Conn_01x02: box_h=7.62, box_top=3.81
    # pin 1 at rel (-7.62, 1.27) -> world (jx - 7.62, jy - 1.27)
    # pin 2 at rel (-7.62, -1.27) -> world (jx - 7.62, jy + 1.27)
    p1x, p1y = jx - 7.62, jy - 1.27  # Pin 1 = +12V (solenoid power)
    p2x, p2y = jx - 7.62, jy + 1.27  # Pin 2 = switched GND from ULN

    # Pin 1 -> +12V
    instances.append(next_pwr("power:+12V", "+12V", p1x - 2.54, p1y - 2.54))
    wires.append(make_wire(p1x, p1y, p1x - 2.54, p1y))
    wires.append(make_wire(p1x - 2.54, p1y, p1x - 2.54, p1y - 2.54))

    # Pin 2 -> valve net (from ULN output, sinks to GND when active)
    labels.append(make_global_label(valve_net, p2x - 2.54, p2y, 180))
    wires.append(make_wire(p2x, p2y, p2x - 2.54, p2y))


# ============================================================
# Place SSD1306 OLED display
# ============================================================
oled_x, oled_y = 50.0, 55.0
texts.append(make_text("OLED Display (I2C 0x3C)", oled_x, oled_y - 15, 1.5))

oled_pin_uuids = [("1", uid()), ("2", uid()), ("3", uid()), ("4", uid())]
instances.append(place_symbol("irrigation:SSD1306_OLED", "U8", "SSD1306_128x64",
    oled_x, oled_y, pin_uuids=oled_pin_uuids,
    description="SSD1306 128x64 OLED Display (I2C 0x3C)"))

oled_gnd_x, oled_gnd_y = oled_x - 7.62, oled_y - 5.08
oled_vcc_x, oled_vcc_y = oled_x - 7.62, oled_y - 2.54
oled_scl_x, oled_scl_y = oled_x - 7.62, oled_y
oled_sda_x, oled_sda_y = oled_x - 7.62, oled_y + 2.54

instances.append(next_pwr("power:GND", "GND", oled_gnd_x - 2.54, oled_gnd_y + 2.54))
wires.append(make_wire(oled_gnd_x, oled_gnd_y, oled_gnd_x - 2.54, oled_gnd_y))
wires.append(make_wire(oled_gnd_x - 2.54, oled_gnd_y, oled_gnd_x - 2.54, oled_gnd_y + 2.54))

instances.append(next_pwr("power:+3V3", "+3V3", oled_vcc_x - 2.54, oled_vcc_y - 2.54))
wires.append(make_wire(oled_vcc_x, oled_vcc_y, oled_vcc_x - 2.54, oled_vcc_y))
wires.append(make_wire(oled_vcc_x - 2.54, oled_vcc_y, oled_vcc_x - 2.54, oled_vcc_y - 2.54))

labels.append(make_global_label("SCL", oled_scl_x - 2.54, oled_scl_y, 180))
wires.append(make_wire(oled_scl_x, oled_scl_y, oled_scl_x - 2.54, oled_scl_y))

labels.append(make_global_label("SDA", oled_sda_x - 2.54, oled_sda_y, 180))
wires.append(make_wire(oled_sda_x, oled_sda_y, oled_sda_x - 2.54, oled_sda_y))


# ============================================================
# Place PCF8574 I/O Expander
# ============================================================
pcf_x, pcf_y = 50.0, 130.0
texts.append(make_text("PCF8574 I/O Expander (I2C 0x20)", pcf_x, pcf_y - 22, 1.5))

pcf_pin_uuids_inst = [(str(i+1), uid()) for i in range(16)]
instances.append(place_symbol("irrigation:PCF8574", "U9", "PCF8574",
    pcf_x, pcf_y, pin_uuids=pcf_pin_uuids_inst,
    description="PCF8574 8-bit I/O Expander (I2C addr 0x20)"))

def pcf_left_pin_pos(i):
    return (pcf_x - 15.24, pcf_y - (10.16 - i * 2.54))

def pcf_right_pin_pos(i):
    return (pcf_x + 15.24, pcf_y - (10.16 - i * 2.54))

# A0, A1, A2 tied to GND
for i in range(3):
    px, py = pcf_left_pin_pos(i)
    instances.append(next_pwr("power:GND", "GND", px - 2.54, py + 2.54))
    wires.append(make_wire(px, py, px - 2.54, py))
    wires.append(make_wire(px - 2.54, py, px - 2.54, py + 2.54))

# GND (pin 8 = left index 7)
px, py = pcf_left_pin_pos(7)
instances.append(next_pwr("power:GND", "GND", px - 2.54, py + 2.54))
wires.append(make_wire(px, py, px - 2.54, py))
wires.append(make_wire(px - 2.54, py, px - 2.54, py + 2.54))

# VCC (pin 16 = right index 7)
px, py = pcf_right_pin_pos(7)
instances.append(next_pwr("power:+3V3", "+3V3", px + 2.54, py - 2.54))
wires.append(make_wire(px, py, px + 2.54, py))
wires.append(make_wire(px + 2.54, py, px + 2.54, py - 2.54))

# SCL (pin 14 = right index 5)
px, py = pcf_right_pin_pos(5)
labels.append(make_global_label("SCL", px + 2.54, py, 0))
wires.append(make_wire(px, py, px + 2.54, py))

# SDA (pin 15 = right index 6)
px, py = pcf_right_pin_pos(6)
labels.append(make_global_label("SDA", px + 2.54, py, 0))
wires.append(make_wire(px, py, px + 2.54, py))

# P0-P7 labels
for i in range(4):
    px, py = pcf_left_pin_pos(3 + i)
    labels.append(make_global_label(f"PCF_P{i}", px - 2.54, py, 180))
    wires.append(make_wire(px, py, px - 2.54, py))
for i in range(4):
    px, py = pcf_right_pin_pos(i)
    labels.append(make_global_label(f"PCF_P{4+i}", px + 2.54, py, 0))
    wires.append(make_wire(px, py, px + 2.54, py))

# INT (pin 13 = right index 4)
px, py = pcf_right_pin_pos(4)
labels.append(make_global_label("PCF_INT", px + 2.54, py, 0))
wires.append(make_wire(px, py, px + 2.54, py))


# ============================================================
# Place Flow Sensor connector
# ============================================================
flow_x, flow_y = 50.0, 180.0
texts.append(make_text("Flow Sensor (Pulse Counter on GPIO34)", flow_x, flow_y - 12, 1.5))

flow_pin_uuids = [("1", uid()), ("2", uid()), ("3", uid())]
instances.append(place_symbol("irrigation:Conn_01x03", "J21", "Flow_Sensor",
    flow_x, flow_y, pin_uuids=flow_pin_uuids,
    description="Flow sensor connector (pulse counter)"))

fp1x, fp1y = flow_x - 7.62, flow_y - 2.54
fp2x, fp2y = flow_x - 7.62, flow_y
fp3x, fp3y = flow_x - 7.62, flow_y + 2.54

instances.append(next_pwr("power:+3V3", "+3V3", fp1x - 2.54, fp1y - 2.54))
wires.append(make_wire(fp1x, fp1y, fp1x - 2.54, fp1y))
wires.append(make_wire(fp1x - 2.54, fp1y, fp1x - 2.54, fp1y - 2.54))

labels.append(make_global_label("FLOW_PULSE", fp2x - 2.54, fp2y, 180))
wires.append(make_wire(fp2x, fp2y, fp2x - 2.54, fp2y))

instances.append(next_pwr("power:GND", "GND", fp3x - 2.54, fp3y + 2.54))
wires.append(make_wire(fp3x, fp3y, fp3x - 2.54, fp3y))
wires.append(make_wire(fp3x - 2.54, fp3y, fp3x - 2.54, fp3y + 2.54))


# ============================================================
# Place Power Input connector
# ============================================================
pwr_x, pwr_y = 50.0, 210.0
texts.append(make_text("Power Input (12V DC)", pwr_x, pwr_y - 12, 1.5))

pwr_pin_uuids = [("1", uid()), ("2", uid())]
instances.append(place_symbol("irrigation:Conn_01x02", "J22", "Power_In",
    pwr_x, pwr_y, pin_uuids=pwr_pin_uuids,
    description="Power input connector 12V"))

pp1x, pp1y = pwr_x - 7.62, pwr_y - 1.27
pp2x, pp2y = pwr_x - 7.62, pwr_y + 1.27

instances.append(next_pwr("power:+12V", "+12V", pp1x - 2.54, pp1y - 2.54))
wires.append(make_wire(pp1x, pp1y, pp1x - 2.54, pp1y))
wires.append(make_wire(pp1x - 2.54, pp1y, pp1x - 2.54, pp1y - 2.54))

instances.append(next_pwr("power:GND", "GND", pp2x - 2.54, pp2y + 2.54))
wires.append(make_wire(pp2x, pp2y, pp2x - 2.54, pp2y))
wires.append(make_wire(pp2x - 2.54, pp2y, pp2x - 2.54, pp2y + 2.54))


# ============================================================
# Assemble the full schematic
# ============================================================
output = f"""(kicad_sch
\t(version 20250114)
\t(generator "eeschema")
\t(generator_version "9.0")
\t(uuid "{ROOT_UUID}")
\t(paper "A2")
\t(lib_symbols
{chr(10).join(lib_symbols)}
\t)
{chr(10).join(texts)}
{chr(10).join(instances)}
{chr(10).join(labels)}
{chr(10).join(wires)}
\t(sheet_instances
\t\t(path "/"
\t\t\t(page "1")
\t\t)
\t)
\t(embedded_fonts no)
)
"""

with open("esp_watering.kicad_sch", "w") as f:
    f.write(output)

print("Generated schematic with:")
print(f"  - ESP32 DevKit (U1) — 3 GPIOs for shift register control")
print(f"  - 3x SN74HC595 shift registers (U2-U4) — chained, 24 outputs")
print(f"  - 3x ULN2003 Darlington drivers (U5-U7) — 20 channels used")
print(f"  - 20 solenoid valve connectors (J1-J20)")
print(f"  - SSD1306 OLED display (U8, I2C 0x3C)")
print(f"  - PCF8574 I/O expander (U9, I2C 0x20)")
print(f"  - Flow sensor connector (J21)")
print(f"  - Power input connector (J22)")
print(f"  - {len(wires)} wires, {len(labels)} labels, {pwr_idx - 1} power symbols")
print(f"  - Paper size: A2 (for 20-zone layout)")
