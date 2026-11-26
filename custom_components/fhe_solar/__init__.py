"""The FHE Solar integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import FheSolarConfigEntry, FheSolarCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: FheSolarConfigEntry) -> bool:
    """Set up FHE Solar from a config entry.

    The coordinator is created here and the first refresh is done before the
    platforms are set up, as described in
    https://developers.home-assistant.io/docs/integration_fetching_data/
    ("Do the first refresh during setup").
    """
    coordinator = FheSolarCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FheSolarConfigEntry) -> bool:
    """Unload a config entry. runtime_data is cleaned up by Home Assistant."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
