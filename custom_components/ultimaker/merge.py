"""Merged printers: one device for a printer reached over LAN and through Digital Factory.

Home Assistant lets a device belong to one config entry only, so the LAN
connection owns a merged printer and also carries its Digital Factory
entities, reading them from the cloud connection's coordinator.
See docs/adr/0001-printer-identity-and-merged-printers.md.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_platform, entity_registry as er

from .cloud_entity import cloud_coordinator_for, merged_cloud_entities
from .const import CONF_CONNECTION, CONNECTION_CLOUD, COORDINATOR, DOMAIN
from .identity import printer_device_info

_ATTACHED = "cloud_coordinator"
_ENTITIES = "cloud_entities"


def is_cloud(entry: ConfigEntry) -> bool:
    return entry.data.get(CONF_CONNECTION) == CONNECTION_CLOUD


async def async_sync_cloud_entities(hass: HomeAssistant, lan_entry: ConfigEntry) -> None:
    """Make a LAN connection carry exactly the Digital Factory entities it should.

    Called whenever either side finishes setting up, in any order: it attaches
    to the cloud connection that imports this printer, re-attaches after that
    connection reloaded, and detaches when the printer is no longer imported.
    """
    store = hass.data.get(DOMAIN, {}).get(lan_entry.entry_id)
    guid = lan_entry.unique_id
    if store is None or not guid:
        return

    coordinator = cloud_coordinator_for(hass, guid)
    if coordinator is not None and guid in coordinator.owned:
        # The cloud connection still provides this printer itself. Its reload
        # leaves the printer to this entry and then calls back here.
        hass.config_entries.async_schedule_reload(coordinator.config_entry.entry_id)
        return
    if store.get(_ATTACHED) is coordinator:
        return

    platforms = {
        platform.domain: platform
        for platform in entity_platform.async_get_platforms(hass, DOMAIN)
        if platform.config_entry is lan_entry
    }
    if "sensor" not in platforms or "binary_sensor" not in platforms:
        return  # still setting up; the end of this entry's setup calls again

    store[_ATTACHED] = coordinator
    for entity in store.pop(_ENTITIES, []):
        await entity.async_remove()

    ent_reg = er.async_get(hass)
    if coordinator is None:
        for entity in er.async_entries_for_config_entry(ent_reg, lan_entry.entry_id):
            if "_cloud_" in entity.unique_id:
                ent_reg.async_remove(entity.entity_id)
        return

    device_info = printer_device_info(lan_entry, store[COORDINATOR].data)
    sensors, binary_sensors = merged_cloud_entities(coordinator, guid, device_info)
    store[_ENTITIES] = [*sensors, *binary_sensors]
    await platforms["sensor"].async_add_entities(sensors)
    await platforms["binary_sensor"].async_add_entities(binary_sensors)

    # What is left under the cloud connection duplicates live LAN telemetry.
    for entity in er.async_entries_for_config_entry(ent_reg, coordinator.config_entry.entry_id):
        if entity.unique_id.startswith(f"{guid}_cloud_"):
            ent_reg.async_remove(entity.entity_id)
    async_remove_empty_devices(hass)


async def async_sync_all_lan_entries(hass: HomeAssistant) -> None:
    """Sync every LAN connection after a cloud connection changed."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if not is_cloud(entry):
            await async_sync_cloud_entities(hass, entry)


@callback
def async_remove_empty_devices(hass: HomeAssistant) -> None:
    """Remove devices an entry no longer has entities on, such as a merged printer's old cloud device."""
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is not ConfigEntryState.LOADED and entry.entry_id not in hass.data.get(DOMAIN, {}):
            continue
        for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
            entities = er.async_entries_for_device(ent_reg, device.id, include_disabled_entities=True)
            if any(entity.config_entry_id == entry.entry_id for entity in entities):
                continue
            if entities or not hasattr(dev_reg, "async_get_device_by_identifier"):
                # Home Assistant before devices became owned by a single config
                # entry: the device is shared, so only detach this entry from it.
                dev_reg.async_update_device(device.id, remove_config_entry_id=entry.entry_id)
            else:
                dev_reg.async_remove_device(device.id)
