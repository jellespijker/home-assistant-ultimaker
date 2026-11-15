"""The Digital Factory client, against canned API responses."""

import aiohttp
import pytest

from custom_components.ultimaker.digital_factory import (
    ApiUnavailable,
    AuthenticationError,
    DigitalFactoryClient,
    InsufficientPlan,
    PermissionDenied,
    RateLimited,
)
from custom_components.ultimaker.digital_factory.client import CONNECT_API

from .conftest import cluster

CLUSTERS = f"{CONNECT_API}/clusters?status=active"


@pytest.fixture
async def client(hass, aioclient_mock):
    async def token() -> str:
        return "umapi-test|eu"

    session = aioclient_mock.create_session(hass.loop)
    yield DigitalFactoryClient(session, token)
    await session.close()


async def test_list_printers_parses_telemetry(client, aioclient_mock) -> None:
    aioclient_mock.get(CLUSTERS, json={"data": [cluster()], "links": {}})

    [printer] = await client.list_printers()

    assert aioclient_mock.mock_calls[0][3]["Authorization"] == "Bearer umapi-test|eu"
    assert (printer.guid, printer.name, printer.model) == ("guid-1", "Workshop S8", "Ultimaker S8")
    assert (printer.status, printer.is_online, printer.queue_length) == ("printing", True, 2)
    assert printer.internal_ip == "192.0.2.10"
    assert printer.capabilities == {"queue", "identify"}
    assert printer.current_job.progress == 25.0
    assert [e.material for e in printer.extruders] == ["Ultimaker PLA White", None]
    assert [(s.empty, s.remaining) for s in printer.material_slots] == [(False, 0.4), (True, None)]
    assert printer.air_manager.filter_age == 8
    assert printer.faults[0].code == "HEATER_HALT"


async def test_list_printers_tolerates_sparse_printers(client, aioclient_mock) -> None:
    """Bridged and offline printers report almost nothing."""
    sparse = {"cluster_id": "c", "host_guid": "0123456789abcdef0123", "is_online": False}
    aioclient_mock.get(CLUSTERS, json={"data": [sparse]})

    [printer] = await client.list_printers()

    assert printer.name == "0123456789abcdef0123"
    assert printer.current_job is None and printer.air_manager is None
    assert printer.extruders == () and printer.material_slots == () and printer.faults == ()


async def test_list_printers_follows_pagination(client, aioclient_mock) -> None:
    page2 = f"{CONNECT_API}/clusters/next-page"  # the client follows whatever URL the API links to
    aioclient_mock.get(CLUSTERS, json={"data": [cluster("a")], "links": {"next": page2}})
    aioclient_mock.get(page2, json={"data": [cluster("b")], "links": {}})

    assert [p.guid for p in await client.list_printers()] == ["a", "b"]


async def test_get_printer_status_returns_queue_and_history(client, aioclient_mock) -> None:
    aioclient_mock.get(
        f"{CONNECT_API}/clusters/cluster-1/status",
        json={"data": {"is_online": True,
                       "print_jobs": [{"uuid": "j1", "status": "printing", "time_total": 100, "time_elapsed": 50},
                                      {"uuid": "j2", "status": "queued", "time_total": 0, "time_elapsed": 0}],
                       "recently_completed": [{"uuid": "j0", "status": "finished"}]}},
    )

    status = await client.get_printer_status("cluster-1")

    assert [(j.uuid, j.progress) for j in status.queue] == [("j1", 50.0), ("j2", None)]
    assert status.recently_completed[0].status == "finished"


def _error(code: str, status: int, **meta) -> dict:
    return {"errors": [{"code": code, "http_status": str(status), "title": "nope", "meta": meta}]}


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (401, _error("noBearerToken", 401), AuthenticationError),
        (403, _error("invalidToken", 403), AuthenticationError),
        # What the live API answers for an unknown or revoked API token.
        (502, _error("apiResponseError", 502, service="Account", response_code=404), AuthenticationError),
        (403, _error("forbidden", 403), PermissionDenied),
        (402, _error("insufficientSubscriptionPlan", 402), InsufficientPlan),
        (429, _error("tooManyRequests", 429), RateLimited),
        (502, _error("apiResponseError", 502, service="Connect", response_code=500), ApiUnavailable),
        (503, {}, ApiUnavailable),
    ],
)
async def test_errors_are_classified(client, aioclient_mock, status, body, expected) -> None:
    aioclient_mock.get(CLUSTERS, status=status, json=body)

    with pytest.raises(expected):
        await client.list_printers()


async def test_network_failure_is_temporary(client, aioclient_mock) -> None:
    aioclient_mock.get(CLUSTERS, exc=aiohttp.ClientConnectionError("down"))

    with pytest.raises(ApiUnavailable):
        await client.list_printers()


async def test_rate_limit_reports_retry_after(client, aioclient_mock) -> None:
    aioclient_mock.get(CLUSTERS, status=429, json={}, headers={"Retry-After": "30"})

    with pytest.raises(RateLimited) as err:
        await client.list_printers()
    assert err.value.retry_after == 30
