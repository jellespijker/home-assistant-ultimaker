from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
import voluptuous as vol
import logging
from typing import Any, Dict
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class UltimakerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ultimaker."""

    VERSION = 1

    def __init__(self) -> None:
        self.data: Dict[str, Any] = {}
        self._errors: Dict[str, str] = {}

    async def async_step_user(self, user_input: Dict[str, Any] | None = None):
        """Handle the initial step."""

        data_schema = vol.Schema({
            vol.Required("name"): selector.TextSelector(),
            vol.Required("ip"): selector.TextSelector(),
            vol.Optional("scan_interval", default=10): selector.NumberSelector(
                {
                    "min": 5,
                    "max": 300,
                    "step": 5,
                    "mode": "box"
                }
            ),
        })

        if user_input is not None:
            self.data = {
                "name": user_input["name"],
                "ip": user_input["ip"],
                "scan_interval": user_input.get("scan_interval", 10),
            }

            return self.async_create_entry(title=self.data["name"], data=self.data)

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=self._errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return UltimakerOptionsFlowHandler(config_entry)


class UltimakerOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Ultimaker."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input: Dict[str, Any] | None = None):
        """Manage the options for the custom component."""

        options_schema = vol.Schema({
            vol.Optional("scan_interval", default=self.config_entry.data.get("scan_interval", 10)): selector.NumberSelector(
                {
                    "min": 5,
                    "max": 300,
                    "step": 5,
                    "mode": "box"
                }
            )
        })

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema
        )