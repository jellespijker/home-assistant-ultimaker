"""Entities of printers reached through a cloud connection."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .cloud_coordinator import CloudCoordinator, CloudPrinterData
from .const import CONF_CONNECTION, CONNECTION_CLOUD, COORDINATOR, DOMAIN
from .digital_factory import PrintJob


def _job_summary(job: PrintJob) -> dict[str, Any]:
    return {"name": job.name, "status": job.status, "owner": job.owner, "progress": job.progress}


def _extruder(data: CloudPrinterData, index: int):
    return next((e for e in data.printer.extruders if e.index == index), None)


def _slot(data: CloudPrinterData, index: int):
    return next((s for s in data.printer.material_slots if s.index == index), None)


def _last_job(data: CloudPrinterData) -> PrintJob | None:
    return data.status.recently_completed[0] if data.status and data.status.recently_completed else None


@dataclass(frozen=True, kw_only=True)
class CloudSensorDescription(SensorEntityDescription):
    value_fn: Callable[[CloudPrinterData], Any]
    attributes_fn: Callable[[CloudPrinterData], dict[str, Any]] | None = None
    overlaps_lan: bool = False
    """True when a LAN connection reports the same thing, live."""


@dataclass(frozen=True, kw_only=True)
class CloudBinarySensorDescription(BinarySensorEntityDescription):
    value_fn: Callable[[CloudPrinterData], bool | None]


PRINTER_SENSORS: tuple[CloudSensorDescription, ...] = (
    CloudSensorDescription(
        key="status", name="Status", icon="mdi:printer-3d",
        value_fn=lambda d: d.printer.status,
    ),
    CloudSensorDescription(
        key="queue_length", name="Print queue", icon="mdi:tray-full",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d.status.queue) if d.status else d.printer.queue_length,
        attributes_fn=lambda d: {"jobs": [_job_summary(j) for j in d.status.queue]} if d.status else {},
    ),
    CloudSensorDescription(
        key="last_job_result", name="Last print job result", icon="mdi:flag-checkered",
        value_fn=lambda d: job.status if (job := _last_job(d)) else None,
        attributes_fn=lambda d: {"name": job.name, "owner": job.owner} if (job := _last_job(d)) else {},
    ),
    CloudSensorDescription(
        key="faults", name="Active faults", icon="mdi:alert-circle-outline",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d.printer.faults),
        attributes_fn=lambda d: {
            "faults": [
                {"code": f.code, "severity": f.severity, "message": f.message, "since": f.timestamp}
                for f in d.printer.faults
            ]
        },
    ),
    CloudSensorDescription(
        key="firmware_update_status", name="Firmware update status", icon="mdi:cloud-download",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.printer.firmware_update_status,
        attributes_fn=lambda d: {"installed": d.printer.firmware_version, "latest": d.printer.latest_firmware},
    ),
    CloudSensorDescription(
        key="job_name", name="Print job", icon="mdi:file-cad", overlaps_lan=True,
        value_fn=lambda d: d.printer.current_job.name if d.printer.current_job else None,
    ),
    CloudSensorDescription(
        key="job_progress", name="Print job progress", icon="mdi:progress-clock", overlaps_lan=True,
        native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.printer.current_job.progress if d.printer.current_job else None,
    ),
    CloudSensorDescription(
        key="job_time_remaining", name="Print job time remaining", overlaps_lan=True,
        device_class=SensorDeviceClass.DURATION, native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda d: d.printer.current_job.time_remaining if d.printer.current_job else None,
    ),
    CloudSensorDescription(
        key="build_plate_temperature", name="Build plate temperature", overlaps_lan=True,
        device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.printer.build_plate_temperature,
    ),
)

AIR_MANAGER_SENSOR = CloudSensorDescription(
    key="air_filter", name="Air manager filter", icon="mdi:air-filter",
    value_fn=lambda d: d.printer.air_manager.filter_status if d.printer.air_manager else None,
    attributes_fn=lambda d: {
        "status": d.printer.air_manager.status,
        "filter_age": d.printer.air_manager.filter_age,
        "filter_max_age": d.printer.air_manager.filter_max_age,
    }
    if d.printer.air_manager
    else {},
)


def _extruder_sensors(index: int) -> tuple[CloudSensorDescription, ...]:
    label = f"Extruder {index + 1}"
    return (
        CloudSensorDescription(
            key=f"extruder_{index}_material", name=f"{label} material", icon="mdi:printer-3d-nozzle",
            value_fn=lambda d: e.material if (e := _extruder(d, index)) else None,
        ),
        CloudSensorDescription(
            key=f"extruder_{index}_print_core", name=f"{label} print core", icon="mdi:printer-3d-nozzle-outline",
            overlaps_lan=True,
            value_fn=lambda d: e.print_core if (e := _extruder(d, index)) else None,
        ),
        CloudSensorDescription(
            key=f"extruder_{index}_temperature", name=f"{label} temperature", overlaps_lan=True,
            device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda d: e.temperature if (e := _extruder(d, index)) else None,
        ),
    )


def _slot_sensors(index: int) -> tuple[CloudSensorDescription, ...]:
    label = f"Material station slot {index + 1}"
    return (
        CloudSensorDescription(
            key=f"slot_{index}_material", name=f"{label} material", icon="mdi:database",
            value_fn=lambda d: s.material if (s := _slot(d, index)) else None,
        ),
        CloudSensorDescription(
            key=f"slot_{index}_remaining", name=f"{label} remaining", icon="mdi:database-arrow-down",
            native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda d: round(s.remaining * 100)
            if (s := _slot(d, index)) and s.remaining is not None
            else None,
        ),
    )


PRINTER_BINARY_SENSORS: tuple[CloudBinarySensorDescription, ...] = (
    CloudBinarySensorDescription(
        key="online", name="Digital Factory connection",
        device_class=BinarySensorDeviceClass.CONNECTIVITY, entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.printer.is_online,
    ),
    CloudBinarySensorDescription(
        key="maintenance_required", name="Maintenance required",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: d.printer.maintenance_required,
    ),
)


def lan_entry_for(hass: HomeAssistant, guid: str) -> ConfigEntry | None:
    """Return the LAN connection that reaches this printer, if one is configured."""
    return next(
        (
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.unique_id == guid
            and entry.data.get(CONF_CONNECTION) != CONNECTION_CLOUD
            and entry.disabled_by is None
        ),
        None,
    )


def cloud_coordinator_for(hass: HomeAssistant, guid: str) -> CloudCoordinator | None:
    """Return the loaded cloud connection that imports this printer, if any."""
    for loaded in hass.data.get(DOMAIN, {}).values():
        coordinator = loaded.get(COORDINATOR)
        if isinstance(coordinator, CloudCoordinator) and guid in (coordinator.data or {}):
            return coordinator
    return None


def _cloud_device_info(data: CloudPrinterData) -> DeviceInfo:
    printer = data.printer
    return DeviceInfo(
        identifiers={(DOMAIN, printer.guid)},
        name=printer.name,
        manufacturer="UltiMaker",
        model=printer.model,
        sw_version=printer.firmware_version,
        serial_number=printer.guid,
    )


class CloudPrinterEntity(CoordinatorEntity[CloudCoordinator]):
    """Base of every entity that reports Digital Factory data for one printer."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: CloudCoordinator, guid: str, description, device_info: DeviceInfo
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._guid = guid
        self._attr_unique_id = f"{guid}_cloud_{description.key}"
        self._attr_device_info = device_info

    @property
    def _data(self) -> CloudPrinterData | None:
        return self.coordinator.data.get(self._guid)

    @property
    def available(self) -> bool:
        """Unavailable when the printer has left the workspace or the poll failed."""
        return super().available and not self.coordinator.closed and self._data is not None


