"""Binary sensors; all of them report Digital Factory data."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .cloud_entity import cloud_binary_sensors
from .const import CONF_CONNECTION, CONNECTION_CLOUD


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities) -> None:
    # A LAN connection has none of its own; merge.py adds a merged printer's later.
    if config_entry.data.get(CONF_CONNECTION) == CONNECTION_CLOUD:
        async_add_entities(cloud_binary_sensors(hass, config_entry))
