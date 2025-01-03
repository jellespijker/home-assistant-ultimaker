"""Platform for sensor integration.

configuration.yaml
sensor:
  - platform: ultimaker
    name: PRINTER_NAME
    host: IP_ADDRESS
    scan_interval: 10 (optional, default 10)
    decimal: 2 (optional, default = 2)
    resources:
      - status (optional)
      - state (optional)
      - progress (optional)
      - bed_temperature (optional)
      - bed_temperature_target (optional)
      - bed_type (optional)
      - hotend_1_temperature (optional)
      - hotend_1_temperature_target (optional)
      - hotend_1_temperature_id (optional)
      - hotend_2_temperature (optional)
      - hotend_2_temperature_target (optional)
      - hotend_2_temperature_id (optional)
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import aiohttp
import async_timeout
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SENSORS,
    TEMP_CELSIUS,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType, StateType
from homeassistant.util import Throttle

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "status": ["Printer status", "", "mdi:printer-3d"],
    "state": ["Print job state", "", "mdi:printer-3d-nozzle"],
    "progress": ["Print job progress", "%", "mdi:progress-clock"],
    "bed_temperature": ["Bed temperature", TEMP_CELSIUS, "mdi:thermometer"],
    "bed_temperature_target": [
        "Bed temperature target",
        TEMP_CELSIUS,
        "mdi:thermometer",
    ],
    "bed_type": ["Bed type", "", "mdi:layers"],
    "hotend_1_temperature": ["Hotend 1 temperature", TEMP_CELSIUS, "mdi:thermometer"],
    "hotend_1_temperature_target": [
        "Hotend 1 temperature target",
        TEMP_CELSIUS,
        "mdi:thermometer",
    ],
    "hotend_1_serial": ["Hotend 1 serial number", "", "mdi:serial"],
    "hotend_1_id": ["Hotend 1 id", "", "mdi:printer-3d-nozzle-outline"],
    "hotend_2_temperature": ["Hotend 2 temperature", TEMP_CELSIUS, "mdi:thermometer"],
    "hotend_2_temperature_target": [
        "Hotend 2 temperature target",
        TEMP_CELSIUS,
        "mdi:thermometer",
    ],
    "hotend_2_statistics_material": ["Hotend 2 statistics material", "", "mdi:statistics"],
    "hotend_2_serial": ["Hotend 2 serial number", "", "mdi:serial"],
    "hotend_2_id": ["Hotend 2 id", "", "mdi:printer-3d-nozzle-outline"],
}

CONF_DECIMAL = "decimal"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_DECIMAL, default=2): cv.positive_int,
        vol.Required(CONF_SENSORS, default=list(SENSOR_TYPES)): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
    }
)


MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)
BASE_URL = "http://{0}/api/v1"


async def async_setup_platform(
    hass: HomeAssistantType, config, async_add_entities, discovery_info=None
):
    """Setup the Ultimaker printer sensors"""
    session = async_get_clientsession(hass)
    data = UltimakerStatusData(session, config.get(CONF_HOST))
    await data.async_update()

    entities = []
    if CONF_SENSORS in config:
        for sensor in config[CONF_SENSORS]:
            sensor_type = sensor.lower()
            name = f"{config.get(CONF_NAME)} {SENSOR_TYPES[sensor][0]}"
            unit = SENSOR_TYPES[sensor][1]
            icon = SENSOR_TYPES[sensor][2]

            _LOGGER.debug(
                f"Adding Ultimaker printer sensor: {name}, {sensor_type}, {unit}, {icon}"
            )
            entities.append(
                UltimakerStatusSensor(
                    data, name, sensor_type, unit, icon, config.get(CONF_DECIMAL)
                )
            )

    async_add_entities(entities, True)


class UltimakerStatusData(object):
    """Handle Ultimaker object and limit updates"""

    def __init__(self, session, host):
        if host:
            self._url_printer = BASE_URL.format(host) + "/printer"
            self._url_print_job = BASE_URL.format(host) + "/print_job"
            self._url_system = BASE_URL.format(host) + "/system"
        self._host = host
        self._session = session
        self._data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Download and update data from the Ultimaker Printer"""
        if self._host:
            try:
                printer_data = await self.fetch_data(self._url_printer)
                print_job_data = await self.fetch_data(self._url_print_job)
                system_data = await self.fetch_data(self._url_system)
                self._data = printer_data.copy()
                self._data.update(print_job_data)
                self._data.update(system_data)
            except aiohttp.ClientError:
                self._data = {"status": "not connected"}
            self._data["sampleTime"] = datetime.now()

    async def fetch_data(self, url):
        try:
            with async_timeout.timeout(5):
                response = await self._session.get(url)
        except aiohttp.ClientError as err:
            _LOGGER.warning(f"Printer {self._host} is offline")
            raise err
        except asyncio.TimeoutError:
            _LOGGER.error(
                f" Timeout error occurred while polling ultimaker printer using url {url}"
            )
        except Exception as err:
            _LOGGER.error(
                f"Unknown error occurred while polling Ultimaker printer using {url} -> error: {err}"
            )
            return {}

        try:
            ret = await response.json()
        except Exception as err:
            _LOGGER.error(f"Cannot parse data received from Ultimaker printer {err}")
            return {}
        return ret

    @property
    def latest_data(self):
        return self._data


class UltimakerStatusSensor(Entity):
    """Representation of a Ultimaker status sensor"""

    def __init__(
        self, data: UltimakerStatusData, name, sensor_type, unit, icon, decimal
    ):
        """Initialize the sensor."""
        self._data = data
        self._name = name
        self._type = sensor_type
        self._unit = unit
        self._icon = icon
        self._decimal = decimal

        self._state = None
        self._last_updated = None

    @property
    def name(self) -> Optional[str]:
        return self._name

    @property
    def icon(self) -> Optional[str]:
        return self._icon

    @property
    def state(self) -> StateType:
        if isinstance(self._state, float):
            return round(self._state, self._decimal)
        else:
            return self._state

    @property
    def unit_of_measurement(self) -> Optional[str]:
        return self._unit

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        attr = {}
        if self._last_updated is not None:
            attr["Last Updated"] = self._last_updated
        return attr

    async def async_update(self):

        await self._data.async_update()
        data = self._data.latest_data

        if data:
            self._last_updated = data.get("sampleTime", None)

            if self._type == "status":
                self._state = data.get("status", "not connected")

            elif self._type == "state":
                self._state = data.get("state", None)
                if self._state:
                    self._state = self._state.replace("_", " ")

            elif self._type == "progress":
                self._state = data.get("progress", 0)
                if self._state:
                    self._state *= 100
                self._state = self._state

            elif "bed" in self._type:
                bed = data.get("bed", None)
                if "temperature" in self._type and bed:
                    temperature = bed.get("temperature", None)
                    if temperature:
                        if "target" in self._type:
                            self._state = temperature.get("target", None)
                        else:
                            self._state = temperature.get("current", None)
                if "type" in self._type and bed:
                    self._state = bed.get("type", None)

            elif "hotend" in self._type:
                head = data.get("heads", [None])[0]
                if head:
                    idx = int(self._type.split("_")[1]) - 1
                    extruder = head["extruders"][idx]
                    hot_end = extruder["hotend"]
                    if "temperature" in self._type and hot_end:
                        temperature = hot_end["temperature"]
                        if "target" in self._type:
                            self._state = temperature.get("target", None)
                        else:
                            self._state = temperature.get("current", None)
                    if "id" in self._type and hot_end:
                        self._state = hot_end["id"]

            _LOGGER.debug(f"Device: {self._type} State: {self._state}")
