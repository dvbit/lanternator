"""
Lanternator – Sensor Entities
REQ: Entità diagnostiche raggruppate sotto il device Lanternator.
- Desired state: stato desiderato corrente (on/off/unknown)
- Current lux: valore lux corrente dal sensore (specchio per il device)
"""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import LIGHT_LUX
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LanternatorCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """REQ: Setup delle entità sensor per questa istanza."""
    coordinator: LanternatorCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        LanternatorDesiredStateSensor(coordinator),
        LanternatorCurrentLuxSensor(coordinator),
    ])


class LanternatorDesiredStateSensor(CoordinatorEntity, SensorEntity):
    """
    REQ: Sensore diagnostico che mostra lo stato desiderato corrente.
    Valori: on, off, unknown.
    """

    def __init__(self, coordinator: LanternatorCoordinator) -> None:
        """Inizializza con riferimento al coordinator."""
        super().__init__(coordinator)
        # REQ (HA entity ID bug): _attr_name in inglese evita entity ID localizzati
        self._attr_name = "Desired state"
        self._attr_translation_key = "desired_state"
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_desired_state"
        )
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:lightbulb-auto"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> str:
        """REQ: Stato desiderato corrente dal coordinator."""
        return self.coordinator.desired_state


class LanternatorCurrentLuxSensor(CoordinatorEntity, SensorEntity):
    """
    REQ: Sensore diagnostico che specchia il valore lux corrente
    per visibilità nel device Lanternator.
    """

    def __init__(self, coordinator: LanternatorCoordinator) -> None:
        """Inizializza con riferimento al coordinator."""
        super().__init__(coordinator)
        # REQ (HA entity ID bug): _attr_name in inglese
        self._attr_name = "Current lux"
        self._attr_translation_key = "current_lux"
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_current_lux"
        )
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_class = SensorDeviceClass.ILLUMINANCE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = LIGHT_LUX
        self._attr_icon = "mdi:brightness-6"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> float | None:
        """REQ: Valore lux corrente dal coordinator."""
        return self.coordinator.current_lux
