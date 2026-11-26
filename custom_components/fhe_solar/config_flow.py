from __future__ import annotations

from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN, CONF_HOME_ID, CONF_TOKEN
from .api import FheSolarApi

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors = {}
        if user_input is not None:
            session = aiohttp_client.async_get_clientsession(self.hass)
            api = FheSolarApi(session)
            try:
                data = await api.sign_in(user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
                token = data["token"]
                home_id = data["user"]["homeId"]
                await self.async_set_unique_id(str(home_id))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"FHE Solar ({home_id})",
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_TOKEN: token,
                        CONF_HOME_ID: home_id,
                    },
                )
            except Exception:
                errors["base"] = "auth"

        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors = {}
        if user_input is not None:
            session = aiohttp_client.async_get_clientsession(self.hass)
            api = FheSolarApi(session)
            try:
                data = await api.sign_in(user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
                token = data["token"]
                updates = {CONF_EMAIL: user_input[CONF_EMAIL], CONF_PASSWORD: user_input[CONF_PASSWORD], CONF_TOKEN: token}
                self.hass.config_entries.async_update_entry(self._reauth_entry, data={**self._reauth_entry.data, **updates})
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            except Exception:
                errors["base"] = "auth"

        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL, default=self._reauth_entry.data.get(CONF_EMAIL)): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(step_id="reauth_confirm", data_schema=schema, errors=errors)