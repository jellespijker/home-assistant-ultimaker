"""Tests for the Ultimaker sensor platform."""
import asyncio
from unittest.mock import patch, MagicMock

import pytest
from homeassistant.setup import async_setup_component

from custom_components.ultimaker.sensor import (
    SENSOR_TYPES,
    UltimakerStatusData,
    UltimakerStatusSensor,
)


@pytest.fixture
def mock_session():
    """Create a mock aiohttp session."""
    session = MagicMock()
    return session


@pytest.fixture
def mock_ultimaker_data(mock_session):
    """Create a mock UltimakerStatusData instance."""
    data = UltimakerStatusData(mock_session, "192.168.1.100")
    
    # Mock the fetch_data method to return test data
    async def mock_fetch_data(url):
        if "printer" in url:
            return {
                "status": "printing",
                "heads": [
                    {
                        "extruders": [
                            {
                                "hotend": {
                                    "id": "AA 0.4",
                                    "temperature": {
                                        "current": 210.5,
                                        "target": 215.0
                                    }
                                }
                            },
                            {
                                "hotend": {
                                    "id": "BB 0.4",
                                    "temperature": {
                                        "current": 200.0,
                                        "target": 205.0
                                    }
                                }
                            }
                        ]
                    }
                ],
                "bed": {
                    "type": "glass",
                    "temperature": {
                        "current": 60.2,
                        "target": 60.0
                    }
                }
            }
        elif "print_job" in url:
            return {
                "state": "printing",
                "progress": 0.45
            }
        elif "system" in url:
            return {
                "name": "My Ultimaker"
            }
        return {}
    
    data.fetch_data = mock_fetch_data
    return data


async def test_sensor_creation():
    """Test creating an Ultimaker sensor."""
    sensor = UltimakerStatusSensor(
        MagicMock(),
        "Test Printer Status",
        "status",
        "",
        "mdi:printer-3d",
        2
    )
    
    assert sensor.name == "Test Printer Status"
    assert sensor.icon == "mdi:printer-3d"
    assert sensor.unit_of_measurement == ""


async def test_sensor_update(mock_ultimaker_data):
    """Test updating an Ultimaker sensor."""
    # Create a status sensor
    status_sensor = UltimakerStatusSensor(
        mock_ultimaker_data,
        "Test Printer Status",
        "status",
        "",
        "mdi:printer-3d",
        2
    )
    
    # Create a progress sensor
    progress_sensor = UltimakerStatusSensor(
        mock_ultimaker_data,
        "Test Print Job Progress",
        "progress",
        "%",
        "mdi:progress-clock",
        2
    )
    
    # Create a bed temperature sensor
    bed_temp_sensor = UltimakerStatusSensor(
        mock_ultimaker_data,
        "Test Bed Temperature",
        "bed_temperature",
        "°C",
        "mdi:thermometer",
        2
    )
    
    # Mock the async_update method of UltimakerStatusData
    with patch.object(mock_ultimaker_data, 'async_update', return_value=None):
        # Set the latest_data property to return our mock data
        mock_ultimaker_data._data = await mock_ultimaker_data.fetch_data("printer")
        mock_ultimaker_data._data.update(await mock_ultimaker_data.fetch_data("print_job"))
        mock_ultimaker_data._data.update(await mock_ultimaker_data.fetch_data("system"))
        
        # Update the sensors
        await status_sensor.async_update()
        await progress_sensor.async_update()
        await bed_temp_sensor.async_update()
    
    # Check the sensor states
    assert status_sensor.state == "printing"
    assert progress_sensor.state == 45.0  # 0.45 * 100
    assert bed_temp_sensor.state == 60.2


def test_run_example():
    """Run a simple test to demonstrate the testing process."""
    # This is a simple test that always passes
    assert True, "This test should always pass"
    print("Test example ran successfully!")