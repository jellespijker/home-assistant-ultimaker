from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, COORDINATOR
from .coordinator import UltimakerDataUpdateCoordinator
from .identity import async_migrate_printer_identity

PLATFORMS = ["sensor", "camera", "update"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ultimaker from a config entry."""
    ip = entry.data["ip"]
    scan_interval = timedelta(seconds=entry.data.get("scan_interval", 10))
    coordinator = UltimakerDataUpdateCoordinator(hass, ip, scan_interval)

    await coordinator.async_config_entry_first_refresh()

    await async_migrate_printer_identity(hass, entry, coordinator.data)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        COORDINATOR: coordinator,
        "ip": ip,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Ultimaker config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
