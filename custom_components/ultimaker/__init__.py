from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from .const import DOMAIN, COORDINATOR
from .coordinator import UltimakerDataUpdateCoordinator
from datetime import timedelta

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ultimaker from a config entry."""
    ip = entry.data["ip"]
    scan_interval = timedelta(seconds=entry.data.get("scan_interval", 10))
    coordinator = UltimakerDataUpdateCoordinator(hass, ip, scan_interval)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        COORDINATOR: coordinator,
        "ip": ip,
    }

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "camera", "update"])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Ultimaker config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, ["sensor", "camera", "update"])
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded