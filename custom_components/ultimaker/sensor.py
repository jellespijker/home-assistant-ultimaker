"""Platform for sensor integration."""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import DOMAIN
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from .const import (
    API_TYPE_CLOUD,
    CONF_API_TYPE,
    CONF_DECIMAL,
    DEFAULT_DECIMAL,
    SENSOR_STATUS,
    SENSOR_STATE,
    SENSOR_PROGRESS,
    SENSOR_BED_TEMPERATURE,
    SENSOR_BED_TEMPERATURE_TARGET,
    SENSOR_BED_TYPE,
    SENSOR_HOTEND_1_TEMPERATURE,
    SENSOR_HOTEND_1_TEMPERATURE_TARGET,
    SENSOR_HOTEND_1_ID,
    SENSOR_HOTEND_2_TEMPERATURE,
    SENSOR_HOTEND_2_TEMPERATURE_TARGET,
    SENSOR_HOTEND_2_ID,
    SENSOR_CLUSTER_STATUS,
    SENSOR_PRINTER_COUNT,
    SENSOR_MAINTENANCE_REQUIRED,
    SENSOR_MATERIAL_REMAINING,
    SENSOR_HOTEND_1_MATERIAL_EXTRUDED,
    SENSOR_HOTEND_1_MATERIAL_REMAINING,
    SENSOR_HOTEND_1_MATERIAL_TYPE,
    SENSOR_HOTEND_2_MATERIAL_EXTRUDED,
    SENSOR_HOTEND_2_MATERIAL_REMAINING,
    SENSOR_HOTEND_2_MATERIAL_TYPE,
    SENSOR_PRINT_JOB_TIME_TOTAL,
    SENSOR_PRINT_JOB_TIME_ELAPSED,
    SENSOR_PRINT_JOB_TIME_REMAINING,
)

_LOGGER = logging.getLogger(__name__)
_LOGGER.info("Initializing Ultimaker sensor platform")

