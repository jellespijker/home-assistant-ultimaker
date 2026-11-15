"""A cloud connection: signing in with an API token and importing chosen printers."""

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ultimaker.const import DOMAIN
from custom_components.ultimaker.digital_factory import ApiUnavailable, AuthenticationError

from .conftest import GUID, cluster


async def _start_cloud_flow(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.MENU
    return await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "cloud"})


async def _add_cloud(hass: HomeAssistant, printers: list[str]) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, title="Digital Factory", unique_id="cloud_org-1",
        data={"connection": "cloud", "api_token": "umapi-test|eu"}, options={"printers": printers},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _unique_ids(hass: HomeAssistant, entry: MockConfigEntry) -> set[str]:
    return {e.unique_id for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)}


async def test_flow_imports_only_the_ticked_printers(hass: HomeAssistant, mock_cloud) -> None:
    result = await _start_cloud_flow(hass)
    assert result["step_id"] == "cloud"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"api_token": " umapi-test|eu "})
    assert result["step_id"] == "printers"
    offered = result["data_schema"].schema["printers"].config["options"]
    assert [o["value"] for o in offered] == ["guid-2", "guid-1"]  # sorted by name
    assert "Lab Factor 4" in offered[0]["label"]

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"printers": ["guid-1"]})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"connection": "cloud", "api_token": "umapi-test|eu"}
    assert result["options"] == {"printers": ["guid-1"]}
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == "cloud_org-1"
    ids = _unique_ids(hass, entry)
    assert "guid-1_cloud_status" in ids
    assert not any(i.startswith("guid-2") for i in ids)


async def test_flow_rejects_a_bad_token_and_recovers(hass: HomeAssistant, mock_cloud) -> None:
    result = await _start_cloud_flow(hass)

    # A double-click in a terminal selects the token only up to the "|".
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"api_token": "umapi-abc"})
    assert result["errors"] == {"base": "incomplete_token"}

    mock_cloud.list_error = AuthenticationError("nope")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"api_token": "umapi-bad|eu"})
    assert result["errors"] == {"base": "invalid_auth"}

    mock_cloud.list_error = ApiUnavailable("down")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"api_token": "umapi-good|eu"})
    assert result["errors"] == {"base": "cannot_connect"}

    mock_cloud.list_error = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"api_token": "umapi-good|eu"})
    assert result["step_id"] == "printers"


async def test_same_workspace_cannot_be_added_twice(hass: HomeAssistant, mock_cloud) -> None:
    await _add_cloud(hass, ["guid-1"])

    result = await _start_cloud_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"api_token": "umapi-other|eu"})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_cloud_printer_states(hass: HomeAssistant, mock_cloud) -> None:
    await _add_cloud(hass, ["guid-1"])

    assert hass.states.get("sensor.workshop_s8_status").state == "printing"
    queue = hass.states.get("sensor.workshop_s8_print_queue")
    assert queue.state == "2"
    assert [j["name"] for j in queue.attributes["jobs"]] == ["bracket", "lid"]
    assert hass.states.get("sensor.workshop_s8_last_print_job_result").state == "finished"
    assert hass.states.get("sensor.workshop_s8_active_faults").state == "1"
    assert hass.states.get("sensor.workshop_s8_print_job_progress").state == "25.0"
    assert hass.states.get("sensor.workshop_s8_extruder_1_material").state == "Ultimaker PLA White"
    assert hass.states.get("sensor.workshop_s8_material_station_slot_1_remaining").state == "40"
    assert hass.states.get("sensor.workshop_s8_air_manager_filter").state == "peak_performance"
    assert hass.states.get("binary_sensor.workshop_s8_maintenance_required").state == "off"
    assert hass.states.get("binary_sensor.workshop_s8_digital_factory_connection").state == "on"


async def _add_lan(hass: HomeAssistant) -> MockConfigEntry:
    lan = MockConfigEntry(domain=DOMAIN, title="My Printer", data={"name": "My Printer", "ip": "192.0.2.10"})
    lan.add_to_hass(hass)
    assert await hass.config_entries.async_setup(lan.entry_id)
    await hass.async_block_till_done()
    return lan


def _devices(hass: HomeAssistant, entry: MockConfigEntry):
    return dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)


