from datetime import timedelta

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .cloud_coordinator import CloudCoordinator
from .const import CONF_PRINTERS, COORDINATOR, DOMAIN
from .coordinator import UltimakerDataUpdateCoordinator
from .identity import async_migrate_printer_identity
from .merge import (
    async_remove_empty_devices,
    async_sync_all_lan_entries,
    async_sync_cloud_entities,
    is_cloud,
)

PLATFORMS = ["sensor", "binary_sensor", "camera", "update"]
CLOUD_PLATFORMS = ["sensor", "binary_sensor"]


def _platforms(entry: ConfigEntry) -> list[str]:
    return CLOUD_PLATFORMS if is_cloud(entry) else PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a LAN connection (one printer) or a cloud connection (one workspace)."""
    if is_cloud(entry):
        coordinator = CloudCoordinator(hass, entry)
        await coordinator.async_config_entry_first_refresh()
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {COORDINATOR: coordinator}
        entry.async_on_unload(entry.add_update_listener(_async_reload_on_options_change))
    else:
        ip = entry.data["ip"]
        scan_interval = timedelta(seconds=entry.data.get("scan_interval", 10))
        coordinator = UltimakerDataUpdateCoordinator(hass, ip, scan_interval)
        await coordinator.async_config_entry_first_refresh()
        await async_migrate_printer_identity(hass, entry, coordinator.data)
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {COORDINATOR: coordinator, "ip": ip}

    await hass.config_entries.async_forward_entry_setups(entry, _platforms(entry))

    if is_cloud(entry):
        _async_remove_unimported_entities(hass, entry)
        await async_sync_all_lan_entries(hass)
    else:
        await async_sync_cloud_entities(hass, entry)
    async_remove_empty_devices(hass)
    return True


async def _async_reload_on_options_change(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Re-import printers when the import list of a cloud connection changes."""
    await hass.config_entries.async_reload(entry.entry_id)


@callback
def _async_remove_unimported_entities(hass: HomeAssistant, cloud_entry: ConfigEntry) -> None:
    """Remove the entities of printers that were taken off the import list."""
    imported = set(cloud_entry.options.get(CONF_PRINTERS, ()))
    ent_reg = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(ent_reg, cloud_entry.entry_id):
        guid, separator, _ = entity.unique_id.partition("_cloud_")
        if separator and guid not in imported:
            ent_reg.async_remove(entity.entity_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Ultimaker config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, _platforms(entry))
    if unloaded:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)[COORDINATOR]
        if is_cloud(entry):
            # Merged printers' LAN connections still hold this coordinator.
            coordinator.async_close()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Hand merged printers over to the connection that remains."""
    if is_cloud(entry):
        await async_sync_all_lan_entries(hass)
        return
    if not entry.unique_id:
        return
    for other in hass.config_entries.async_entries(DOMAIN):
        if (
            is_cloud(other)
            and other.state is ConfigEntryState.LOADED
            and entry.unique_id in other.options.get(CONF_PRINTERS, ())
        ):
            hass.config_entries.async_schedule_reload(other.entry_id)
