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