# Define sensor descriptions
SENSOR_DESCRIPTIONS = [
    SensorEntityDescription(
        key=SENSOR_STATUS,
        name="Printer status",
        icon="mdi:printer-3d",
    ),
    SensorEntityDescription(
        key=SENSOR_STATE,
        name="Print job state",
        icon="mdi:printer-3d-nozzle",
    ),
    SensorEntityDescription(
        key=SENSOR_PROGRESS,
        name="Print job progress",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:progress-clock",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_BED_TEMPERATURE,
        name="Bed temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_BED_TEMPERATURE_TARGET,
        name="Bed temperature target",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_BED_TYPE,
        name="Bed type",
        icon="mdi:layers",
    ),
    SensorEntityDescription(
        key=SENSOR_HOTEND_1_TEMPERATURE,
        name="Hotend 1 temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_HOTEND_1_TEMPERATURE_TARGET,
        name="Hotend 1 temperature target",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_HOTEND_1_ID,
        name="Hotend 1 id",
        icon="mdi:printer-3d-nozzle-outline",
    ),
    SensorEntityDescription(
        key=SENSOR_HOTEND_2_TEMPERATURE,
        name="Hotend 2 temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_HOTEND_2_TEMPERATURE_TARGET,
        name="Hotend 2 temperature target",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_HOTEND_2_ID,
        name="Hotend 2 id",
        icon="mdi:printer-3d-nozzle-outline",
    ),
    # Hotend 1 material sensors
    SensorEntityDescription(
        key=SENSOR_HOTEND_1_MATERIAL_EXTRUDED,
        name="Hotend 1 material extruded",
        native_unit_of_measurement="mm",
        icon="mdi:printer-3d-nozzle",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=SENSOR_HOTEND_1_MATERIAL_REMAINING,
        name="Hotend 1 material remaining",
        native_unit_of_measurement="mm",
        icon="mdi:spool",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_HOTEND_1_MATERIAL_TYPE,
        name="Hotend 1 material type",
        icon="mdi:material-design",
    ),
    # Hotend 2 material sensors
    SensorEntityDescription(
        key=SENSOR_HOTEND_2_MATERIAL_EXTRUDED,
        name="Hotend 2 material extruded",
        native_unit_of_measurement="mm",
        icon="mdi:printer-3d-nozzle",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=SENSOR_HOTEND_2_MATERIAL_REMAINING,
        name="Hotend 2 material remaining",
        native_unit_of_measurement="mm",
        icon="mdi:spool",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_HOTEND_2_MATERIAL_TYPE,
        name="Hotend 2 material type",
        icon="mdi:material-design",
    ),
    # Print job time sensors
    SensorEntityDescription(
        key=SENSOR_PRINT_JOB_TIME_TOTAL,
        name="Print job total time",
        native_unit_of_measurement="s",
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_PRINT_JOB_TIME_ELAPSED,
        name="Print job elapsed time",
        native_unit_of_measurement="s",
        icon="mdi:clock-start",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_PRINT_JOB_TIME_REMAINING,
        name="Print job remaining time",
        native_unit_of_measurement="s",
        icon="mdi:clock-end",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]

# Cloud-specific sensor descriptions
CLOUD_SENSOR_DESCRIPTIONS = [
    SensorEntityDescription(
        key=SENSOR_CLUSTER_STATUS,
        name="Cluster status",
        icon="mdi:printer-3d-nozzle-alert",
    ),
    SensorEntityDescription(
        key=SENSOR_PRINTER_COUNT,
        name="Printer count",
        icon="mdi:printer-3d",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_MAINTENANCE_REQUIRED,
        name="Maintenance required",
        icon="mdi:tools",
    ),
    SensorEntityDescription(
        key=SENSOR_MATERIAL_REMAINING,
        name="Material remaining",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:spool",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]


async def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType = None,
) -> None:
    """Set up the sensor platform."""
    _LOGGER.error(
        "The Ultimaker integration does not support YAML configuration. "
        "Please configure it through the UI (Devices & Services)"
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Ultimaker sensors based on a config entry."""
    _LOGGER.info("Setting up Ultimaker sensors for config entry %s", entry.entry_id)

    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    api_client = data["api_client"]
    _LOGGER.debug("Retrieved coordinator and API client from hass.data")

    # Determine which sensor descriptions to use based on API type
    descriptions = SENSOR_DESCRIPTIONS.copy()
    api_type = entry.data.get(CONF_API_TYPE)
    _LOGGER.debug("API type: %s", api_type)

    if api_type == API_TYPE_CLOUD:
        _LOGGER.debug("Adding cloud-specific sensor descriptions")
        descriptions.extend(CLOUD_SENSOR_DESCRIPTIONS)
        _LOGGER.info("Setting up cloud API sensors for Ultimaker")
    else:
        _LOGGER.info("Setting up local API sensors for Ultimaker")

    # Get decimal precision from options
    decimal = entry.options.get(CONF_DECIMAL, DEFAULT_DECIMAL)
    _LOGGER.debug("Using decimal precision: %s", decimal)

    # Create sensors
    entities = []
    _LOGGER.debug("Creating %d sensor entities", len(descriptions))

    for description in descriptions:
        _LOGGER.debug("Creating sensor: %s (key: %s)", description.name, description.key)
        entities.append(
            UltimakerSensor(
                coordinator=coordinator,
                description=description,
                entry_id=entry.entry_id,
                decimal=decimal,
            )
        )

    _LOGGER.info("Adding %d Ultimaker sensor entities", len(entities))
    async_add_entities(entities)
    _LOGGER.debug("Ultimaker sensors setup completed for config entry %s", entry.entry_id)


class UltimakerSensor(CoordinatorEntity, SensorEntity):
    """Representation of an Ultimaker sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: SensorEntityDescription,
        entry_id: str,
        decimal: int,
    ) -> None:
        """Initialize the sensor."""
        _LOGGER.debug("Initializing UltimakerSensor: %s (key: %s)", description.name, description.key)
        super().__init__(coordinator)

        self.entity_description = description
        self._entry_id = entry_id
        self._decimal = decimal

        # Extract device name from coordinator name
        device_name = coordinator.name
        if "(" in device_name and ")" in device_name:
            device_name = device_name.split("(")[1].split(")")[0]

        # Create unique ID using device name and sensor key
        self._attr_unique_id = f"{entry_id}_{device_name}_{description.key}"
        _LOGGER.debug("Sensor unique_id: %s", self._attr_unique_id)

        # Set up device info
        _LOGGER.debug("Setting up device info for sensor %s", description.name)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=f"Ultimaker Printer ({device_name})",
            manufacturer="Ultimaker",
            model="Ultimaker Printer",
        )

        _LOGGER.info("Initialized Ultimaker sensor: %s", description.name)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        sensor_name = self.entity_description.name
        sensor_key = self.entity_description.key

        _LOGGER.debug("Checking availability for sensor: %s (key: %s)", sensor_name, sensor_key)

        # Check if coordinator update was successful
        if not self.coordinator.last_update_success:
            _LOGGER.debug("Sensor %s unavailable: coordinator update failed", sensor_name)
            return False

        # For status sensor, always available if coordinator has data
        if sensor_key == SENSOR_STATUS and self.coordinator.data:
            _LOGGER.debug("Status sensor is always available when coordinator has data")
            return True

        # For other sensors, check if we have valid data
        data = self.coordinator.data
        if not data:
            _LOGGER.debug("Sensor %s unavailable: no data from coordinator", sensor_name)
            return False

        # Check if printer is connected
        status = data.get("status")
        if status in ["not connected", "timeout", "error"]:
            _LOGGER.debug("Sensor %s unavailable: printer status is '%s'", sensor_name, status)
            return False

        # For hotend 2 sensors, check if the printer has a second extruder
        if sensor_key in [
            SENSOR_HOTEND_2_TEMPERATURE, 
            SENSOR_HOTEND_2_TEMPERATURE_TARGET, 
            SENSOR_HOTEND_2_ID,
            SENSOR_HOTEND_2_MATERIAL_EXTRUDED,
            SENSOR_HOTEND_2_MATERIAL_REMAINING,
            SENSOR_HOTEND_2_MATERIAL_TYPE
        ]:
            heads = data.get("heads", [{}])
            if not heads or len(heads) == 0:
                return False

            head = heads[0]
            extruders = head.get("extruders", [])
            if len(extruders) < 2:
                _LOGGER.debug("Sensor %s unavailable: printer has fewer than 2 extruders", sensor_name)
                return False

        # For all other sensors, assume they're available if the printer is connected
        # The API client ensures all required fields are present with default values
        _LOGGER.debug("Sensor %s available (printer is connected)", sensor_name)
        return True

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        sensor_name = self.entity_description.name
        sensor_key = self.entity_description.key

        _LOGGER.debug("Getting native value for sensor: %s (key: %s)", sensor_name, sensor_key)

        data = self.coordinator.data
        if not data:
            _LOGGER.debug("No data available for sensor %s", sensor_name)
            return None

        value = None
        key = self.entity_description.key
        _LOGGER.debug("Extracting value for sensor %s from data", sensor_name)

        if key == SENSOR_STATUS:
            value = data.get("status", "not connected")
            _LOGGER.debug("Status sensor value: %s", value)

        elif key == SENSOR_STATE:
            value = data.get("state", None)
            _LOGGER.debug("Raw state value: %s", value)
            if value:
                value = value.replace("_", " ")
                _LOGGER.debug("Formatted state value: %s", value)
            else:
                _LOGGER.debug("No state value found")

        elif key == SENSOR_PROGRESS:
            value = data.get("progress", 0)
            _LOGGER.debug("Raw progress value: %s", value)
            if value:
                value *= 100
                _LOGGER.debug("Scaled progress value: %s%%", value)

        elif key == SENSOR_BED_TEMPERATURE:
            bed = data.get("bed", {})
            temperature = bed.get("temperature", {})
            value = temperature.get("current", None)
            _LOGGER.debug("Bed temperature value: %s", value)

        elif key == SENSOR_BED_TEMPERATURE_TARGET:
            bed = data.get("bed", {})
            temperature = bed.get("temperature", {})
            value = temperature.get("target", None)
            _LOGGER.debug("Bed temperature target value: %s", value)

        elif key == SENSOR_BED_TYPE:
            bed = data.get("bed", {})
            value = bed.get("type", None)
            _LOGGER.debug("Bed type value: %s", value)

        elif key == SENSOR_HOTEND_1_TEMPERATURE:
            heads = data.get("heads", [{}])
            if heads and len(heads) > 0:
                head = heads[0]
                extruders = head.get("extruders", [{}])
                if extruders and len(extruders) > 0:
                    extruder = extruders[0]
                    hot_end = extruder.get("hotend", {})
                    temperature = hot_end.get("temperature", {})
                    value = temperature.get("current", None)
                    _LOGGER.debug("Hotend 1 temperature value: %s", value)
                else:
                    _LOGGER.debug("No extruders found for hotend 1 temperature")
            else:
                _LOGGER.debug("No heads found for hotend 1 temperature")

        elif key == SENSOR_HOTEND_1_TEMPERATURE_TARGET:
            heads = data.get("heads", [{}])
            if heads and len(heads) > 0:
                head = heads[0]
                extruders = head.get("extruders", [{}])
                if extruders and len(extruders) > 0:
                    extruder = extruders[0]
                    hot_end = extruder.get("hotend", {})
                    temperature = hot_end.get("temperature", {})
                    value = temperature.get("target", None)
                    _LOGGER.debug("Hotend 1 temperature target value: %s", value)
                else:
                    _LOGGER.debug("No extruders found for hotend 1 temperature target")
            else:
                _LOGGER.debug("No heads found for hotend 1 temperature target")

        elif key == SENSOR_HOTEND_1_ID:
            heads = data.get("heads", [{}])
            if heads and len(heads) > 0:
                head = heads[0]
                extruders = head.get("extruders", [{}])
                if extruders and len(extruders) > 0:
                    extruder = extruders[0]
                    hot_end = extruder.get("hotend", {})
                    value = hot_end.get("id", None)
                    _LOGGER.debug("Hotend 1 ID value: %s", value)
                else:
                    _LOGGER.debug("No extruders found for hotend 1 ID")
            else:
                _LOGGER.debug("No heads found for hotend 1 ID")

        elif key == SENSOR_HOTEND_2_TEMPERATURE:
            heads = data.get("heads", [{}])
            if heads and len(heads) > 0:
                head = heads[0]
                extruders = head.get("extruders", [{}])
                if extruders and len(extruders) > 1:
                    extruder = extruders[1]
                    hot_end = extruder.get("hotend", {})
                    temperature = hot_end.get("temperature", {})
                    value = temperature.get("current", None)
                    _LOGGER.debug("Hotend 2 temperature value: %s", value)
                else:
                    _LOGGER.debug("Fewer than 2 extruders found for hotend 2 temperature")
            else:
                _LOGGER.debug("No heads found for hotend 2 temperature")

        elif key == SENSOR_HOTEND_2_TEMPERATURE_TARGET:
            heads = data.get("heads", [{}])
            if heads and len(heads) > 0:
                head = heads[0]
                extruders = head.get("extruders", [{}])
                if extruders and len(extruders) > 1:
                    extruder = extruders[1]
                    hot_end = extruder.get("hotend", {})
                    temperature = hot_end.get("temperature", {})
                    value = temperature.get("target", None)
                    _LOGGER.debug("Hotend 2 temperature target value: %s", value)
                else:
                    _LOGGER.debug("Fewer than 2 extruders found for hotend 2 temperature target")
            else:
                _LOGGER.debug("No heads found for hotend 2 temperature target")

        elif key == SENSOR_HOTEND_2_ID:
            heads = data.get("heads", [{}])
            if heads and len(heads) > 0:
                head = heads[0]
                extruders = head.get("extruders", [{}])
                if extruders and len(extruders) > 1:
                    extruder = extruders[1]
                    hot_end = extruder.get("hotend", {})
                    value = hot_end.get("id", None)
                    _LOGGER.debug("Hotend 2 ID value: %s", value)
                else:
                    _LOGGER.debug("Fewer than 2 extruders found for hotend 2 ID")
            else:
                _LOGGER.debug("No heads found for hotend 2 ID")

        # Cloud-specific sensors
        elif key == SENSOR_CLUSTER_STATUS:
            value = data.get("cluster_status", None)
            _LOGGER.debug("Cluster status value: %s", value)

        elif key == SENSOR_PRINTER_COUNT:
            value = data.get("printer_count", 0)
            _LOGGER.debug("Printer count value: %s", value)

        elif key == SENSOR_MAINTENANCE_REQUIRED:
            # This is a placeholder - in a real implementation, you would
            # check if any maintenance tasks are pending
            value = "No"
            _LOGGER.debug("Maintenance required value: %s", value)

        elif key == SENSOR_MATERIAL_REMAINING:
            # Try to get actual material remaining if available
            try:
                heads = data.get("heads", [{}])
                if heads and len(heads) > 0:
                    head = heads[0]
                    extruders = head.get("extruders", [{}])
                    if extruders and len(extruders) > 0:
                        extruder = extruders[0]
                        active_material = extruder.get("active_material", {})
                        if "length_remaining" in active_material:
                            # Convert to percentage based on typical spool size (e.g., 750m)
                            length = active_material.get("length_remaining", 0)
                            typical_spool = 750000  # 750m in mm
                            value = min(100, max(0, (length / typical_spool) * 100))
                            _LOGGER.debug("Material remaining calculated from length: %s mm (%.1f%%)", 
                                         length, value)
                        else:
                            value = 0
                            _LOGGER.debug("No length_remaining field found for material remaining")
                    else:
                        value = 0
                        _LOGGER.debug("No extruders found for material remaining")
                else:
                    value = 0
                    _LOGGER.debug("No heads found for material remaining")
            except Exception as err:
                _LOGGER.warning("Error calculating material remaining: %s", err)
                value = 0

        # Hotend 1 material sensors
        elif key == SENSOR_HOTEND_1_MATERIAL_EXTRUDED:
            try:
                heads = data.get("heads", [{}])
                if heads and len(heads) > 0:
                    head = heads[0]
                    extruders = head.get("extruders", [{}])
                    if extruders and len(extruders) > 0:
                        extruder = extruders[0]
                        hotend = extruder.get("hotend", {})
                        statistics = hotend.get("statistics", {})
                        value = statistics.get("material_extruded", 0)
                        _LOGGER.debug("Hotend 1 material extruded: %s mm", value)
                    else:
                        _LOGGER.debug("No extruders found for hotend 1 material extruded")
                        value = 0
                else:
                    _LOGGER.debug("No heads found for hotend 1 material extruded")
                    value = 0
            except Exception as err:
                _LOGGER.warning("Error getting hotend 1 material extruded: %s", err)
                value = 0

        elif key == SENSOR_HOTEND_1_MATERIAL_REMAINING:
            try:
                heads = data.get("heads", [{}])
                if heads and len(heads) > 0:
                    head = heads[0]
                    extruders = head.get("extruders", [{}])
                    if extruders and len(extruders) > 0:
                        extruder = extruders[0]
                        active_material = extruder.get("active_material", {})
                        value = active_material.get("length_remaining", 0)
                        _LOGGER.debug("Hotend 1 material remaining: %s mm", value)
                    else:
                        _LOGGER.debug("No extruders found for hotend 1 material remaining")
                        value = 0
                else:
                    _LOGGER.debug("No heads found for hotend 1 material remaining")
                    value = 0
            except Exception as err:
                _LOGGER.warning("Error getting hotend 1 material remaining: %s", err)
                value = 0

        elif key == SENSOR_HOTEND_1_MATERIAL_TYPE:
            try:
                heads = data.get("heads", [{}])
                if heads and len(heads) > 0:
                    head = heads[0]
                    extruders = head.get("extruders", [{}])
                    if extruders and len(extruders) > 0:
                        extruder = extruders[0]
                        active_material = extruder.get("active_material", {})
                        value = active_material.get("GUID", "unknown")
                        _LOGGER.debug("Hotend 1 material type: %s", value)
                    else:
                        _LOGGER.debug("No extruders found for hotend 1 material type")
                        value = "unknown"
                else:
                    _LOGGER.debug("No heads found for hotend 1 material type")
                    value = "unknown"
            except Exception as err:
                _LOGGER.warning("Error getting hotend 1 material type: %s", err)
                value = "unknown"

        # Hotend 2 material sensors
        elif key == SENSOR_HOTEND_2_MATERIAL_EXTRUDED:
            try:
                heads = data.get("heads", [{}])
                if heads and len(heads) > 0:
                    head = heads[0]
                    extruders = head.get("extruders", [{}])
                    if extruders and len(extruders) > 1:
                        extruder = extruders[1]
                        hotend = extruder.get("hotend", {})
                        statistics = hotend.get("statistics", {})
                        value = statistics.get("material_extruded", 0)
                        _LOGGER.debug("Hotend 2 material extruded: %s mm", value)
                    else:
                        _LOGGER.debug("Fewer than 2 extruders found for hotend 2 material extruded")
                        value = 0
                else:
                    _LOGGER.debug("No heads found for hotend 2 material extruded")
                    value = 0
            except Exception as err:
                _LOGGER.warning("Error getting hotend 2 material extruded: %s", err)
                value = 0

        elif key == SENSOR_HOTEND_2_MATERIAL_REMAINING:
            try:
                heads = data.get("heads", [{}])
                if heads and len(heads) > 0:
                    head = heads[0]
                    extruders = head.get("extruders", [{}])
                    if extruders and len(extruders) > 1:
                        extruder = extruders[1]
                        active_material = extruder.get("active_material", {})
                        value = active_material.get("length_remaining", 0)
                        _LOGGER.debug("Hotend 2 material remaining: %s mm", value)
                    else:
                        _LOGGER.debug("Fewer than 2 extruders found for hotend 2 material remaining")
                        value = 0
                else:
                    _LOGGER.debug("No heads found for hotend 2 material remaining")
                    value = 0
            except Exception as err:
                _LOGGER.warning("Error getting hotend 2 material remaining: %s", err)
                value = 0

        elif key == SENSOR_HOTEND_2_MATERIAL_TYPE:
            try:
                heads = data.get("heads", [{}])
                if heads and len(heads) > 0:
                    head = heads[0]
                    extruders = head.get("extruders", [{}])
                    if extruders and len(extruders) > 1:
                        extruder = extruders[1]
                        active_material = extruder.get("active_material", {})
                        value = active_material.get("GUID", "unknown")
                        _LOGGER.debug("Hotend 2 material type: %s", value)
                    else:
                        _LOGGER.debug("Fewer than 2 extruders found for hotend 2 material type")
                        value = "unknown"
                else:
                    _LOGGER.debug("No heads found for hotend 2 material type")
                    value = "unknown"
            except Exception as err:
                _LOGGER.warning("Error getting hotend 2 material type: %s", err)
                value = "unknown"

        # Print job time sensors
        elif key == SENSOR_PRINT_JOB_TIME_TOTAL:
            try:
                value = data.get("time_total", 0)
                _LOGGER.debug("Print job total time: %s seconds", value)
            except Exception as err:
                _LOGGER.warning("Error getting print job total time: %s", err)
                value = 0

        elif key == SENSOR_PRINT_JOB_TIME_ELAPSED:
            try:
                value = data.get("time_elapsed", 0)
                _LOGGER.debug("Print job elapsed time: %s seconds", value)
            except Exception as err:
                _LOGGER.warning("Error getting print job elapsed time: %s", err)
                value = 0

        elif key == SENSOR_PRINT_JOB_TIME_REMAINING:
            try:
                total_time = data.get("time_total", 0)
                elapsed_time = data.get("time_elapsed", 0)

                if total_time > 0 and elapsed_time <= total_time:
                    value = total_time - elapsed_time
                else:
                    value = 0

                _LOGGER.debug("Print job remaining time: %s seconds", value)
            except Exception as err:
                _LOGGER.warning("Error calculating print job remaining time: %s", err)
                value = 0

        # Round float values to the specified decimal precision
        if isinstance(value, float):
            original_value = value
            value = round(value, self._decimal)
            _LOGGER.debug("Rounded float value from %s to %s (decimal precision: %d)", 
                         original_value, value, self._decimal)

        _LOGGER.info("Sensor %s final value: %s", self.entity_description.name, value)
        return value

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        sensor_name = self.entity_description.name
        _LOGGER.debug("Getting extra state attributes for sensor: %s", sensor_name)

        attrs = {}
        data = self.coordinator.data

        if data and "sampleTime" in data:
            sample_time = data["sampleTime"]
            attrs["Last Updated"] = sample_time
            _LOGGER.debug("Added 'Last Updated' attribute: %s", sample_time)
        else:
            _LOGGER.debug("No sample time available for attributes")

        _LOGGER.debug("Extra state attributes for %s: %s", sensor_name, attrs)
        return attrs
