# Printers are identified by GUID, and a merged printer is owned by its LAN connection

A printer can be reached by a LAN connection, a cloud connection, or both, and we want one Home Assistant device either way. We identify every printer by its GUID (`system.guid` on the local API, `host_guid` in Digital Factory: the same EEPROM value, which survives a factory reset). Existing LAN devices, previously keyed on the config entry ID, are migrated the first time the printer answers after the upgrade.

Home Assistant lets a device belong to one config entry only (since 2026 it splits devices shared between entries). So a merged printer's device is owned by its LAN config entry, and that entry also carries the printer's Digital Factory entities, reading them from the cloud connection's coordinator. The cloud connection provides devices only for cloud-only printers. On a merged printer the LAN connection owns live telemetry (status, progress, temperatures, camera stream) and Digital Factory adds only what LAN lacks. All control actions go through the cloud connection; a LAN-only printer is read-only.

## Considered Options

- **A LAN entry and a cloud entry attaching to the same device**: the original plan; rejected because current Home Assistant no longer allows it.
- **The cloud entry polling the printer's LAN address itself**: rejected because it would move existing LAN entities to another config entry and make the cloud entry hold per-printer LAN settings.
- **Separate devices for LAN and cloud**: rejected because users would see the same printer twice.
- **One config entry per printer holding both connections**: rejected because a cloud connection is per workspace, and one credential would be duplicated across entries.
- **Matching on IP address or hostname**: rejected because both change; Cura uses them only as fallbacks behind the GUID.

## Consequences

- Entities move between the two entries, keeping their entity IDs, when a printer gains or loses its LAN connection. Either entry can finish setting up first, so the handover is a sync step run at the end of both setups rather than at platform setup.
- Digital Factory entities that overlap LAN telemetry exist only on cloud-only printers.
- While a merged printer's LAN connection cannot be set up (printer unreachable at startup), its Digital Factory entities are unavailable too.
- The cloud's `cluster_id` and printer `uuid` change on reset or re-registration and must never be used as identity.
