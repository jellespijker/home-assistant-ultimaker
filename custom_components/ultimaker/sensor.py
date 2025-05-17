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
)

_LOGGER = logging.getLogger(__name__)

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
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    api_client = data["api_client"]

    # Determine which sensor descriptions to use based on API type
    descriptions = SENSOR_DESCRIPTIONS.copy()
    if entry.data.get(CONF_API_TYPE) == API_TYPE_CLOUD:
        descriptions.extend(CLOUD_SENSOR_DESCRIPTIONS)

    # Get decimal precision from options
    decimal = entry.options.get(CONF_DECIMAL, DEFAULT_DECIMAL)

    # Create sensors
    entities = []
    for description in descriptions:
        entities.append(
            UltimakerSensor(
                coordinator=coordinator,
                description=description,
                entry_id=entry.entry_id,
                decimal=decimal,
            )
        )

    async_add_entities(entities)


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
        super().__init__(coordinator)
        self.entity_description = description
        self._entry_id = entry_id
        self._decimal = decimal
        self._attr_unique_id = f"{entry_id}_{description.key}"

        # Set up device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Ultimaker Printer",
            manufacturer="Ultimaker",
            model="Ultimaker Printer",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        # For status sensor, always available if coordinator has data
        if self.entity_description.key == SENSOR_STATUS and self.coordinator.data:
            return True

        # For other sensors, check if we have valid data
        data = self.coordinator.data
        if not data or data.get("status") in ["not connected", "timeout", "error"]:
            return False

        # Check if the required data for each sensor type is present
        key = self.entity_description.key

        if key == SENSOR_STATE:
            return "state" in data

        elif key == SENSOR_PROGRESS:
            return "progress" in data

        elif key == SENSOR_BED_TEMPERATURE:
            bed = data.get("bed", {})
            temperature = bed.get("temperature", {})
            return "current" in temperature

        elif key == SENSOR_BED_TEMPERATURE_TARGET:
            bed = data.get("bed", {})
            temperature = bed.get("temperature", {})
            return "target" in temperature

        elif key == SENSOR_BED_TYPE:
            bed = data.get("bed", {})
            return "type" in bed

        elif key == SENSOR_HOTEND_1_TEMPERATURE:
            heads = data.get("heads", [{}])
            if not heads or len(heads) == 0:
                return False
            head = heads[0]
            extruders = head.get("extruders", [{}])
            if not extruders or len(extruders) == 0:
                return False
            extruder = extruders[0]
            hot_end = extruder.get("hotend", {})
            temperature = hot_end.get("temperature", {})
            return "current" in temperature

        elif key == SENSOR_HOTEND_1_TEMPERATURE_TARGET:
            heads = data.get("heads", [{}])
            if not heads or len(heads) == 0:
                return False
            head = heads[0]
            extruders = head.get("extruders", [{}])
            if not extruders or len(extruders) == 0:
                return False
            extruder = extruders[0]
            hot_end = extruder.get("hotend", {})
            temperature = hot_end.get("temperature", {})
            return "target" in temperature

        elif key == SENSOR_HOTEND_1_ID:
            heads = data.get("heads", [{}])
            if not heads or len(heads) == 0:
                return False
            head = heads[0]
            extruders = head.get("extruders", [{}])
            if not extruders or len(extruders) == 0:
                return False
            extruder = extruders[0]
            hot_end = extruder.get("hotend", {})
            return "id" in hot_end

        elif key == SENSOR_HOTEND_2_TEMPERATURE:
            heads = data.get("heads", [{}])
            if not heads or len(heads) == 0:
                return False
            head = heads[0]
            extruders = head.get("extruders", [{}])
            if len(extruders) < 2:
                return False
            extruder = extruders[1]
            hot_end = extruder.get("hotend", {})
            temperature = hot_end.get("temperature", {})
            return "current" in temperature

        elif key == SENSOR_HOTEND_2_TEMPERATURE_TARGET:
            heads = data.get("heads", [{}])
            if not heads or len(heads) == 0:
                return False
            head = heads[0]
            extruders = head.get("extruders", [{}])
            if len(extruders) < 2:
                return False
            extruder = extruders[1]
            hot_end = extruder.get("hotend", {})
            temperature = hot_end.get("temperature", {})
            return "target" in temperature

        elif key == SENSOR_HOTEND_2_ID:
            heads = data.get("heads", [{}])
            if not heads or len(heads) == 0:
                return False
            head = heads[0]
            extruders = head.get("extruders", [{}])
            if len(extruders) < 2:
                return False
            extruder = extruders[1]
            hot_end = extruder.get("hotend", {})
            return "id" in hot_end

        elif key == SENSOR_MATERIAL_REMAINING:
            heads = data.get("heads", [{}])
            if not heads or len(heads) == 0:
                return False
            head = heads[0]
            extruders = head.get("extruders", [{}])
            if not extruders or len(extruders) == 0:
                return False
            extruder = extruders[0]
            active_material = extruder.get("active_material", {})
            return "length_remaining" in active_material

        # For other sensors, assume they're available if we have data
        return True

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        data = self.coordinator.data
        if not data:
            return None

        value = None
        key = self.entity_description.key

        if key == SENSOR_STATUS:
            value = data.get("status", "not connected")

        elif key == SENSOR_STATE:
            value = data.get("state", None)
            if value:
                value = value.replace("_", " ")

        elif key == SENSOR_PROGRESS:
            value = data.get("progress", 0)
            if value:
                value *= 100

        elif key == SENSOR_BED_TEMPERATURE:
            bed = data.get("bed", {})
            temperature = bed.get("temperature", {})
            value = temperature.get("current", None)

        elif key == SENSOR_BED_TEMPERATURE_TARGET:
            bed = data.get("bed", {})
            temperature = bed.get("temperature", {})
            value = temperature.get("target", None)

        elif key == SENSOR_BED_TYPE:
            bed = data.get("bed", {})
            value = bed.get("type", None)

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

        elif key == SENSOR_HOTEND_1_ID:
            heads = data.get("heads", [{}])
            if heads and len(heads) > 0:
                head = heads[0]
                extruders = head.get("extruders", [{}])
                if extruders and len(extruders) > 0:
                    extruder = extruders[0]
                    hot_end = extruder.get("hotend", {})
                    value = hot_end.get("id", None)

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

        elif key == SENSOR_HOTEND_2_ID:
            heads = data.get("heads", [{}])
            if heads and len(heads) > 0:
                head = heads[0]
                extruders = head.get("extruders", [{}])
                if extruders and len(extruders) > 1:
                    extruder = extruders[1]
                    hot_end = extruder.get("hotend", {})
                    value = hot_end.get("id", None)

        # Cloud-specific sensors
        elif key == SENSOR_CLUSTER_STATUS:
            value = data.get("cluster_status", None)

        elif key == SENSOR_PRINTER_COUNT:
            value = data.get("printer_count", 0)

        elif key == SENSOR_MAINTENANCE_REQUIRED:
            # This is a placeholder - in a real implementation, you would
            # check if any maintenance tasks are pending
            value = "No"

        elif key == SENSOR_MATERIAL_REMAINING:
            # This is a placeholder - in a real implementation, you would
            # get the material remaining from the API
            value = 0

        # Round float values to the specified decimal precision
        if isinstance(value, float):
            value = round(value, self._decimal)

        return value

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        attrs = {}
        data = self.coordinator.data
        if data and "sampleTime" in data:
            attrs["Last Updated"] = data["sampleTime"]
        return attrs
