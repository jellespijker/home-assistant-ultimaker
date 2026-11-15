"""Shared fixtures for the Ultimaker integration tests."""

from unittest.mock import AsyncMock, patch

import pytest

GUID = "6f0a3a5e-1c2b-4d3e-8f90-123456789abc"
MAC = "cc:bd:d3:00:44:ec"


def printer_data(guid: str | None = GUID) -> dict:
    """Return what the coordinator yields for one poll of a LAN printer."""
    system = {"variant": "Ultimaker S5", "firmware": "9.0.0", "hardware": {"revision": 1}}
    if guid is not None:
        system["guid"] = guid
    return {
        "printer": {"status": "idle"},
        "print_job": {},
        "system": system,
        "ambient_temperature": {"current": 215},
        "latest_firmware": "9.0.1",
        "camera_stream_url": "http://192.0.2.10/api/v1/camera/0/stream",
        "camera_snapshot_url": "http://192.0.2.10/api/v1/camera/0/snapshot",
        "mac": MAC,
    }


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load the integration from custom_components."""
    yield


@pytest.fixture
def mock_poll():
    """Replace the printer poll; set `.return_value` to change what the printer reports."""
    with patch(
        "custom_components.ultimaker.coordinator.UltimakerDataUpdateCoordinator._async_update_data",
        new_callable=AsyncMock,
        return_value=printer_data(),
    ) as poll:
        yield poll


def cluster(guid: str = "guid-1", **overrides) -> dict:
    data = {
        "cluster_id": f"cluster-{guid}",
        "host_guid": guid,
        "friendly_name": "Workshop S8",
        "host_internal_ip": "192.0.2.10",
        "host_name": "ultimakersystem-0013955289b5",
        "host_print_job_count": 2,
        "is_online": True,
        "display_status": "printing",
        "printer_type": "ultimaker_s8",
        "capabilities": ["queue", "identify"],
        "host_current_print_job": {
            "uuid": "job-1", "name": "bracket", "status": "printing", "state": "in_progress",
            "started": True, "time_total": 1000, "time_elapsed": 250, "time_remaining": 750,
        },
        "host_printer": {
            "uuid": "printer-1",
            "machine_variant": "Ultimaker S8",
            "firmware_version": "12.0.0.0",
            "latest_available_firmware": "12.1.0.0",
            "firmware_update_status": "update_available",
            "enabled": True,
            "maintenance_required": False,
            "build_plate": {"temperature": 59.8, "type": "flex"},
            "air_manager": {"supported": True, "status": "available", "filter_status": "peak_performance", "filter_age": 8, "filter_max_age": 1500},
            "configuration": [
                {"extruder_index": 0, "print_core_id": "AA 0.4", "temperature": 205.3,
                 "material": {"brand": "Ultimaker", "material": "PLA", "color": "White"}},
                {"extruder_index": 1, "print_core_id": "AA 0.4", "temperature": 35.3,
                 "material": {"brand": "empty", "material": "empty", "color": "empty"}},
            ],
            "material_station": {"supported": True, "material_slots": [
                {"slot_index": 0, "extruder_index": 0, "material_empty": False, "material_remaining": 0.4,
                 "material": {"brand": "Ultimaker", "material": "PLA", "color": "White"}},
                {"slot_index": 1, "extruder_index": 1, "material_empty": True, "material_remaining": -1,
                 "material": {"brand": "empty", "material": "empty", "color": "empty"}},
            ]},
            "faults": [{"code": "HEATER_HALT", "severity": "ERROR", "message": "halt", "timestamp": "2026-11-12T18:07:22+00:00"}],
        },
    }
    data.update(overrides)
    return data
