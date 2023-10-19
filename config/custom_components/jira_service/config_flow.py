"""Config flow for JIRA integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN
from .jira_web_client import jira_web_client

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
    }
)


class JiraFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for JIRA."""

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            error, success = await self._async_try_connect(user_input)
            if error is not None:
                errors["base"] = error
            elif success is True:
                await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input.get(CONF_USERNAME)
                    + " : "
                    + user_input.get(CONF_HOST),
                    data={
                        CONF_API_KEY: user_input.get(CONF_API_KEY),
                        CONF_HOST: user_input.get(CONF_HOST),
                        CONF_USERNAME: user_input.get(CONF_USERNAME),
                    },
                )

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=CONFIG_SCHEMA,
            errors=errors,
        )

    async def _async_try_connect(
        self, user_input: str
    ) -> tuple[str, None] | tuple[None, dict[str, str]]:
        """Try connecting to JIRA."""
        aiohttp_client.async_get_clientsession(self.hass)
        client = jira_web_client(
            api_key=user_input[CONF_API_KEY],
            base_url=user_input[CONF_HOST],
            username=user_input[CONF_USERNAME],
        )

        try:
            success = await client.verify_connection()
        except Exception as ex:  # pylint:disable=broad-except
            _LOGGER.exception("Unexpected exception: %s", ex)
            return "unknown", None
        return None, success