def _assert_merged(hass: HomeAssistant, lan: MockConfigEntry, cloud: MockConfigEntry) -> None:
    """One device, owned by the LAN connection, carrying LAN and Digital Factory entities."""
    [device] = _devices(hass, lan)
    assert _devices(hass, cloud) == []
    assert not _unique_ids(hass, cloud)
    ids = _unique_ids(hass, lan)
    assert f"{GUID}_printer_activity" in ids
    assert f"{GUID}_cloud_queue_length" in ids
    assert f"{GUID}_cloud_extruder_0_material" in ids
    assert f"{GUID}_cloud_maintenance_required" in ids
    # What the LAN connection already reports live is not duplicated.
    assert f"{GUID}_cloud_job_progress" not in ids
    assert f"{GUID}_cloud_extruder_0_temperature" not in ids
    assert f"{GUID}_cloud_build_plate_temperature" not in ids
    ent_reg = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(ent_reg, lan.entry_id):
        assert entity.device_id == device.id
    queue = ent_reg.async_get_entity_id("sensor", DOMAIN, f"{GUID}_cloud_queue_length")
    assert hass.states.get(queue).state == "2"


async def test_merged_printer_is_one_device_when_lan_was_added_first(hass: HomeAssistant, mock_cloud, mock_poll) -> None:
    mock_cloud.printers = [cluster(GUID)]
    lan = await _add_lan(hass)

    cloud = await _add_cloud(hass, [GUID])

    _assert_merged(hass, lan, cloud)


async def test_merged_printer_is_one_device_when_cloud_was_added_first(hass: HomeAssistant, mock_cloud, mock_poll) -> None:
    """The cloud connection's own device and entities move to the LAN connection, keeping entity IDs."""
    mock_cloud.printers = [cluster(GUID)]
    cloud = await _add_cloud(hass, [GUID])
    ent_reg = er.async_get(hass)
    queue_before = ent_reg.async_get_entity_id("sensor", DOMAIN, f"{GUID}_cloud_queue_length")
    assert queue_before == "sensor.workshop_s8_print_queue"
    assert len(_devices(hass, cloud)) == 1

    lan = await _add_lan(hass)

    _assert_merged(hass, lan, cloud)
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, f"{GUID}_cloud_queue_length") == queue_before


async def test_removing_the_lan_connection_hands_the_printer_back(hass: HomeAssistant, mock_cloud, mock_poll) -> None:
    mock_cloud.printers = [cluster(GUID)]
    lan = await _add_lan(hass)
    cloud = await _add_cloud(hass, [GUID])

    await hass.config_entries.async_remove(lan.entry_id)
    await hass.async_block_till_done()

    assert len(_devices(hass, cloud)) == 1
    ids = _unique_ids(hass, cloud)
    assert f"{GUID}_cloud_queue_length" in ids
    assert f"{GUID}_cloud_job_progress" in ids  # now the only source of progress


async def test_unticking_a_printer_removes_it(hass: HomeAssistant, mock_cloud) -> None:
    entry = await _add_cloud(hass, ["guid-1", "guid-2"])
    assert len(_devices(hass, entry)) == 2

    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(result["flow_id"], {"printers": ["guid-2"]})
    await hass.async_block_till_done()

    assert not any(i.startswith("guid-1") for i in _unique_ids(hass, entry))
    assert [d.name for d in _devices(hass, entry)] == ["Lab Factor 4"]


async def test_changing_the_import_list_adds_printers(hass: HomeAssistant, mock_cloud) -> None:
    entry = await _add_cloud(hass, ["guid-1"])

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "printers"
    await hass.config_entries.options.async_configure(result["flow_id"], {"printers": ["guid-1", "guid-2"]})
    await hass.async_block_till_done()

    assert "guid-2_cloud_status" in _unique_ids(hass, entry)
    assert hass.states.get("sensor.lab_factor_4_status").state == "printing"


async def test_printer_that_left_the_workspace_becomes_unavailable(hass: HomeAssistant, mock_cloud) -> None:
    entry = await _add_cloud(hass, ["guid-1"])
    mock_cloud.printers = [cluster("guid-2")]

    await hass.data[DOMAIN][entry.entry_id]["coordinator"].async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.workshop_s8_status").state == "unavailable"


async def test_rejected_token_asks_to_sign_in_again(hass: HomeAssistant, mock_cloud) -> None:
    entry = await _add_cloud(hass, ["guid-1"])
    mock_cloud.list_error = AuthenticationError("revoked")

    await hass.data[DOMAIN][entry.entry_id]["coordinator"].async_refresh()
    await hass.async_block_till_done()

    [flow] = hass.config_entries.flow.async_progress()
    assert flow["context"]["source"] == "reauth"
    assert flow["step_id"] == "reauth_confirm"

    mock_cloud.list_error = None
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {"api_token": "umapi-new|eu"})
    await hass.async_block_till_done()
    assert result["reason"] == "reauth_successful"
    assert entry.data["api_token"] == "umapi-new|eu"
    assert entry.state is ConfigEntryState.LOADED


