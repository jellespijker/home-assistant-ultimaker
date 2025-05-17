[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)
# Home Assistant Ultimaker Integration

![sensors](https://github.com/jellespijker/home-assistant-ultimaker/raw/main/resources/home-assistant-um.png)

## Features

This integration supports both local API and cloud API connections to Ultimaker printers:

### Local API
Connect directly to your Ultimaker printer on your local network.

### Cloud API (New!)
Connect to your Ultimaker printer(s) through the Ultimaker Connect cloud service using OpenID Connect (OIDC) authentication.

## Supported Sensors

### Local API Sensors
- Printer status
- Print job state
- Print job progress
- Hotend id (AA 0.4, BB 0.4, ...)
- Hotend temperature
- Hotend target temperature
- Bed type (glass, ...)
- Bed temperature
- Bed target temperature

### Cloud API Sensors
All Local API sensors plus:
- Cluster status
- Printer count
- Maintenance required
- Material remaining

## Installation

### Using HACS:
Just search for **ultimaker** in the HACS integration bar

### From source:
Copy the `ultimaker` directory in your own `custom_components` folder

## Setup

### UI Setup (Recommended)
1. In Home Assistant, go to **Settings** > **Devices & Services**
2. Click the **+ ADD INTEGRATION** button
3. Search for and select **Ultimaker**
4. Follow the setup wizard

For detailed setup instructions, including how to set up the cloud API connection with OIDC authentication, see the [Setup Guide](custom_components/ultimaker/SETUP.md).

### YAML Configuration (Legacy)

The integration still supports YAML configuration for the local API:

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
      - bed_type  # optional
      - bed_temperature  # optional
      - bed_temperature_target  # optional
      - hotend_1_id  # optional
      - hotend_1_temperature  # optional
      - hotend_1_temperature_target  # optional
      - hotend_2_id  # optional
      - hotend_2_temperature  # optional
      - hotend_2_temperature_target  # optional
```

## Camera Integration

Add a camera to the configuration.yaml:

```yaml
camera:
  - platform: generic
    still_image_url: http://ip_adress:8080/?action=snapshot
    framerate: 4
```

## Lovelace UI Example

```yaml
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
