
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfInformation,
    UnitOfLength,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from datetime import datetime, timedelta, timezone
import logging
from .coordinator import UltimakerDataUpdateCoordinator


_LOGGER = logging.getLogger(__name__)
DOMAIN = "ultimaker"

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
        "transform": str
    },

    "firmware_latest": {
        "name": "Latest firmware version",
        "path": ["latest_firmware"],
        "icon": "mdi:cloud-download",
        "entity_category": EntityCategory.DIAGNOSTIC,
        "transform": str
    },

    "firmware_update_available": {
        "name": "Firmware update available",
        "icon": "mdi:update",
        "entity_category": EntityCategory.DIAGNOSTIC,
        "transform_from_data": lambda d: (
            d.get("system", {}).get("firmware") != d.get("latest_firmware")
        ),
        "transform": str,
        "entity_category": EntityCategory.DIAGNOSTIC,
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
        "unit": UnitOfLength.METERS,
        "icon": "mdi:printer-3d-nozzle",
        "path": ["printer", "heads", 0, "extruders", 0, "hotend", "statistics", "material_extruded"],
        "state_class": "total_increasing",
        "entity_category": EntityCategory.DIAGNOSTIC,
        "transform": lambda x: round(x / 1000, 3)  
    },
    "max_temperature_exposed": {
        "name": "Hotend max temperature",
        "unit": UnitOfTemperature.CELSIUS,
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
        "unit": UnitOfLength.MILLIMETERS,
        "icon": "mdi:counter",
        "path": ["printer", "heads", 0, "extruders", 0, "active_material", "length_remaining"],
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },
    "led_brightness": {
        "name": "LED brightness",
        "unit": PERCENTAGE,
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
        "unit": PERCENTAGE,
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
        "unit": UnitOfTemperature.CELSIUS,
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
        "unit": UnitOfTime.SECONDS,
        "device_class": "duration",
        "state_class": "measurement",
        "icon": "mdi:clock-start",
        "path": ["print_job", "time_elapsed"],
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },

    "time_remaining_raw": {
        "name": "Time remaining (raw)",
        "unit": UnitOfTime.SECONDS,
        "device_class": "duration",
        "state_class": "measurement",
        "icon": "mdi:clock-end",
        "transform_from_data": lambda d: (
            d.get("print_job", {}).get("time_total", 0) - d.get("print_job", {}).get("time_elapsed", 0)
        ),
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },
    "eta": {
        "name": "ETA",
        "device_class": "timestamp",
        "icon": "mdi:calendar-clock",
        "transform_from_data": lambda d: (
            (datetime.now(timezone.utc) +
            timedelta(seconds=(d["print_job"].get("time_total", 0) - d["print_job"].get("time_elapsed", 0)))
            ).replace(second=0, microsecond=0)
            if "print_job" in d and d["print_job"].get("time_total") and d["print_job"].get("time_elapsed") else None
        ),
        "entity_registry_enabled_default": False,
    },

    "ip_address": {
        "name": "IP address",
        "icon": "mdi:ip-network",
        "value_fn": lambda coordinator, config_entry: config_entry.data.get("ip"),
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    },

    "mac_address": {
        "name": "MAC address",
        "icon": "mdi:lan",
        "value_fn": lambda coordinator, config_entry: coordinator.data.get("mac"),
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "entity_registry_visible_default": False
    }

}


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up Ultimaker sensors from a config entry."""

    ip = config_entry.data["ip"]
    scan_interval = timedelta(seconds=config_entry.data.get("scan_interval", 10))
    coordinator = UltimakerDataUpdateCoordinator(hass, ip, scan_interval)
    await coordinator.async_config_entry_first_refresh()

    entities = []
    for key, desc in SENSOR_TYPES.items():
        entities.append(UltimakerSensor(coordinator, config_entry, key, desc))

    async_add_entities(entities)


class UltimakerSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, config_entry, key, description):
        super().__init__(coordinator)
        self._key = key
        self._desc = description
        self._value_fn = description.get("value_fn")
        user_prefix = coordinator.config_entry.data.get("name", "Ultimaker")
        sys_data = coordinator.data.get("system", {})
        ip = coordinator.config_entry.data.get("ip")
        mac = self.coordinator.data.get("mac")
        self._attr_name = f"{user_prefix} {description['name']}"
        self._attr_unique_id = f"{user_prefix.lower().replace(' ', '_')}_{key}"
        self._attr_native_unit_of_measurement = description.get("unit")
        self._attr_device_class = description.get("device_class")
        self._attr_state_class = description.get("state_class")
        self._attr_icon = description.get("icon")
        self._attr_entity_category = description.get("entity_category")
        self._attr_entity_registry_enabled_default = description.get("entity_registry_enabled_default", True)
        self._attr_entity_registry_visible_default = description.get("entity_registry_visible_default", True)


        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            connections={(CONNECTION_NETWORK_MAC, mac)} if mac else set(),
            name=config_entry.data.get("name", "Ultimaker"),
            manufacturer="Ultimaker",
            model=sys_data.get("variant", "Unknown"),
            sw_version=sys_data.get("firmware", "Unknown"),
            hw_version=str(sys_data.get("hardware", {}).get("revision", "Unknown")),
            serial_number=sys_data.get("guid", None),
        )

    @property
    def native_value(self):
        # Si hay una función personalizada de valor, úsala
        if "value_fn" in self._desc:
            return self._desc["value_fn"](self.coordinator, self.coordinator.config_entry)

        # Lógica original para sensores basados en path
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