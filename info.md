[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
# Home Assistant Ultimaker printers

Personal version with new sensors

![sensors](https://github.com/jellespijker/home-assistant-ultimaker/raw/main/resources/home-assistant-um.png)

Adds support for the following ultimaker printer sensors:

- Printer status
- Print job state
- Print job progress
- Hotend id (AA 0.4, BB 0.4, ...)
- Hotend temperature
- Hotend target temperature
- Bed type (glass, ...)
- Bed temperature
- Bed target temperature

{% if installed %}
## Changes as compared to your installed version:

### Features

{% if version_installed.replace("v", "").replace("V", "").replace(".","") | int < 14  %}
- Added `bed_type`
- Added `hotend_1_id`
- Added `hotend_2_id`
{% endif %}
{% if version_installed.replace("v", "").replace("V", "").replace(".","") | int < 15  %}
- Support from Python 3.8 and higher
- Support Home Assistant OS 5.4.99 and higher
{% endif %}

### Bugfixes

{% else %}

## Usage

Add the Ultimaker platform to your sensors in `configuration.yaml`

```yaml
sensor:
  - platform: ultimaker
    name: name
    host: ip_adress
    scan_interval: 10  # optional, default 10
    decimal: 2  # optional, default 2 rounds the sensor values
    sensors:
      - status  # optional
      - state  # optional
      - progress  # optional
      - time_elapsed # optional
      - time_estimated # optional
      - time_total # optional
      - bed_type  # optional
      - bed_temperature  # optional
      - bed_temperature_target  # optional
      - hotend_1_id  # optional
      - hotend_1_temperature  # optional
      - hotend_1_temperature_target  # optional
      - hotend_1_statistics_material_extruded # optional
      - hotend_1_statistics_prints_since_cleaned # optional
      - hotend_1_statistics_max_temperature_exposed # optional
      - hotend_1_statistics_time_spent_hot # optional
      - hotend_1_serial # optional
      - hotend_2_id  # optional
      - hotend_2_temperature  # optional
      - hotend_2_temperature_target  # optional
      - hotend_2_statistics_material_extruded # optional
      - hotend_2_statistics_prints_since_cleaned # optional
      - hotend_1_statistics_max_temperature_exposed # optional
      - hotend_1_statistics_time_spent_hot # optional
      - hotend_2_serial # optional
```

### Camera
Define a generic camera in the `configuration.yaml`

```yaml
camera:
  - platform: generic
    still_image_url: http://ip_adress:8080/?action=snapshot
    framerate: 4
```

### Lovelace card

Add a lovelace card to the UI, replace `printername` with the name you specified in your `configuration.yaml`

```typescript
type: vertical-stack
cards:
  - type: entity
    entity: sensor.printername_print_job_state
  - type: conditional
    conditions:
      - entity: sensor.printername_printer_status
        state: printing
    card:
      type: picture-entity
      entity: sensor.printername_print_job_progress
      camera_image: camera.generic_camera
      camera_view: live
  - type: gauge
    entity: sensor.printername_print_job_progress
    min: 0
    max: 100
    severity:
      green: 66
      yellow: 33
      red: 0
```

{% endif %}
