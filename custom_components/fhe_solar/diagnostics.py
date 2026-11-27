"""Diagnostics support for FHE Solar."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_EMAIL, CONF_HOME_ID, CONF_PASSWORD, CONF_TOKEN
from .coordinator import FheSolarConfigEntry

# Keys observed in the API responses (own structure test 2026-11-26, RESULTS.md):
# - credentials/token: entry data, `user.password`, `users[].password`, `token`
# - personal data: `firstName`, `lastName`, `email`, `phone`
# - location data: `address`, `city`, `postalCode`
# - `label` is the home name (contains the owner's name in the observed data)
# - `serialNumber` of the inverters (listed as example key in the HA diagnostics docs)
# - the FHE home id ties a file to one account: `home_id` (entry data),
#   `homeId` (`user`/`users[]`), `id` (`home`, nested objects)
TO_REDACT = {
    CONF_EMAIL,
    CONF_HOME_ID,
    CONF_PASSWORD,
    CONF_TOKEN,
    "homeId",
    "id",
    "firstName",
    "lastName",
    "phone",
    "address",
    "city",
    "postalCode",
    "label",
    "serialNumber",
}


def _anonymize_serial_keys(mapping: dict[str, Any], serial_map: dict[str, str]) -> dict[str, Any]:
    """Replace inverter serial numbers used as dict keys (instantData, today_yield).

    async_redact_data only redacts values, not keys.
    """
    return {serial_map.get(key, key): value for key, value in mapping.items()}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: FheSolarConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    data: dict[str, Any] = dict(coordinator.data or {})

    # Stable pseudonyms for the inverter serials, in the order of fheMaster1000s.
    serial_map: dict[str, str] = {}
    for index, inverter in enumerate(data.get("fheMaster1000s") or [], start=1):
        serial = inverter.get("serialNumber") if isinstance(inverter, dict) else None
        if serial:
            serial_map[str(serial)] = f"inverter_{index}"
    for index, serial in enumerate(data.get("instantData") or {}, start=1):
        serial_map.setdefault(str(serial), f"inverter_unlisted_{index}")

    if isinstance(data.get("instantData"), dict):
        data["instantData"] = _anonymize_serial_keys(data["instantData"], serial_map)

    return {
        # entry.title is "FHE Solar (<home id>)" and is therefore not included.
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
        },
        "coordinator": {
            "update_interval_seconds": (
                coordinator.update_interval.total_seconds() if coordinator.update_interval else None
            ),
            "last_update_success": coordinator.last_update_success,
            "today_yield": _anonymize_serial_keys(dict(coordinator.today_yield), serial_map),
        },
        "data": async_redact_data(data, TO_REDACT),
    }
