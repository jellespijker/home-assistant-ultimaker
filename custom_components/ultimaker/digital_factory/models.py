"""Typed views of Digital Factory API responses.

Parsing is lenient: printers of different generations omit different fields,
so a missing field becomes None (or an empty collection) instead of an error.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _material_name(material: dict[str, Any] | None) -> str | None:
    """Return a readable material name, or None for an empty slot."""
    if not material or material.get("material") in (None, "", "empty"):
        return None
    parts = [material.get("brand"), material.get("material"), material.get("color")]
    return " ".join(p for p in parts if p and p not in ("empty", "Generic")) or material["material"]


@dataclass(frozen=True)
class Extruder:
    index: int
    print_core: str | None
    material: str | None
    temperature: float | None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Extruder:
        return cls(
            index=data.get("extruder_index", 0),
            print_core=data.get("print_core_id") or None,
            material=_material_name(data.get("material")),
            temperature=data.get("temperature"),
        )


@dataclass(frozen=True)
class MaterialSlot:
    index: int
    extruder_index: int | None
    material: str | None
    empty: bool
    remaining: float | None
    """Fraction of the spool left, 0 to 1; None when the printer cannot tell."""

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> MaterialSlot:
        remaining = data.get("material_remaining")
        return cls(
            index=data.get("slot_index", 0),
            extruder_index=data.get("extruder_index"),
            material=_material_name(data.get("material")),
            empty=bool(data.get("material_empty", False)),
            remaining=remaining if remaining is not None and remaining >= 0 else None,
        )


@dataclass(frozen=True)
class AirManager:
    status: str | None
    filter_status: str | None
    filter_age: int | None
    filter_max_age: int | None

    @classmethod
    def from_json(cls, data: dict[str, Any] | None) -> AirManager | None:
        if not data or not data.get("supported"):
            return None
        return cls(
            status=data.get("status"),
            filter_status=data.get("filter_status"),
            filter_age=data.get("filter_age"),
            filter_max_age=data.get("filter_max_age"),
        )


@dataclass(frozen=True)
class Fault:
    code: str
    severity: str | None
    message: str | None
    timestamp: str | None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Fault:
        return cls(
            code=str(data.get("code", "unknown")),
            severity=data.get("severity"),
            message=data.get("message"),
            timestamp=data.get("timestamp"),
        )


@dataclass(frozen=True)
class PrintJob:
    uuid: str
    name: str | None
    status: str | None
    state: str | None
    owner: str | None
    started: bool
    time_total: int | None
    time_elapsed: int | None
    time_remaining: int | None
    created_at: str | None
    preview_url: str | None

    @property
    def progress(self) -> float | None:
        """Return progress as a percentage; the API has no progress field."""
        if not self.time_total or self.time_elapsed is None:
            return None
        return round(min(100.0, max(0.0, self.time_elapsed / self.time_total * 100)), 1)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> PrintJob:
        return cls(
            uuid=data["uuid"],
            name=data.get("name"),
            status=data.get("status"),
            state=data.get("state"),
            owner=data.get("owner"),
            started=bool(data.get("started", False)),
            time_total=data.get("time_total"),
            time_elapsed=data.get("time_elapsed"),
            time_remaining=data.get("time_remaining"),
            created_at=data.get("created_at"),
            preview_url=data.get("preview_url"),
        )


@dataclass(frozen=True)
class CloudPrinter:
    """One printer as Digital Factory lists it (the API calls this a cluster)."""

    cluster_id: str
    guid: str
    workspace_id: str | None
    name: str
    model: str | None
    is_online: bool
    status: str | None
    """What Digital Factory displays: idle, printing, offline, wait_cleanup, ..."""
    printer_uuid: str | None
    internal_ip: str | None
    host_name: str | None
    firmware_version: str | None
    latest_firmware: str | None
    firmware_update_status: str | None
    enabled: bool | None
    maintenance_required: bool | None
    queue_length: int | None
    current_job: PrintJob | None
    build_plate_temperature: float | None
    build_plate_type: str | None
    air_manager: AirManager | None
    capabilities: frozenset[str] = field(default_factory=frozenset)
    extruders: tuple[Extruder, ...] = ()
    material_slots: tuple[MaterialSlot, ...] = ()
    faults: tuple[Fault, ...] = ()

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> CloudPrinter:
        host = data.get("host_printer") or {}
        build_plate = host.get("build_plate") or {}
        station = host.get("material_station") or {}
        job = data.get("host_current_print_job")
        return cls(
            cluster_id=data["cluster_id"],
            guid=data["host_guid"],
            workspace_id=data.get("organization_id") or data.get("user_id"),
            name=data.get("friendly_name") or host.get("friendly_name") or data.get("host_name") or data["host_guid"],
            model=host.get("machine_variant") or data.get("printer_type"),
            is_online=bool(data.get("is_online", False)),
            status=data.get("display_status") or host.get("status"),
            printer_uuid=host.get("uuid") or None,
            internal_ip=data.get("host_internal_ip") or host.get("ip_address") or None,
            host_name=data.get("host_name"),
            firmware_version=host.get("firmware_version") or data.get("host_version"),
            latest_firmware=host.get("latest_available_firmware") or None,
            firmware_update_status=host.get("firmware_update_status"),
            enabled=host.get("enabled"),
            maintenance_required=host.get("maintenance_required"),
            queue_length=data.get("host_print_job_count"),
            current_job=PrintJob.from_json(job) if job and job.get("uuid") else None,
            build_plate_temperature=build_plate.get("temperature"),
            build_plate_type=build_plate.get("type"),
            air_manager=AirManager.from_json(host.get("air_manager")),
            capabilities=frozenset(data.get("capabilities") or ()),
            extruders=tuple(Extruder.from_json(e) for e in host.get("configuration") or ()),
            material_slots=tuple(
                MaterialSlot.from_json(s) for s in station.get("material_slots") or ()
            )
            if station.get("supported")
            else (),
            faults=tuple(Fault.from_json(f) for f in host.get("faults") or ()),
        )


@dataclass(frozen=True)
class PrinterStatus:
    """The print queue and recent history of one printer."""

    is_online: bool
    queue: tuple[PrintJob, ...]
    recently_completed: tuple[PrintJob, ...]

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> PrinterStatus:
        return cls(
            is_online=bool(data.get("is_online", False)),
            queue=tuple(PrintJob.from_json(j) for j in data.get("print_jobs") or ()),
            recently_completed=tuple(
                PrintJob.from_json(j) for j in data.get("recently_completed") or ()
            ),
        )
