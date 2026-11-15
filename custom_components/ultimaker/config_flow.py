from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
import voluptuous as vol

from .cloud_coordinator import cloud_client
from .const import (
    API_TOKEN_URL,
    CONF_API_TOKEN,
    CONF_CONNECTION,
    CONF_PRINTERS,
    CONNECTION_CLOUD,
    DOMAIN,
    UPGRADE_URL,
)
from .digital_factory import AuthenticationError, CloudPrinter, DigitalFactoryError

_LOGGER = logging.getLogger(__name__)

_SCAN_INTERVAL_SELECTOR = selector.NumberSelector({"min": 5, "max": 300, "step": 5, "mode": "box"})
_TOKEN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_TOKEN): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        )
    }
)
_TOKEN_PLACEHOLDERS = {"api_token_url": API_TOKEN_URL, "upgrade_url": UPGRADE_URL}


def _printers_schema(printers: list[CloudPrinter], selected: list[str]) -> vol.Schema:
    """Return the import list: every printer of the workspace, to tick or untick."""
    options = [
        selector.SelectOptionDict(
            value=p.guid,
            label=f"{p.name} ({p.model or 'unknown model'}{'' if p.is_online else ', offline'})",
        )
        for p in sorted(printers, key=lambda p: p.name.lower())
    ]
    # Keep printers that were imported but have since left the workspace selectable,
    # so saving the form does not silently drop them.
    known = {p.guid for p in printers}
    options += [selector.SelectOptionDict(value=g, label=g) for g in selected if g not in known]
    return vol.Schema(
        {
            vol.Required(CONF_PRINTERS, default=selected): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options, multiple=True, mode=selector.SelectSelectorMode.LIST
                )
            )
        }
    )


class UltimakerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Add a LAN connection (one printer) or a cloud connection (a Digital Factory workspace)."""

    VERSION = 1

    def __init__(self) -> None:
        self._api_token: str | None = None
        self._printers: list[CloudPrinter] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Ask which kind of connection to add."""
        return self.async_show_menu(step_id="user", menu_options=["lan", "cloud"])

    async def async_step_lan(self, user_input: dict[str, Any] | None = None):
        """Add one printer by its address on the local network."""
        if user_input is not None:
            data = {
                "name": user_input["name"],
                "ip": user_input["ip"],
                "scan_interval": user_input.get("scan_interval", 10),
            }
            return self.async_create_entry(title=data["name"], data=data)

        return self.async_show_form(
            step_id="lan",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): selector.TextSelector(),
                    vol.Required("ip"): selector.TextSelector(),
                    vol.Optional("scan_interval", default=10): _SCAN_INTERVAL_SELECTOR,
                }
            ),
        )

    async def _async_fetch_printers(self, api_token: str) -> tuple[list[CloudPrinter], str | None]:
        """Return the workspace's printers, or the error key to show."""
        # An API token looks like "umapi-<id>|<zone>". Selecting it by double-click
        # stops at the "|", and the API rejects the remainder like any wrong token.
        if not api_token.startswith("umapi-") or "|" not in api_token:
            _LOGGER.warning(
                "The pasted API token is incomplete (%d characters, starts with 'umapi-': %s, has '|': %s)",
                len(api_token),
                api_token.startswith("umapi-"),
                "|" in api_token,
            )
            return [], "incomplete_token"
        try:
            return await cloud_client(self.hass, api_token).list_printers(), None
        except AuthenticationError as err:
            _LOGGER.warning("Digital Factory rejected the API token: %s", err)
            return [], "invalid_auth"
        except DigitalFactoryError as err:
            _LOGGER.warning("Cannot reach Digital Factory: %s", err)
            return [], "cannot_connect"

    async def async_step_cloud(self, user_input: dict[str, Any] | None = None):
        """Sign in to Digital Factory with an API token."""
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input[CONF_API_TOKEN].strip()
            printers, error = await self._async_fetch_printers(token)
            if error:
                errors["base"] = error
            elif not printers:
                errors["base"] = "no_printers"
            else:
                await self.async_set_unique_id(f"cloud_{printers[0].workspace_id}")
                self._abort_if_unique_id_configured()
                self._api_token, self._printers = token, printers
                return await self.async_step_printers()

        return self.async_show_form(
            step_id="cloud",
            data_schema=_TOKEN_SCHEMA,
            errors=errors,
            description_placeholders=_TOKEN_PLACEHOLDERS,
        )

    async def async_step_printers(self, user_input: dict[str, Any] | None = None):
        """Choose which printers of the workspace to import."""
        if user_input is not None:
            return self.async_create_entry(
                title="Digital Factory",
                data={CONF_CONNECTION: CONNECTION_CLOUD, CONF_API_TOKEN: self._api_token},
                options={CONF_PRINTERS: user_input[CONF_PRINTERS]},
            )

        # Pre-tick the printers that already have a LAN connection.
        lan_guids = {e.unique_id for e in self._async_current_entries()}
        preselected = [p.guid for p in self._printers if p.guid in lan_guids]
        return self.async_show_form(
            step_id="printers",
            data_schema=_printers_schema(self._printers, preselected),
            description_placeholders={"count": str(len(self._printers))},
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]):
        """Digital Factory rejected the stored API token."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input[CONF_API_TOKEN].strip()
            printers, error = await self._async_fetch_printers(token)
            if error:
                errors["base"] = error
            elif not printers:
                errors["base"] = "no_printers"
            else:
                # Only the same workspace may replace the credential, so the printers
                # behind existing entities cannot be swapped by a different sign-in.
                await self.async_set_unique_id(f"cloud_{printers[0].workspace_id}")
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates={CONF_API_TOKEN: token}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_TOKEN_SCHEMA,
            errors=errors,
            description_placeholders=_TOKEN_PLACEHOLDERS,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return UltimakerOptionsFlowHandler()


class UltimakerOptionsFlowHandler(config_entries.OptionsFlow):
    """Change the import list of a cloud connection, or the scan interval of a LAN connection."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if self.config_entry.data.get(CONF_CONNECTION) == CONNECTION_CLOUD:
            return await self.async_step_printers()
        return await self.async_step_lan()

    async def async_step_lan(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="lan",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "scan_interval", default=self.config_entry.data.get("scan_interval", 10)
                    ): _SCAN_INTERVAL_SELECTOR
                }
            ),
        )

    async def async_step_printers(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data={CONF_PRINTERS: user_input[CONF_PRINTERS]})

        try:
            printers = await cloud_client(
                self.hass, self.config_entry.data[CONF_API_TOKEN]
            ).list_printers()
        except DigitalFactoryError as err:
            _LOGGER.warning("Cannot list Digital Factory printers: %s", err)
            return self.async_abort(reason="cannot_connect")

        return self.async_show_form(
            step_id="printers",
            data_schema=_printers_schema(printers, list(self.config_entry.options.get(CONF_PRINTERS, []))),
            description_placeholders={"count": str(len(printers))},
        )
