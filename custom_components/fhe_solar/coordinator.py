from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers import aiohttp_client
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

from .api import FheSolarApi
from .const import (
    DOMAIN,
    CONF_HOME_ID,
    CONF_TOKEN,
    CONF_EMAIL,
    CONF_PASSWORD,
    DEFAULT_SCAN_INTERVAL_ACTIVE,
    DEFAULT_SCAN_INTERVAL_IDLE,
    MIN_SCAN_INTERVAL,
    MAX_SCAN_INTERVAL,
)

class FheSolarCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, config_entry):
        self.hass = hass
        self.entry = config_entry
        session = aiohttp_client.async_get_clientsession(hass)
        self.api = FheSolarApi(session)
        self.api.set_token(config_entry.data[CONF_TOKEN])
        self.home_id = int(config_entry.data[CONF_HOME_ID])

        self._empty_count = 0
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{self.home_id}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL_ACTIVE),
        )

    def _is_daytime(self) -> bool:
        sun = self.hass.states.get("sun.sun")
        if not sun or not isinstance(sun.attributes.get("elevation"), (int, float)):
            # Fallback: treat as daytime during 7–19 local if sun integration absent
            hour = dt_util.now().hour
            return 7 <= hour <= 19
        return sun.attributes["elevation"] > 0

    def _has_instant_data(self, data: Dict[str, Any]) -> bool:
        instant = data.get("instantData") or {}
        return bool(instant)

    def _adjust_interval(self, has_data: bool) -> None:
        # Backoff if kein instantData mehrfach hintereinander (nachts/unproduktiv)
        if has_data:
            self._empty_count = 0
            seconds = max(MIN_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_ACTIVE)
        else:
            self._empty_count += 1
            # Exponentieller Backoff bis MAX
            seconds = min(MAX_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_IDLE * (2 ** max(0, self._empty_count - 1)))
        # Wenn Sonne deutlich unter dem Horizont: mindestens Idle-Interval
        if not self._is_daytime():
            seconds = max(seconds, DEFAULT_SCAN_INTERVAL_IDLE)
        self.update_interval = timedelta(seconds=seconds)

    async def _async_update_data(self) -> Dict[str, Any]:
        try:
            data = await self.api.get_home(self.home_id)
        except PermissionError as e:
            # Reauth anstoßen
            self.hass.async_create_task(self._start_reauth())
            raise UpdateFailed("Unauthorized") from e
        except Exception as e:
            raise UpdateFailed(str(e)) from e

        has_data = self._has_instant_data(data)
        self._adjust_interval(has_data)
        return data

    async def _start_reauth(self) -> None:
        await self.hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth", "entry_id": self.entry.entry_id},
            data=self.entry.data,
        )