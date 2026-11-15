"""Printer identity: GUID-based devices and the migration from the pre-2.0 scheme."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ultimaker.const import DOMAIN

from .conftest import GUID, MAC, printer_data


def _device(hass: HomeAssistant, identifier: str, entry: MockConfigEntry):
    """Look up a device by identifier on old and new Home Assistant versions."""
    dev_reg = dr.async_get(hass)
    if hasattr(dev_reg, "async_get_device_by_identifier"):
        return dev_reg.async_get_device_by_identifier((DOMAIN, identifier), entry.entry_id)
    return dev_reg.async_get_device(identifiers={(DOMAIN, identifier)})


def _entry(hass: HomeAssistant, name: str = "My Printer", ip: str = "192.0.2.10") -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title=name, data={"name": name, "ip": ip, "scan_interval": 10})
    entry.add_to_hass(hass)
    return entry


def _register_legacy(hass: HomeAssistant, entry: MockConfigEntry, with_mac: bool = True) -> tuple[str, dict[str, str]]:
    """Create the device and entities a 1.x install left in the registries."""
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        connections={(dr.CONNECTION_NETWORK_MAC, MAC)} if with_mac else set(),
        name=entry.title,
    )
    ent_reg = er.async_get(hass)
    legacy = {
        "sensor": (f"{entry.title.lower().replace(' ', '_')}_printer_activity", "printer_activity"),
        "camera": (f"{entry.entry_id}_camera", "camera"),
        "update": (f"{entry.entry_id}_firmware", "firmware"),
    }
    entity_ids = {}
    for domain, (unique_id, key) in legacy.items():
        entity_ids[key] = ent_reg.async_get_or_create(
            domain, DOMAIN, unique_id, config_entry=entry, device_id=device.id,
            suggested_object_id=f"legacy_{key}",
        ).entity_id
    return device.id, entity_ids


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED


async def test_new_printer_is_identified_by_guid(hass: HomeAssistant, mock_poll) -> None:
    entry = _entry(hass)
    await _setup(hass, entry)

    device = _device(hass, GUID, entry)
    assert device is not None
    assert device.identifiers == {(DOMAIN, GUID)}
    assert entry.unique_id == GUID

    ent_reg = er.async_get(hass)
    for domain, key in (("sensor", "printer_activity"), ("camera", "camera"), ("update", "firmware")):
        entity_id = ent_reg.async_get_entity_id(domain, DOMAIN, f"{GUID}_{key}")
        assert entity_id is not None
        assert ent_reg.async_get(entity_id).device_id == device.id


async def test_printer_is_polled_once_per_setup(hass: HomeAssistant, mock_poll) -> None:
    await _setup(hass, _entry(hass))
    assert mock_poll.call_count == 1


async def test_legacy_device_and_entities_keep_their_ids(hass: HomeAssistant, mock_poll) -> None:
    entry = _entry(hass)
    device_id, entity_ids = _register_legacy(hass, entry)

    await _setup(hass, entry)

    dev_reg = dr.async_get(hass)
    device = _device(hass, GUID, entry)
    assert device.id == device_id
    assert device.identifiers == {(DOMAIN, GUID)}
    assert len(dr.async_entries_for_config_entry(dev_reg, entry.entry_id)) == 1

    ent_reg = er.async_get(hass)
    for key, entity_id in entity_ids.items():
        registered = ent_reg.async_get(entity_id)
        assert registered.unique_id == f"{GUID}_{key}"
        assert registered.device_id == device_id
    # Every entity created by setup reuses a migrated registry entry or is new; none is duplicated.
    unique_ids = [e.unique_id for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id)]
    assert len(unique_ids) == len(set(unique_ids))
    assert all(u.startswith(f"{GUID}_") for u in unique_ids)


async def test_migration_is_idempotent(hass: HomeAssistant, mock_poll) -> None:
    entry = _entry(hass)
    device_id, entity_ids = _register_legacy(hass, entry)
    await _setup(hass, entry)
    before = {e.entity_id: e.unique_id for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)}

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    after = {e.entity_id: e.unique_id for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)}
    assert after == before
    assert _device(hass, GUID, entry).id == device_id


async def test_printer_without_guid_keeps_legacy_identity(hass: HomeAssistant, mock_poll) -> None:
    mock_poll.return_value = printer_data(guid=None)
    entry = _entry(hass)
    device_id, entity_ids = _register_legacy(hass, entry)

    await _setup(hass, entry)

    device = _device(hass, entry.entry_id, entry)
    assert device.id == device_id
    assert entry.unique_id is None
    ent_reg = er.async_get(hass)
    assert ent_reg.async_get(entity_ids["printer_activity"]).unique_id == "my_printer_printer_activity"
    assert ent_reg.async_get(entity_ids["camera"]).unique_id == f"{entry.entry_id}_camera"
    assert ent_reg.async_get(entity_ids["firmware"]).unique_id == f"{entry.entry_id}_firmware"


async def test_second_entry_for_same_printer_keeps_its_old_identity(hass: HomeAssistant, mock_poll) -> None:
    """Two 1.x entries for one printer: the first claims the GUID, the second is left untouched."""
    mock_poll.return_value = {**printer_data(), "mac": None}
    first = _entry(hass, name="My Printer")
    first_device_id, first_entities = _register_legacy(hass, first, with_mac=False)
    await _setup(hass, first)

    second = _entry(hass, name="Same Printer", ip="192.0.2.11")
    second_device_id, second_entities = _register_legacy(hass, second, with_mac=False)
    await _setup(hass, second)

    dev_reg = dr.async_get(hass)
    assert _device(hass, GUID, first).id == first_device_id
    assert _device(hass, second.entry_id, second).id == second_device_id
    assert first.unique_id == GUID
    assert second.unique_id is None

    ent_reg = er.async_get(hass)
    for key, entity_id in first_entities.items():
        assert ent_reg.async_get(entity_id).unique_id == f"{GUID}_{key}"
    assert ent_reg.async_get(second_entities["printer_activity"]).unique_id == "same_printer_printer_activity"
    assert ent_reg.async_get(second_entities["camera"]).unique_id == f"{second.entry_id}_camera"
    assert ent_reg.async_get(second_entities["firmware"]).unique_id == f"{second.entry_id}_firmware"
    for entity in er.async_entries_for_config_entry(ent_reg, second.entry_id):
        assert entity.device_id == second_device_id
        assert hass.states.get(entity.entity_id) is not None or entity.disabled
