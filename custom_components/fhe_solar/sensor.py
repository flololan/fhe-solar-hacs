from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass, RestoreSensor
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_HOME_ID
from .coordinator import FheSolarCoordinator

PARALLEL_UPDATES = 0

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = FheSolarCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entities: list[SensorEntity] = []

    data = coordinator.data
    home = data.get("home", {})
    home_label = home.get("label") or f"Home {home.get('id')}"
    home_id = home.get("id") or entry.data[CONF_HOME_ID]
    instant = data.get("instantData") or {}
    inverters = data.get("fheMaster1000s") or []

    # Geräte/Entitäten pro Inverter
    for inv in inverters:
        serial = inv.get("serialNumber")
        if not serial:
            continue
        entities.extend(
            [
                FhePowerSensor(coordinator, serial, "outputPower", f"FHE {serial} Output Power", home_label),
                FhePowerSensor(coordinator, serial, "pv1Power", f"FHE {serial} PV1 Power", home_label),
                FhePowerSensor(coordinator, serial, "pv2Power", f"FHE {serial} PV2 Power", home_label),
                FheEnergyTodaySensor(coordinator, serial, f"FHE {serial} Today Yield", home_label),
            ]
        )

    # Haus-Gesamt
    entities.extend(
        [
            FheTotalPowerSensor(coordinator, f"FHE {home_label} Total Power"),
            FheTotalEnergyTodaySensor(coordinator, f"FHE {home_label} Today Yield"),
        ]
    )

    async_add_entities(entities)


class FheBase(CoordinatorEntity[FheSolarCoordinator], RestoreSensor, SensorEntity):
    _attr_has_entity_name = False

    def __init__(self, coordinator: FheSolarCoordinator):
        super().__init__(coordinator)

    @property
    def available(self) -> bool:
        # verfügbar auch nachts; Werte können None sein
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        # Überschrieben in Subklassen für Inverter vs. Haus
        return None


class FhePowerSensor(FheBase):
    def __init__(self, coordinator: FheSolarCoordinator, serial: str, key: str, name: str, home_label: str):
        super().__init__(coordinator)
        self._serial = serial
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.home_id}-{serial}-{key}"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "kW"

        self._home_label = home_label

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"inverter-{self._serial}")},
            "manufacturer": "FHE",
            "model": "FHE Master 1000",
            "name": f"FHE Inverter {self._serial}",
            "suggested_area": None,
            "via_device": (DOMAIN, f"home-{self.coordinator.home_id}"),
        }

    @property
    def native_value(self) -> Optional[float]:
        instant = (self.coordinator.data or {}).get("instantData") or {}
        inv = instant.get(self._serial) or {}
        val = inv.get(self._key)
        # API liefert Zahlen in kW; None nachts/kein Datensatz
        return float(val) if isinstance(val, (int, float)) else None


class FheEnergyTodaySensor(FheBase):
    def __init__(self, coordinator: FheSolarCoordinator, serial: str, name: str, home_label: str):
        super().__init__(coordinator)
        self._serial = serial
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.home_id}-{serial}-todayYield"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = "kWh"
        self._home_label = home_label

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"inverter-{self._serial}")},
            "manufacturer": "FHE",
            "model": "FHE Master 1000",
            "name": f"FHE Inverter {self._serial}",
            "via_device": (DOMAIN, f"home-{self.coordinator.home_id}"),
        }

    @property
    def native_value(self) -> Optional[float]:
        instant = (self.coordinator.data or {}).get("instantData") or {}
        inv = instant.get(self._serial) or {}
        val = inv.get("todayYield")
        return float(val) if isinstance(val, (int, float)) else None


class FheTotalPowerSensor(FheBase):
    def __init__(self, coordinator: FheSolarCoordinator, name: str):
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.home_id}-total-outputPower"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "kW"

    @property
    def device_info(self):
        home = (self.coordinator.data or {}).get("home") or {}
        home_label = home.get("label") or f"Home {home.get('id')}"
        return {
            "identifiers": {(DOMAIN, f"home-{self.coordinator.home_id}")},
            "manufacturer": "FHE",
            "name": f"FHE Solar {home_label}",
            "model": "FHE Home",
        }

    @property
    def native_value(self) -> Optional[float]:
        data = self.coordinator.data or {}
        instant = data.get("instantData") or {}
        if not instant:
            return 0.0  # nachts: 0 kW statt None, damit Frontend stabil bleibt
        total = 0.0
        for inv in instant.values():
            val = inv.get("outputPower")
            if isinstance(val, (int, float)):
                total += float(val)
        return total


class FheTotalEnergyTodaySensor(FheBase):
    # Dieser Sensor ist die Entität für das Energy Dashboard
    def __init__(self, coordinator: FheSolarCoordinator, name: str):
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.home_id}-total-todayYield"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = "kWh"

    @property
    def device_info(self):
        home = (self.coordinator.data or {}).get("home") or {}
        home_label = home.get("label") or f"Home {home.get('id')}"
        return {
            "identifiers": {(DOMAIN, f"home-{self.coordinator.home_id}")},
            "manufacturer": "FHE",
            "name": f"FHE Solar {home_label}",
            "model": "FHE Home",
        }

    @property
    def native_value(self) -> Optional[float]:
        data = self.coordinator.data or {}
        instant = data.get("instantData") or {}
        if not instant:
            return 0.0  # nachts nach Reset: 0 kWh
        total = 0.0
        for inv in instant.values():
            val = inv.get("todayYield")
            if isinstance(val, (int, float)):
                total += float(val)
        return total