async def test_reauth_refuses_a_different_workspace(hass: HomeAssistant, mock_cloud) -> None:
    entry = await _add_cloud(hass, ["guid-1"])
    mock_cloud.list_error = AuthenticationError("revoked")
    await hass.data[DOMAIN][entry.entry_id]["coordinator"].async_refresh()
    await hass.async_block_till_done()
    [flow] = hass.config_entries.flow.async_progress()

    mock_cloud.list_error = None
    mock_cloud.printers = [cluster("guid-9", organization_id="org-other")]
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {"api_token": "umapi-other|eu"})

    assert result["reason"] == "wrong_account"
    assert entry.data["api_token"] == "umapi-test|eu"


async def test_temporary_outage_keeps_the_credential(hass: HomeAssistant, mock_cloud) -> None:
    entry = await _add_cloud(hass, ["guid-1"])
    mock_cloud.list_error = ApiUnavailable("down")

    await hass.data[DOMAIN][entry.entry_id]["coordinator"].async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.workshop_s8_status").state == "unavailable"
    assert not hass.config_entries.flow.async_progress()
    assert entry.state is ConfigEntryState.LOADED


async def test_merged_printer_survives_both_connections_starting_together(hass: HomeAssistant, mock_cloud, mock_poll) -> None:
    """At Home Assistant startup both entries set up concurrently, in no fixed order."""
    mock_cloud.printers = [cluster(GUID)]
    lan = MockConfigEntry(
        domain=DOMAIN, title="My Printer", unique_id=GUID, data={"name": "My Printer", "ip": "192.0.2.10"}
    )
    cloud = MockConfigEntry(
        domain=DOMAIN, title="Digital Factory", unique_id="cloud_org-1",
        data={"connection": "cloud", "api_token": "umapi-test|eu"}, options={"printers": [GUID]},
    )
    lan.add_to_hass(hass)
    cloud.add_to_hass(hass)

    # Setting up the integration starts every entry of the domain at once.
    assert await hass.config_entries.async_setup(cloud.entry_id)
    await hass.async_block_till_done()

    assert lan.state is ConfigEntryState.LOADED and cloud.state is ConfigEntryState.LOADED
    _assert_merged(hass, lan, cloud)


async def test_merged_printer_follows_a_cloud_reload(hass: HomeAssistant, mock_cloud, mock_poll) -> None:
    mock_cloud.printers = [cluster(GUID)]
    lan = await _add_lan(hass)
    cloud = await _add_cloud(hass, [GUID])
    mock_cloud.printers = [cluster(GUID, display_status="wait_cleanup")]

    assert await hass.config_entries.async_reload(cloud.entry_id)
    await hass.async_block_till_done()

    _assert_merged(hass, lan, cloud)
    status = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{GUID}_cloud_status")
    assert hass.states.get(status).state == "wait_cleanup"


async def test_unticking_a_merged_printer_removes_its_cloud_entities(hass: HomeAssistant, mock_cloud, mock_poll) -> None:
    mock_cloud.printers = [cluster(GUID), cluster("guid-2", friendly_name="Lab Factor 4")]
    lan = await _add_lan(hass)
    cloud = await _add_cloud(hass, [GUID, "guid-2"])

    result = await hass.config_entries.options.async_init(cloud.entry_id)
    await hass.config_entries.options.async_configure(result["flow_id"], {"printers": ["guid-2"]})
    await hass.async_block_till_done()

    ids = _unique_ids(hass, lan)
    assert f"{GUID}_printer_activity" in ids
    assert not any("_cloud_" in i for i in ids)


async def test_removing_the_cloud_connection_leaves_the_lan_printer_intact(hass: HomeAssistant, mock_cloud, mock_poll) -> None:
    mock_cloud.printers = [cluster(GUID)]
    lan = await _add_lan(hass)
    cloud = await _add_cloud(hass, [GUID])

    await hass.config_entries.async_remove(cloud.entry_id)
    await hass.async_block_till_done()

    ids = _unique_ids(hass, lan)
    assert f"{GUID}_printer_activity" in ids
    assert not any("_cloud_" in i for i in ids)
    assert len(_devices(hass, lan)) == 1
