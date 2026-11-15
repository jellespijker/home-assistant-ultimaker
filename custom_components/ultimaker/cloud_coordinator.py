"""Polling of one cloud connection: a Digital Factory workspace."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CLOUD_SCAN_INTERVAL_SECONDS, CONF_API_TOKEN, CONF_PRINTERS, DOMAIN
from .digital_factory import (
    AuthenticationError,
    CloudPrinter,
    DigitalFactoryClient,
    DigitalFactoryError,
    PrinterStatus,
    RateLimited,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class CloudPrinterData:
    """What one poll knows about an imported printer."""

    printer: CloudPrinter
    status: PrinterStatus | None
    """Queue and recent history; None when the printer is offline or the call failed."""


def cloud_client(hass: HomeAssistant, api_token: str) -> DigitalFactoryClient:
    """Return a Digital Factory client that signs in with an API token."""

    async def token() -> str:
        return api_token

    return DigitalFactoryClient(async_get_clientsession(hass), token)


class CloudCoordinator(DataUpdateCoordinator[dict[str, CloudPrinterData]]):
    """Fetches the imported printers of a workspace; data is keyed by printer GUID."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} cloud",
            update_interval=timedelta(seconds=CLOUD_SCAN_INTERVAL_SECONDS),
        )
        self.client = cloud_client(hass, entry.data[CONF_API_TOKEN])
        self.imported: frozenset[str] = frozenset(entry.options.get(CONF_PRINTERS, ()))
        self.closed = False
        self.owned: set[str] = set()
        """GUIDs of the printers whose entities this connection itself provides."""

    @callback
    def async_close(self) -> None:
        """Mark the connection as gone, so entities still holding it turn unavailable."""
        self.closed = True
        self.async_update_listeners()

    async def _async_update_data(self) -> dict[str, CloudPrinterData]:
        try:
            printers = [p for p in await self.client.list_printers() if p.guid in self.imported]
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except RateLimited as err:
            raise UpdateFailed(str(err), retry_after=err.retry_after) from err
        except DigitalFactoryError as err:
            raise UpdateFailed(str(err)) from err

        statuses = await asyncio.gather(*(self._status(p) for p in printers))
        return {p.guid: CloudPrinterData(p, s) for p, s in zip(printers, statuses)}

    async def _status(self, printer: CloudPrinter) -> PrinterStatus | None:
        if not printer.is_online:
            return None
        try:
            return await self.client.get_printer_status(printer.cluster_id)
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except DigitalFactoryError as err:
            _LOGGER.debug("No queue for %s this poll: %s", printer.name, err)
            return None
