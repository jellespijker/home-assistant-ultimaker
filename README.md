[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
# Home Assistant Ultimaker printers

![sensors](resources/home-assistant-um.png)

Adds support for the following ultimaker printer sensors:

- Printer status
- Print job state
- Print job progress
- Hotend temperature
- Hotend target temperature
- Bed temperature
- Bed target temperature

# Install

## Using HACS:

> Pull Request made to add it to the HACS default repositories

In the mean time you can add a custom repository by the integrations using `https://github.com/jellespijker/home-assistant-ultimaker`

## From source:

Copy the `ultimaker` directory in your own `custom_components` folder


# Usage

configuration.yaml

```yaml
sensor:
  - platform: ultimaker
    name: name
    host: ip_adress
    scan_interval: 10  # optional, default 10
    decimal: 2  # optional, default 2 rounds the sensor values
    sensors:
      - status  # optional
      - state # optional
      - progress # optional
      - print_job_name # optional
      - print_job_finished # optional
      - bed_temperature # optional
      - bed_temperature_target # optional
      - hotend_1_temperature # optional
      - hotend_1_temperature_target # optional
      - hotend_2_temperature # optional
      - hotend_2_temperature_target # optional
```

add a camera to the configuration.yaml

```yaml
camera:
  - platform: generic
    still_image_url: http://ip_adress:8080/?action=snapshot
    framerate: 4
```

add a lovelace card to the UI

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