class CloudSensor(CloudPrinterEntity, SensorEntity):
    entity_description: CloudSensorDescription

    @property
    def native_value(self):
        return self.entity_description.value_fn(self._data) if self._data else None

    @property
    def extra_state_attributes(self):
        fn = self.entity_description.attributes_fn
        return fn(self._data) if fn and self._data else None


class CloudBinarySensor(CloudPrinterEntity, BinarySensorEntity):
    entity_description: CloudBinarySensorDescription

    @property
    def is_on(self):
        return self.entity_description.value_fn(self._data) if self._data else None


def _sensor_descriptions(data: CloudPrinterData, merged: bool) -> list[CloudSensorDescription]:
    descriptions = list(PRINTER_SENSORS)
    if data.printer.air_manager:
        descriptions.append(AIR_MANAGER_SENSOR)
    for extruder in data.printer.extruders:
        descriptions.extend(_extruder_sensors(extruder.index))
    for slot in data.printer.material_slots:
        descriptions.extend(_slot_sensors(slot.index))
    if merged:
        descriptions = [d for d in descriptions if not d.overlaps_lan]
    return descriptions


def _own_printers(hass: HomeAssistant, entry: ConfigEntry):
    """Yield (coordinator, guid, data) for the printers a cloud connection itself provides.

    A device belongs to one config entry, so a merged printer is owned by its
    LAN connection, which also carries the printer's Digital Factory entities
    (see merge.py); the cloud connection leaves such a printer alone.
    """
    coordinator: CloudCoordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    for guid, data in coordinator.data.items():
        if lan_entry_for(hass, guid) is None:
            coordinator.owned.add(guid)
            yield coordinator, guid, data


def cloud_sensors(hass: HomeAssistant, entry: ConfigEntry) -> list[CloudSensor]:
    """Return the sensors of the printers a cloud connection itself provides."""
    return [
        CloudSensor(coordinator, guid, description, _cloud_device_info(data))
        for coordinator, guid, data in _own_printers(hass, entry)
        for description in _sensor_descriptions(data, merged=False)
    ]


def cloud_binary_sensors(hass: HomeAssistant, entry: ConfigEntry) -> list[CloudBinarySensor]:
    """Return the binary sensors of the printers a cloud connection itself provides."""
    return [
        CloudBinarySensor(coordinator, guid, description, _cloud_device_info(data))
        for coordinator, guid, data in _own_printers(hass, entry)
        for description in PRINTER_BINARY_SENSORS
    ]


def merged_cloud_entities(
    coordinator: CloudCoordinator, guid: str, lan_device_info: DeviceInfo
) -> tuple[list[CloudSensor], list[CloudBinarySensor]]:
    """Return the Digital Factory entities a LAN connection carries for its merged printer."""
    sensors = [
        CloudSensor(coordinator, guid, description, lan_device_info)
        for description in _sensor_descriptions(coordinator.data[guid], merged=True)
    ]
    binary_sensors = [
        CloudBinarySensor(coordinator, guid, description, lan_device_info)
        for description in PRINTER_BINARY_SENSORS
    ]
    return sensors, binary_sensors
