[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
# Home Assistant Ultimaker printers

![lovelace](https://github.com/jellespijker/home-assistant-ultimaker/raw/main/resources/lovelace.png)

Adds support for Ultimaker printers with the following sensors and features:

- Printer status and activity
- Print job state and progress
- Print job ETA and time remaining
- Current and target temperatures for bed and hotends
- Bed and hotend types
- Fan speed
- Firmware version and update availability
- Network and hardware info
- Camera live stream and snapshots
- Update entity for firmware
- All entities grouped under a single device

{% if installed %}
## Changes compared to your installed version:

{% if version_installed.replace("v", "").replace("V", "").replace(".","") | int < 20 %}
### 🚨 Breaking Changes (0.2.0)
This version introduces a complete refactor of the integration:
- YAML configuration has been **removed**.
- Integration now uses **config_flow** and can be configured via the Home Assistant UI.
- Entity names and structure have been standardized. You may need to reconfigure Lovelace cards and automations.
- Some sensors from previous versions have been **renamed, merged or removed** for consistency.

### ✨ Features
- Camera stream and snapshot support
- Firmware update check via `update` entity
- Extended device info (model, firmware, hardware, serial)
- Support for Home Assistant OS 2023.5 and Python 3.10+
- Automatic grouping of all entities under a single device

### 🐛 Bugfixes
- Improved error handling and reconnection logic
- Fixed detection of hotend types and null values

{% endif %}

{% else %}

## Highlights

- Fully UI-configurable integration (no more YAML)
- Sensor entities grouped by device
- Support for camera stream and snapshots
- Update entity for firmware
- Better performance and error handling

## Installation

This integration is available through [HACS](https://hacs.xyz). After installing, go to **Settings > Devices & Services > Add Integration**, and search for **Ultimaker**.

{% endif %}