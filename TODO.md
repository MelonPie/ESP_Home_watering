# TODO

- **Replace flow sensor (FS300A → YF-B6 or similar low-flow).** Current FS300A stalls below ~1 L/min, so slow leaks produce zero pulses and the leak detector cannot see them (observed: `flow_rate` stuck at 0.00 during a real leak). Peak system flow is ~3 L/min, which fits within the YF-B6's range. After swap: recalibrate using the 5 L bucket method and update the calibration in `esphome/irrigation-micr-2.yaml:144-162`.
