# Home Assistant Integration: Ultimaker

[![hacs\_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)

Custom integration for monitoring **UltiMaker 3**, **S3**, **S5**, **S7** and **S8** 3D printers from Home Assistant. Provides detailed real-time data, camera stream, and firmware updates.

---

## Features

* 🖨️ Print job status, progress, ETA, and remaining time
* 🔥 Extruder and bed temperatures
* 🌡️ Ambient temperature
* ⚙️ System firmware, hardware info, uptime
* 📸 Live camera view and snapshots
* 🔄 Firmware update availability
* 📊 Sensor data with proper device classes and icons
* 🧠 Uses DataUpdateCoordinator for efficient polling
* 📁 Fully supports config flow (UI setup)

---

## Installation

### Option 1: HACS (Recommended)

1. Go to **HACS > Integrations**
2. Click **+ Explore & Download Repositories**
3. Search for `Ultimaker` and add it as a custom integration
4. Restart Home Assistant
5. Add the integration from **Settings > Devices & Services**

### Option 2: Manual

1. Copy the `ultimaker/` folder to `custom_components/` in your Home Assistant config
2. Restart Home Assistant
3. Add the integration from **Settings > Devices & Services**

---

## Configuration

No YAML required.

After installation, go to **Settings > Devices & Services**, click **Add Integration**, and select **Ultimaker**. Enter the printer's IP address and a name.


![setup](https://github.com/jellespijker/home-assistant-ultimaker/raw/main/resources/setup.png)
---

## Available Entities

* Ambient Temperature
* Bed Temperature
* Bed Target Temperature
* Extruder 0 Temperature
* Extruder 0 Target Temperature
* ETA
* Firmware Version
* Hardware Revision
* Layer Number
* Material 0 Length Remaining
* Material 0 Type
* Model
* Nozzle Diameter
* Print Duration
* Print Duration Elapsed
* Print Duration Remaining
* Print Job Name
* Printer Status
* Serial Number
* Total Extrusion
* Total Hot Time
* Total Print Time
* Uptime
* Variant
* Camera (Stream & Snapshot)
* Firmware Update Available

![sensors](https://github.com/jellespijker/home-assistant-ultimaker/raw/main/resources/sensors.png)
---

## Breaking Changes

This version is a complete rewrite. It is **not compatible** with earlier versions and introduces breaking changes in:

* Entity unique IDs
* Sensor availability and types
* Data update logic (now using `DataUpdateCoordinator`)
* UI configuration only (no YAML)

Please remove and re-add the integration if you’re updating from a previous version.

---

## Lovelace

Add a Lovelace card to the UI:

Example 1

![sensors](https://github.com/jellespijker/home-assistant-ultimaker/raw/main/resources/lovelace.png)

```yaml
type: grid
cards:
  - type: heading
    heading: UltiMaker
    heading_style: title
  - show_state: true
    show_name: false
    camera_view: auto
    fit_mode: cover
    type: picture-entity
    entity: sensor.ums5_print_job_progress
    camera_image: camera.ums5_camera
    tap_action:
      action: more-info
  - show_name: true
    show_icon: false
    show_state: true
    type: glance
    entities:
      - entity: sensor.ums5_time_remaining
      - entity: sensor.ums5_eta
    state_color: false
  - type: tile
    entity: sensor.ums5_printer_activity
    features_position: bottom
    vertical: false
    name: Estado
    grid_options:
      columns: 6
      rows: 1
  - type: tile
    entity: switch.sonoff_10003b7db7
    features_position: bottom
    vertical: true
    icon_tap_action:
      action: more-info
  - type: tile
    entity: sensor.ums5_print_job_name
    features_position: bottom
    vertical: false
    grid_options:
      columns: 6
      rows: 1
    name: Archivo
  - type: entities
    entities:
      - entity: sensor.ums5_bed_temperature
      - entity: sensor.ums5_bed_temperature_target
      - entity: sensor.ums5_fan_speed
      - entity: sensor.ums5_print_job_state
    grid_options:
      columns: 6
      rows: auto
  - type: entities
    entities:
      - entity: sensor.ums5_hotend_1_temperature
      - entity: sensor.ums5_hotend_1_id
      - entity: sensor.ums5_hotend_2_temperature
      - entity: sensor.ums5_hotend_2_id
    grid_options:
      columns: 6
      rows: auto
```

Example 2

```yaml
type: grid
cards:
  - type: heading
    icon: ""
    heading_style: title
    heading: UltiMaker
  - show_state: false
    show_name: false
    camera_view: auto
    fit_mode: cover
    type: picture-entity
    entity: sensor.ums5_print_job_progress
    camera_image: camera.ums5_camera
    tap_action:
      action: more-info
  - type: markdown
    content: >
      **Hora finalización:**   {{ as_timestamp(states('sensor.ums5_eta')) |
      timestamp_custom('%H:%M', true) }}

      **Tiempo transcurrido:**   {{ states('sensor.ums5_time_elapsed') }} h

      **Tiempo restante:**   {{ states('sensor.ums5_time_remaining') }} h

      **Archivo actual:**   {{ states('sensor.ums5_print_job_name') }}

      **Estado de la impresora:**   {{ states('sensor.ums5_printer_activity') }}
      // {{ states('sensor.ums5_print_job_progress') }} %

      **Hotend 1:**   {{ states('sensor.ums5_hotend_1_temperature') }} °C // {{
      states('sensor.ums5_hotend_1_temperature_target') }} °C // {{
      states('sensor.ums5_hotend_1_id') }}

      **Hotend 2:**   {{ states('sensor.ums5_hotend_2_temperature') }} °C // {{
      states('sensor.ums5_hotend_2_temperature_target') }} °C // {{
      states('sensor.ums5_hotend_2_id') }}

      **Cama caliente:**   {{ states('sensor.ums5_bed_temperature') }} °C
      (objetivo: {{ states('sensor.ums5_bed_temperature_target') }} °C)  

      **Firmware:**   {{ states('sensor.ums5_firmware_version') }} → Última: {{
      states('sensor.ums5_latest_firmware_version') }}
```


## Credits

This integration was inspired by the original work of [jellespijker](https://github.com/jellespijker) and later expanded by [alnavasa](https://github.com/alnavasa).



## License

MIT License. Not affiliated with Ultimaker BV.
