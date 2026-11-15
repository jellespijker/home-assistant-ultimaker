"""Client for the UltiMaker Digital Factory API.

This package must not import Home Assistant, so it can be tested alone and
extracted into its own distribution later.
"""

from .client import DigitalFactoryClient
from .errors import (
    ApiError,
    ApiUnavailable,
    AuthenticationError,
    DigitalFactoryError,
    InsufficientPlan,
    PermissionDenied,
    RateLimited,
)
from .models import AirManager, CloudPrinter, Extruder, Fault, MaterialSlot, PrintJob, PrinterStatus

__all__ = [
    "AirManager",
    "ApiError",
    "ApiUnavailable",
    "AuthenticationError",
    "CloudPrinter",
    "DigitalFactoryClient",
    "DigitalFactoryError",
    "Extruder",
    "Fault",
    "InsufficientPlan",
    "MaterialSlot",
    "PermissionDenied",
    "PrintJob",
    "PrinterStatus",
    "RateLimited",
]
