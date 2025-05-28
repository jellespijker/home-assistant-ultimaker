import logging

from datetime import timedelta
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    UnitOfTemperature,
    UnitOfTime,
    UnitOfInformation,
    UnitOfLength,
    PERCENTAGE,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.helpers.device_registry import DeviceInfo
import aiohttp

from homeassistant.helpers.entity import EntityCategory
from datetime import datetime, timezone

from .coordinator import UltimakerDataUpdateCoordinator

import subprocess
import re
import datetime

def get_mac_from_ip(ip):
    """Retrieve MAC address for a given IP using ARP table."""
    try:
        subprocess.run(["ping", "-c", "1", ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        result = subprocess.run(["arp", "-n", ip], capture_output=True, text=True)
        match = re.search(r"(([a-fA-F0-9]{2}[:-]){5}[a-fA-F0-9]{2})", result.stdout)
        return match.group(0).lower() if match else None
    except Exception as e:
        _LOGGER.warning(f"Error getting MAC address for {ip}: {e}")
        return None







_LOGGER = logging.getLogger(__name__)
DOMAIN = "ultimaker"
SCAN_INTERVAL = timedelta(seconds=10)

SENSOR_TYPES = {
    "bed_temperature": {
        "name": "Bed temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": "temperature",
        "state_class": "measurement",
        "icon": "mdi:radiator",
        "path": ["printer", "bed", "temperature", "current"],
    },
    "bed_temperature_target": {
        "name": "Bed temperature target",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": "temperature",
        "state_class": "measurement",
        "icon": "mdi:radiator-disabled",
        "path": ["printer", "bed", "temperature", "target"],
    },
    "bed_type": {
        "name": "Bed type",
        "unit": None,
        "icon": "mdi:printer-3d",
        "path": ["printer", "bed", "type"],
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },
    "hotend_1_temperature": {
        "name": "Hotend 1 temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": "temperature",
        "state_class": "measurement",
        "icon": "mdi:printer-3d-nozzle-heat",
        "path": ["printer", "heads", 0, "extruders", 0, "hotend", "temperature", "current"],
    },
    "hotend_1_temperature_target": {
        "name": "Hotend 1 temperature target",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": "temperature",
        "state_class": "measurement",
        "icon": "mdi:printer-3d-nozzle",
        "path": ["printer", "heads", 0, "extruders", 0, "hotend", "temperature", "target"],
    },
    "hotend_1_id": {
        "name": "Hotend 1 ID",
        "icon": "mdi:printer-3d-nozzle",
        "path": ["printer", "heads", 0, "extruders", 0, "hotend", "id"],
    },
    "hotend_2_temperature": {
        "name": "Hotend 2 temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": "temperature",
        "state_class": "measurement",
        "icon": "mdi:printer-3d-nozzle-heat",
        "path": ["printer", "heads", 0, "extruders", 1, "hotend", "temperature", "current"],
    },
    "hotend_2_temperature_target": {
        "name": "Hotend 2 temperature target",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": "temperature",
        "state_class": "measurement",
        "icon": "mdi:printer-3d-nozzle",
        "path": ["printer", "heads", 0, "extruders", 1, "hotend", "temperature", "target"],
    },
    "hotend_2_id": {
        "name": "Hotend 2 ID",
        "icon": "mdi:printer-3d-nozzle",
        "path": ["printer", "heads", 0, "extruders", 1, "hotend", "id"],
    },
    "print_job_progress": {
        "name": "Print job progress",
        "unit": PERCENTAGE,
        "device_class": None,
        "state_class": "measurement",
        "icon": "mdi:percent",
        "path": ["print_job", "progress"],
        "transform": lambda v: round(v * 100, 1),
    },
    "print_job_state": {
        "name": "Print job state",
        "icon": "mdi:file",
        "path": ["print_job", "state"],
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },
    "printer_status": {
        "name": "Printer status",
        "icon": "mdi:printer-3d",
        "path": ["printer", "status"],
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },
    "time_elapsed": {
        "name": "Time elapsed",
        "unit": UnitOfTime.HOURS,
        "device_class": "duration",
        "state_class": "measurement",
        "icon": "mdi:clock-start",
        "path": ["print_job", "time_elapsed"],
        "transform": lambda v: round(v / 3600, 2),
    },
    "time_total": {
        "name": "Time total",
        "unit": UnitOfTime.HOURS,
        "device_class": "duration",
        "state_class": "measurement",
        "icon": "mdi:clock-outline",
        "path": ["print_job", "time_total"],
        "transform": lambda v: round(v / 3600, 2),
    },
    "time_remaining": {
        "name": "Time remaining",
        "unit": UnitOfTime.HOURS,
        "device_class": "duration",
        "state_class": "measurement",
        "icon": "mdi:clock-end",
        "transform_from_data": lambda d: round((d.get("print_job", {}).get("time_total", 0) - d.get("print_job", {}).get("time_elapsed", 0)) / 3600, 2),
    },

    "firmware_version": {
        "name": "Firmware version",
        "path": ["system", "firmware"],
        "icon": "mdi:chip",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },

    "firmware_latest": {
        "name": "Latest firmware version",
        "path": ["latest_firmware"],
        "icon": "mdi:cloud-download",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },

    "firmware_update_available": {
        "name": "Firmware update available",
        "icon": "mdi:update",
        "entity_category": EntityCategory.DIAGNOSTIC,
        "transform_from_data": lambda d: (
            d.get("system", {}).get("firmware") != d.get("latest_firmware")
        ),
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },

    "uptime": {
        "name": "Uptime",
        "path": ["system", "uptime"],
        "unit": UnitOfTime.HOURS,
        "device_class": "duration",
        "state_class": "measurement",
        "transform": lambda v: round(v / 3600, 1),
        "icon": "mdi:clock-start",
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },
    "memory_used": {
        "name": "Memory used",
        "unit": UnitOfInformation.MEGABYTES,
        "device_class": "data_size",
        "state_class": "measurement",
        "icon": "mdi:memory",
        "path": ["system", "memory", "used"],
        "transform": lambda v: round(v / 1024 / 1024, 1),
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "memory_total": {
        "name": "Memory total",
        "unit": UnitOfInformation.MEGABYTES,
        "device_class": "data_size",
        "state_class": "measurement",
        "icon": "mdi:memory",
        "path": ["system", "memory", "total"],
        "icon": "mdi:memory",
        "transform": lambda v: round(v / 1024 / 1024, 1),
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },
    "hardware_revision": {
        "name": "Hardware revision",
        "path": ["system", "hardware", "revision"],
        "icon": "mdi:memory",
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },
    "model": {
        "name": "Model",
        "path": ["system", "variant"],
        "icon": "mdi:printer-3d",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "fan_speed": {
        "name": "Fan speed",
        "path": ["printer", "heads", 0, "fan"],
        "unit": PERCENTAGE,
        "state_class": "measurement",
        "icon": "mdi:fan",
    },
    "hotend_1_time_spent_hot": {
        "name": "Hotend 1 Time Hot",
        "path": ["printer", "heads", 0, "extruders", 0, "hotend", "statistics", "time_spent_hot"],
        "unit": UnitOfTime.HOURS,
        "device_class": "duration",
        "transform": lambda v: round(v / 3600, 2),
        "icon": "mdi:fire",
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },
    "hotend_1_prints_since_cleaned": {
        "name": "Hotend 1 Prints Since Cleaned",
        "path": ["printer", "heads", 0, "extruders", 0, "hotend", "statistics", "prints_since_cleaned"],
        "icon": "mdi:printer-3d",
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },
    "hotend_2_time_spent_hot": {
        "name": "Hotend 2 Time Hot",
        "path": ["printer", "heads", 0, "extruders", 1, "hotend", "statistics", "time_spent_hot"],
        "unit": UnitOfTime.HOURS,
        "device_class": "duration",
        "transform": lambda v: round(v / 3600, 2),
        "icon": "mdi:fire",
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },
    "hotend_2_prints_since_cleaned": {
        "name": "Hotend 2 Prints Since Cleaned",
        "path": ["printer", "heads", 0, "extruders", 1, "hotend", "statistics", "prints_since_cleaned"],
        "icon": "mdi:printer-3d",
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },
    "print_job_name": {
        "name": "Print job name",
        "path": ["print_job", "name"],
        "icon": "mdi:file-document",
    },
    "print_job_source": {
        "name": "Print job source",
        "path": ["print_job", "source"],
        "icon": "mdi:web",
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },
    "print_job_source_app": {
        "name": "Source application",
        "path": ["print_job", "source_application"],
        "icon": "mdi:application",
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },


    "material_extruded": {
        "name": "Material extruded",
        "unit": "m",
        "icon": "mdi:printer-3d-nozzle",
        "path": ["printer", "heads", 0, "extruders", 0, "hotend", "statistics", "material_extruded"],
        "state_class": "total_increasing",
        "entity_category": EntityCategory.DIAGNOSTIC,
        "transform": lambda x: round(x / 1000, 3)  
    },
    "max_temperature_exposed": {
        "name": "Hotend max temperature",
        "unit": "°C",
        "device_class": "temperature",
        "state_class": "measurement",
        "icon": "mdi:thermometer-high",
        "path": ["printer", "heads", 0, "extruders", 0, "hotend", "statistics", "max_temperature_exposed"],
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },
    "filament_remaining": {
        "name": "Filament remaining",
        "unit": "mm",
        "icon": "mdi:counter",
        "path": ["printer", "heads", 0, "extruders", 0, "active_material", "length_remaining"],
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },
    "led_brightness": {
        "name": "LED brightness",
        "unit": "%",
        "icon": "mdi:led-on",
        "path": ["printer", "led", "brightness"],
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },
    "led_hue": {
        "name": "LED hue",
        "unit": "°",
        "icon": "mdi:palette",
        "path": ["printer", "led", "hue"],
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },
    "led_saturation": {
        "name": "LED saturation",
        "unit": "%",
        "icon": "mdi:palette",
        "path": ["printer", "led", "saturation"],
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },
    "hostname": {
        "name": "Hostname",
        "icon": "mdi:server",
        "path": ["system", "hostname"],
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },
    "platform": {
        "name": "Platform",
        "icon": "mdi:chip",
        "path": ["system", "platform"],
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },
    "system_guid": {
        "name": "System GUID",
        "icon": "mdi:identifier",
        "path": ["system", "guid"],
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },
    "country": {
        "name": "Country",
        "icon": "mdi:earth",
        "path": ["system", "country"],
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },
    "language": {
        "name": "Language",
        "icon": "mdi:translate",
        "path": ["system", "language"],
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },
    "system_time": {
        "name": "System Time",
        "device_class": "timestamp",
        "icon": "mdi:clock",
        "transform": lambda v: datetime.fromtimestamp(v["utc"], tz=timezone.utc),
        "path": ["system", "time"],
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },
    "hotend_offset_state": {
        "name": "Hotend offset state",
        "icon": "mdi:cursor-pointer",
        "path": ["printer", "heads", 0, "extruders", 0, "hotend", "offset", "state"],
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "ethernet_connected": {
        "name": "Ethernet Connected",
        "icon": "mdi:lan-connect",
        "path": ["printer", "network", "ethernet", "connected"],
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "wifi_connected": {
        "name": "WiFi Connected",
        "icon": "mdi:wifi",
        "path": ["printer", "network", "wifi", "connected"],
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "wifi_mode": {
        "name": "WiFi Mode",
        "icon": "mdi:wifi-settings",
        "path": ["printer", "network", "wifi", "mode"],
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },
    "wifi_ssid": {
        "name": "WiFi SSID",
        "icon": "mdi:wifi",
        "path": ["printer", "network", "wifi", "ssid"],
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },

    "camera_stream_url": {
        "name": "Camera Stream URL",
        "path": ["camera_stream_url"],
        "icon": "mdi:video-wireless",
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },

    "camera_snapshot_url": {
        "name": "Camera Snapshot URL",
        "path": ["camera_snapshot_url"],
        "icon": "mdi:camera",
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
},


    "ambient_temperature": {
        "name": "Ambient Temperature",
        "unit": "°C",
        "device_class": "temperature",
        "state_class": "measurement",
        "icon": "mdi:thermometer",
        "path": ["ambient_temperature", "current"],
        "transform": lambda v: round(v / 10, 1),  
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },

    "printer_activity": {
        "name": "Printer activity",
        "icon": "mdi:printer-3d",
        "transform_from_data": lambda d: (
            d.get("print_job", {}).get("state")
            if d.get("print_job", {}).get("state") not in [None, "unknown"]
            else d.get("printer", {}).get("status", "unknown")
        ),
    },
    "time_elapsed_raw": {
        "name": "Time elapsed (raw)",
        "unit": "s",
        "device_class": "duration",
        "state_class": "measurement",
        "icon": "mdi:clock-start",
        "path": ["print_job", "time_elapsed"],
    },

    "time_remaining_raw": {
        "name": "Time remaining (raw)",
        "unit": "s",
        "device_class": "duration",
        "state_class": "measurement",
        "icon": "mdi:clock-end",
        "transform_from_data": lambda d: (
            d.get("print_job", {}).get("time_total", 0) - d.get("print_job", {}).get("time_elapsed", 0)
        ),
    },
    "eta": {
        "name": "ETA",
        "device_class": "timestamp",
        "icon": "mdi:calendar-clock",
        "transform_from_data": lambda d: (
            (datetime.datetime.now(datetime.timezone.utc) +
            datetime.timedelta(seconds=(d["print_job"].get("time_total", 0) - d["print_job"].get("time_elapsed", 0)))
            ).replace(second=0, microsecond=0)
            if "print_job" in d and d["print_job"].get("time_total") and d["print_job"].get("time_elapsed") else None
        ),
        "entity_registry_enabled_default": False,

    }
}



async def async_setup_entry(hass, config_entry, async_add_entities):
    ip = config_entry.data["host"]
    coordinator = UltimakerDataUpdateCoordinator(hass, ip)
    await coordinator.async_config_entry_first_refresh()

    entities = []
    for key, desc in SENSOR_TYPES.items():
        entities.append(UltimakerSensor(coordinator, config_entry.entry_id, key, desc))

    async_add_entities(entities)


class UltimakerSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry_id, key, description):
        super().__init__(coordinator)
        self._key = key
        self._desc = description
        user_prefix = coordinator.config_entry.data.get("name", "Ultimaker")
        self._attr_name = f"{user_prefix} {description['name']}"
        self._attr_unique_id = f"{user_prefix.lower().replace(' ', '_')}_{key}"
        self._attr_native_unit_of_measurement = description.get("unit")
        self._attr_device_class = description.get("device_class")
        self._attr_state_class = description.get("state_class")
        self._attr_icon = description.get("icon")
        self._attr_entity_category = description.get("entity_category")
        self._attr_entity_registry_enabled_default = description.get("entity_registry_enabled_default", True)
        self._attr_entity_registry_visible_default = description.get("entity_registry_visible_default", True)
        sys_data = coordinator.data.get("system", {})
        ip = coordinator.config_entry.data.get("host")
        mac_address = get_mac_from_ip(ip)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            connections={("mac", mac_address)} if mac_address else set(),
            name=user_prefix,
            manufacturer="Ultimaker",
            model=sys_data.get("variant", "Unknown"),
            sw_version=sys_data.get("firmware", "Unknown"),
            hw_version=str(sys_data.get("hardware", {}).get("revision", "Unknown")),
            serial_number=sys_data.get("guid", None),
        )

    @property
    def native_value(self):
        data = self.coordinator.data
        try:
            if "transform_from_data" in self._desc:
                return self._desc["transform_from_data"](data)
            for key in self._desc["path"]:
                data = data[key]
            if "transform" in self._desc:
                return self._desc["transform"](data)
            return data
        except (KeyError, TypeError):
            return None