from homeassistant.components.update import UpdateEntity, UpdateDeviceClass, UpdateEntityFeature
from .identity import entity_unique_id, printer_device_info
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import logging
from .const import DOMAIN, COORDINATOR

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    """Set up Ultimaker firmware update entity."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]
    name = config_entry.data.get("name", "Ultimaker")
    async_add_entities([UltimakerFirmwareUpdate(coordinator, config_entry, name)])


class UltimakerFirmwareUpdate(UpdateEntity):
    def __init__(self, coordinator, config_entry, name):
        self._coordinator = coordinator
        self._config_entry = config_entry
        self._attr_name = f"{name} Firmware"
        self._attr_unique_id = entity_unique_id(config_entry, coordinator.data, "firmware", "update")
        self._attr_has_entity_name = True
        self._attr_device_info = printer_device_info(config_entry, coordinator.data)

        self._attr_device_class = UpdateDeviceClass.FIRMWARE
        self._attr_supported_features = UpdateEntityFeature(0)

        
    @property
    def installed_version(self):
        return self._coordinator.data.get("system", {}).get("firmware")

    @property
    def latest_version(self):
        return self._coordinator.data.get("latest_firmware")

    @property
    def release_summary(self):
        return ""

    @property
    def update_available(self):
        current = self.installed_version
        latest = self.latest_version
        return bool(latest and current and current != latest)