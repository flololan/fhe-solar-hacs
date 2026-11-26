"""Data update coordinator for FHE Solar."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import FheSolarApi, FheSolarApiError, FheSolarAuthError, FheSolarConnectionError
from .const import (
    CONF_EMAIL,
    CONF_HOME_ID,
    CONF_PASSWORD,
    CONF_TOKEN,
    DEFAULT_SCAN_INTERVAL_ACTIVE,
    DEFAULT_SCAN_INTERVAL_IDLE,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

type FheSolarConfigEntry = ConfigEntry[FheSolarCoordinator]


class FheSolarCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch the home data (incl. instantData of all inverters) from the FHE API."""

    config_entry: FheSolarConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: FheSolarConfigEntry) -> None:
        session = aiohttp_client.async_get_clientsession(hass)
        self.api = FheSolarApi(session)
        self.api.set_token(config_entry.data[CONF_TOKEN])
        self.home_id = int(config_entry.data[CONF_HOME_ID])

        self._empty_count = 0
        # Highest todayYield seen per inverter serial for the current local day.
        # Observed 2026-11-25 (HA history): inverters drop out of instantData in
        # the evening (16:34-16:37) and one inverter reported todayYield 0.0 at
        # 16:40 after 0.5 earlier that day. Energy produced today cannot
        # decrease within the day, so the per-day maximum is kept.
        self.today_yield: dict[str, float] = {}
        self._today_yield_date: date | None = None
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
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

    def _has_instant_data(self, data: dict[str, Any]) -> bool:
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

    def _reset_today_yield_if_new_day(self) -> None:
        today = dt_util.now().date()
        if today != self._today_yield_date:
            self._today_yield_date = today
            self.today_yield = {}

    def seed_today_yield(self, serial: str, value: float) -> None:
        """Seed a per-inverter value (used by RestoreSensor after a restart)."""
        self._reset_today_yield_if_new_day()
        self.today_yield[serial] = max(self.today_yield.get(serial, 0.0), float(value))

    def _update_today_yield(self, data: dict[str, Any]) -> None:
        self._reset_today_yield_if_new_day()
        instant = data.get("instantData") or {}
        for serial, inv in instant.items():
            if not isinstance(inv, dict):
                continue
            val = inv.get("todayYield")
            if isinstance(val, (int, float)):
                self.today_yield[serial] = max(self.today_yield.get(serial, 0.0), float(val))

    def _today_yield_is_current(self) -> bool:
        return self._today_yield_date == dt_util.now().date()

    def get_today_yield(self, serial: str) -> float | None:
        """Held value of one inverter for today, None if nothing was seen today."""
        if not self._today_yield_is_current():
            return None
        return self.today_yield.get(serial)

    @property
    def today_yield_total(self) -> float:
        """Sum of the held per-inverter values (0.0 if nothing was seen today)."""
        if not self._today_yield_is_current():
            return 0.0
        return float(sum(self.today_yield.values()))

    async def _async_refresh_token(self) -> None:
        """Sign in again with the stored credentials and persist the new token.

        The API answers 401 {"message":"Failed to authenticate token"} for a
        rejected token (own test, see RESULTS.md). Email and password are already
        stored in the config entry, so a new token can be obtained without user
        interaction. Only if that sign-in is rejected as well, reauthentication
        is started by raising ConfigEntryAuthFailed (see _async_update_data).
        """
        entry = self.config_entry
        data = await self.api.sign_in(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
        self.hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_TOKEN: data["token"]}
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            try:
                data = await self.api.get_home(self.home_id)
            except FheSolarAuthError:
                _LOGGER.debug("FHE token rejected, signing in again")
                await self._async_refresh_token()
                data = await self.api.get_home(self.home_id)
        except FheSolarAuthError as err:
            # Credentials no longer work -> HA starts the reauth flow.
            raise ConfigEntryAuthFailed from err
        except FheSolarConnectionError as err:
            raise UpdateFailed(f"Cannot reach FHE API: {err}") from err
        except FheSolarApiError as err:
            raise UpdateFailed(str(err)) from err

        has_data = self._has_instant_data(data)
        self._adjust_interval(has_data)
        self._update_today_yield(data)
        return data
