"""Config flow for FHE Solar."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .api import FheSolarApi, FheSolarAuthError, FheSolarConnectionError
from .const import CONF_HOME_ID, CONF_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _try_sign_in(
    hass: HomeAssistant, email: str, password: str
) -> tuple[dict[str, Any] | None, str | None]:
    """Sign in and map exceptions to config-flow error keys."""
    api = FheSolarApi(aiohttp_client.async_get_clientsession(hass))
    try:
        return await api.sign_in(email, password), None
    except FheSolarAuthError:
        return None, "invalid_auth"
    except FheSolarConnectionError:
        return None, "cannot_connect"
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Unexpected error during FHE Solar sign-in")
        return None, "unknown"


class FheSolarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for FHE Solar."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data, error = await _try_sign_in(self.hass, user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
            if error:
                errors["base"] = error
            else:
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

        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Start reauthentication (triggered by ConfigEntryAuthFailed)."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the credentials again and update the existing entry."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            data, error = await _try_sign_in(self.hass, user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
            if error:
                errors["base"] = error
            else:
                # Make sure the user signed in to the same FHE home, not a different one.
                await self.async_set_unique_id(str(data["user"]["homeId"]))
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_TOKEN: data["token"],
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL, default=reauth_entry.data.get(CONF_EMAIL)): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(step_id="reauth_confirm", data_schema=schema, errors=errors)
