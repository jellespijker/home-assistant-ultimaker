import logging
from homeassistant.components.update import UpdateEntity, UpdateDeviceClass
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.update import UpdateEntityFeature

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
        self._attr_unique_id = f"{config_entry.entry_id}_firmware"
        self._attr_has_entity_name = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=name,
            manufacturer="Ultimaker",
        )
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