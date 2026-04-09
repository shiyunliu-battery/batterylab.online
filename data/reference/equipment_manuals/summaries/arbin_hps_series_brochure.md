# Arbin Ultra-High Precision Battery Tester (HPS Series)

## Specifications
- **Voltage Range:** -6 to 6V
- **Current Ranges:** Multiple automatically switching ranges provided per channel (5A, 1A, 100mA, 10mA, 1mA, 100µA).
- **Precision Limits:** Up to 10 ppm measurement precision.
- **Resolution:** 24-bit hardware resolution across all six current ranges.
- **Hardware Architecture:** Embedded MCU per test channel enabling real-time calculations of capacity, energy, IR, power, and efficiency metrics on the hardware side rather than at the PC layer.
- **Sampling & Control:** Features a temperature-controlled sampling circuit designed specifically to reduce noise and variance, making it highly suited for early life degradation tracking (HPC) and precise coulombic efficiency (CE) testing.
- **Supplemental I/O:** Built-in secondary voltage input, PT100 temperature input, CAN-Bus interfacing, and dedicated EIS capability per channel.

## Operating Boundaries & Lab Use
- **Primary Use Case:** The HPS series is explicitly engineered for Ultra-High Precision Coulometry (HPC). Its sub-milliamp current ranges (down to 100µA) and extreme low-noise capability (10 ppm) are ideal for detecting subtle parasitic reactions, measuring strict cycle-to-cycle thermodynamic changes, and predicting long-term cell life early in testing cycles without requiring multi-year campaigns.
- **Testing Exclusions:** With a maximum 5A ceiling on general high-precision units, it is not suitable for high C-rate throughput on large-format EV cells or packs; it is intended for rigorous characterization (coin cells, small pouches, or low C-rate sweeps on commercial 18650/21700s).
- **Thermal Management Integration:** May optionally integrate with the Arbin MZTC chamber to provide a tight benchtop isothermal testing environment, which is highly recommended to defend the 10ppm precision against ambient lab temperature drift.
