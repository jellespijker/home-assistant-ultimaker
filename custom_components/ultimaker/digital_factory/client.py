"""HTTP client for the Digital Factory Connect API."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp

from .errors import (
    ApiError,
    ApiUnavailable,
    AuthenticationError,
    InsufficientPlan,
    PermissionDenied,
    RateLimited,
)
from .models import CloudPrinter, PrinterStatus

API_ROOT = "https://api.ultimaker.com"
CONNECT_API = f"{API_ROOT}/connect/v1"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)
_MAX_PAGES = 50

TokenProvider = Callable[[], Awaitable[str]]
"""Returns the bearer token to use: an API token, or a fresh OAuth access token."""


class DigitalFactoryClient:
    """Read access to the printers of one Digital Factory workspace."""

    def __init__(self, session: aiohttp.ClientSession, token_provider: TokenProvider) -> None:
        self._session = session
        self._token_provider = token_provider

    async def list_printers(self) -> list[CloudPrinter]:
        """Return every active printer in the workspace, with its current telemetry."""
        printers: list[CloudPrinter] = []
        url: str | None = f"{CONNECT_API}/clusters?status=active"
        for _ in range(_MAX_PAGES):
            body = await self._get(url)
            printers.extend(CloudPrinter.from_json(item) for item in body.get("data") or ())
            url = (body.get("links") or {}).get("next")
            if not url:
                return printers
        raise ApiError("Digital Factory returned more pages of printers than expected")

    async def get_printer_status(self, cluster_id: str) -> PrinterStatus:
        """Return the print queue and recent history of one printer."""
        body = await self._get(f"{CONNECT_API}/clusters/{cluster_id}/status")
        return PrinterStatus.from_json(body.get("data") or {})

    async def _get(self, url: str) -> dict[str, Any]:
        token = await self._token_provider()
        try:
            async with self._session.get(
                url,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                timeout=REQUEST_TIMEOUT,
            ) as response:
                if response.status == 200:
                    body = await response.json(content_type=None)
                    if not isinstance(body, dict):
                        raise ApiError(f"Unexpected response from Digital Factory for {url}")
                    return body
                _raise_for_error(response.status, response.headers, await _error_of(response))
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise ApiUnavailable(f"Cannot reach Digital Factory: {err}") from err
        except ValueError as err:
            raise ApiError(f"Digital Factory sent an unreadable response: {err}") from err
        raise AssertionError("unreachable")


async def _error_of(response: aiohttp.ClientResponse) -> dict[str, Any]:
    """Return the first error object of a failed response, or an empty dict."""
    try:
        body = await response.json(content_type=None)
        return (body.get("errors") or [{}])[0]
    except (ValueError, AttributeError, aiohttp.ClientError):
        return {}


def _raise_for_error(status: int, headers: Any, error: dict[str, Any]) -> None:
    code = error.get("code")
    meta = error.get("meta") or {}
    message = error.get("title") or f"Digital Factory answered HTTP {status}"

    if status == 401 or code in ("invalidToken", "noBearerToken"):
        raise AuthenticationError(message)
    # An unknown or revoked API token surfaces as a 502: the Connect API fails
    # to exchange it at the account service, which answers 404.
    if status == 502 and meta.get("service") == "Account" and meta.get("response_code") in (401, 403, 404):
        raise AuthenticationError("Digital Factory did not recognise the API token")
    if status == 402 or code == "insufficientSubscriptionPlan":
        raise InsufficientPlan(message)
    if status == 403:
        raise PermissionDenied(message)
    if status == 429:
        retry_after = headers.get("Retry-After")
        raise RateLimited(message, float(retry_after) if retry_after and retry_after.isdigit() else None)
    if status >= 500:
        raise ApiUnavailable(message)
    raise ApiError(message)
