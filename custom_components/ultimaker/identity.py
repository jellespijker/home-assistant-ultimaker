"""Printer identity: one printer is one device, identified by its GUID.

See docs/adr/0001-printer-identity-and-merged-printers.md.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _reported_guid(data: dict[str, Any]) -> str | None:
    return (data.get("system") or {}).get("guid") or None


def printer_guid(entry: ConfigEntry, data: dict[str, Any]) -> str | None:
    """Return the GUID this entry identifies its printer by.

    None when the printer reports no GUID, or when another LAN entry already
    claimed the same printer; such an entry keeps the pre-2.0 identity.
    """
    guid = _reported_guid(data)
    return guid if guid and entry.unique_id == guid else None


def _legacy_sensor_prefix(entry: ConfigEntry) -> str:
    return entry.data.get("name", "Ultimaker").lower().replace(" ", "_")


def entity_unique_id(entry: ConfigEntry, data: dict[str, Any], key: str, platform: str) -> str:
    """Return the unique ID for an entity of this printer."""
    guid = printer_guid(entry, data)
    if guid:
        return f"{guid}_{key}"
    if platform == "sensor":
        return f"{_legacy_sensor_prefix(entry)}_{key}"
    return f"{entry.entry_id}_{key}"


def printer_device_info(entry: ConfigEntry, data: dict[str, Any]) -> DeviceInfo:
    """Return the device info shared by every entity of this printer."""
    system = data.get("system") or {}
    mac = data.get("mac")
    return DeviceInfo(
        identifiers={(DOMAIN, printer_guid(entry, data) or entry.entry_id)},
        connections={(CONNECTION_NETWORK_MAC, mac)} if mac else set(),
        name=entry.data.get("name", "Ultimaker"),
        manufacturer="Ultimaker",
        model=system.get("variant", "Unknown"),
        sw_version=system.get("firmware", "Unknown"),
        hw_version=str((system.get("hardware") or {}).get("revision", "Unknown")),
        serial_number=_reported_guid(data),
    )


async def async_migrate_printer_identity(
    hass: HomeAssistant, entry: ConfigEntry, data: dict[str, Any]
) -> None:
    """Move a pre-2.0 device and its entities onto the GUID-based identity.

    Runs on every setup and only touches registry entries still on the old
    scheme, so a printer that was unreachable during the upgrade is migrated
    the first time it answers.
    """
    guid = _reported_guid(data)
    if not guid:
        return

    if entry.unique_id != guid:
        if any(
            other.unique_id == guid
            for other in hass.config_entries.async_entries(DOMAIN)
            if other.entry_id != entry.entry_id
        ):
            _LOGGER.warning(
                "Printer %s is already set up by another entry; '%s' keeps its old identity",
                guid,
                entry.title,
            )
            return
        hass.config_entries.async_update_entry(entry, unique_id=guid)

    dev_reg = dr.async_get(hass)
    old_identifier = (DOMAIN, entry.entry_id)
    if hasattr(dev_reg, "async_get_device_by_identifier"):
        old_device = dev_reg.async_get_device_by_identifier(old_identifier, entry.entry_id)
    else:  # Home Assistant before devices became owned by a single config entry
        old_device = dev_reg.async_get_device(identifiers={old_identifier})
    if old_device is not None:
        dev_reg.async_update_device(old_device.id, new_identifiers={(DOMAIN, guid)})

    sensor_prefix = f"{_legacy_sensor_prefix(entry)}_"
    entry_prefix = f"{entry.entry_id}_"

    @callback
    def _new_unique_id(entity: er.RegistryEntry) -> dict[str, str] | None:
        old = entity.unique_id
        if old.startswith(f"{guid}_"):
            return None
        if old.startswith(entry_prefix):
            return {"new_unique_id": f"{guid}_{old[len(entry_prefix):]}"}
        if entity.domain == "sensor" and old.startswith(sensor_prefix):
            return {"new_unique_id": f"{guid}_{old[len(sensor_prefix):]}"}
        return None

    await er.async_migrate_entries(hass, entry.entry_id, _new_unique_id)
