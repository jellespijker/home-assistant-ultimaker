"""Config flow for Ultimaker integration."""
import logging
import voluptuous as vol
from typing import Any, Dict, List, Optional

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import DOMAIN
from .const import (
    CONF_API_TYPE, 
    API_TYPE_LOCAL, 
    API_TYPE_CLOUD, 
    CONF_HOST, 
    CONF_CLUSTER_ID,
    CONF_ORGANIZATION_ID
)
from .api_client import UltimakerCloudApiClient

_LOGGER = logging.getLogger(__name__)

class UltimakerOAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Ultimaker OAuth2 authentication."""

    DOMAIN = DOMAIN
    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        super().__init__()
        self._workspaces = []
        self._organization_id = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return _LOGGER

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_API_TYPE, default=API_TYPE_LOCAL): vol.In(
                            [API_TYPE_LOCAL, API_TYPE_CLOUD]
                        ),
                    }
                ),
            )

        if user_input[CONF_API_TYPE] == API_TYPE_LOCAL:
            return await self.async_step_local()

        # For cloud API, we might need to select an organization
        self._organization_id = user_input.get(CONF_ORGANIZATION_ID)
        return await self.async_step_oauth()

    async def async_step_local(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle local API configuration."""
        if user_input is None:
            return self.async_show_form(
                step_id="local",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_HOST): str,
                    }
                ),
            )

        return self.async_create_entry(
            title=f"Ultimaker Printer ({user_input[CONF_HOST]})",
            data={
                CONF_API_TYPE: API_TYPE_LOCAL,
                CONF_HOST: user_input[CONF_HOST],
            },
        )

    async def async_step_pick_organization(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the step to pick an organization."""
        if not self._workspaces:
            return self.async_abort(reason="no_organizations")

        if user_input is None:
            workspace_names = {w["id"]: w["name"] for w in self._workspaces}
            return self.async_show_form(
                step_id="pick_organization",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_ORGANIZATION_ID): vol.In(workspace_names),
                    }
                ),
            )

        # Store the selected organization ID
        self._organization_id = user_input[CONF_ORGANIZATION_ID]

        # Re-authenticate with the selected organization
        return await self.async_step_oauth()

    async def async_oauth_create_entry(self, data: Dict[str, Any]) -> FlowResult:
        """Create an entry for OAuth2 authenticated config flow."""
        # If we have a token, try to get user info and check for multiple workspaces
        if "token" in data and not self._organization_id:
            session = async_get_clientsession(self.hass)
            api_client = UltimakerCloudApiClient(
                session=session,
                token=data["token"]["access_token"],
                token_expiry=None,  # Not needed for this check
            )

            try:
                # Get workspaces
                self._workspaces = await api_client.get_workspaces()

                # If multiple workspaces and no organization ID selected yet, show selection
                if len(self._workspaces) > 1:
                    return await self.async_step_pick_organization()
                elif len(self._workspaces) == 1:
                    # If only one workspace, use it
                    self._organization_id = self._workspaces[0]["id"]
            except Exception as err:
                _LOGGER.error("Error getting workspaces: %s", err)
                # Continue with flow even if we can't get workspaces

        # Add organization ID to data if available
        if self._organization_id:
            data[CONF_ORGANIZATION_ID] = self._organization_id

        # Get cluster ID if available
        cluster_id = data.get(CONF_CLUSTER_ID)
        title = "Ultimaker Cloud"
        if cluster_id:
            title = f"{title} ({cluster_id})"
        elif self._organization_id:
            # Try to find the organization name
            for workspace in self._workspaces:
                if workspace["id"] == self._organization_id:
                    title = f"{title} ({workspace['name']})"
                    break

        return self.async_create_entry(
            title=title,
            data={
                CONF_API_TYPE: API_TYPE_CLOUD,
                **data,
            },
        )

class UltimakerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ultimaker."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return UltimakerOptionsFlow(config_entry)

class UltimakerOptionsFlow(config_entries.OptionsFlow):
    """Handle options for the Ultimaker integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        api_type = self.config_entry.data.get(CONF_API_TYPE, API_TYPE_LOCAL)

        if api_type == API_TYPE_LOCAL:
            options_schema = vol.Schema(
                {
                    vol.Optional(
                        "scan_interval",
                        default=self.config_entry.options.get("scan_interval", 10),
                    ): vol.All(vol.Coerce(int), vol.Range(min=5, max=60)),
                    vol.Optional(
                        "decimal",
                        default=self.config_entry.options.get("decimal", 2),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=5)),
                }
            )
        else:  # API_TYPE_CLOUD
            options_schema = vol.Schema(
                {
                    vol.Optional(
                        "scan_interval",
                        default=self.config_entry.options.get("scan_interval", 30),
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
                    vol.Optional(
                        "decimal",
                        default=self.config_entry.options.get("decimal", 2),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=5)),
                    vol.Optional(
                        CONF_CLUSTER_ID,
                        default=self.config_entry.options.get(CONF_CLUSTER_ID, ""),
                    ): str,
                }
            )

        return self.async_show_form(step_id="init", data_schema=options_schema)
