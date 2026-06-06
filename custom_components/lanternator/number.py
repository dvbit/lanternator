"""
Lanternator – Number Entities
REQ: Entità number configurabili da UI, raggruppate sotto il device.
     Aggiornano il coordinator a runtime e persistono nella config entry.
- lux_threshold, debounce_seconds, polling_minutes
- brightness, color_temp, rgb_r, rgb_g, rgb_b
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import (
    NumberEntity,
    NumberDeviceClass,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import LIGHT_LUX, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_BRIGHTNESS,
    CONF_COLOR_TEMP,
    CONF_DEBOUNCE_SECONDS,
    CONF_LUX_THRESHOLD,
    CONF_POLLING_MINUTES,
    CONF_RGB_COLOR_B,
    CONF_RGB_COLOR_G,
    CONF_RGB_COLOR_R,
    DOMAIN,
)
from .coordinator import LanternatorCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class LanternatorNumberSpec:
    """Specifica per un'entità number Lanternator."""

    key: str                    # CONF_* key
    name: str                   # English name (REQ: _attr_name per entity ID)
    translation_key: str        # Translation key per display localizzato
    icon: str
    min_value: float
    max_value: float
    step: float
    mode: NumberMode
    unit: str | None
    entity_category: EntityCategory
    value_getter: str           # Nome property del coordinator


# REQ: Definizione di tutti i parametri configurabili
NUMBER_SPECS: list[LanternatorNumberSpec] = [
    LanternatorNumberSpec(
        key=CONF_LUX_THRESHOLD,
        name="Lux threshold",
        translation_key="lux_threshold",
        icon="mdi:brightness-5",
        min_value=1,
        max_value=1000,
        step=1,
        mode=NumberMode.BOX,
        unit=LIGHT_LUX,
        entity_category=EntityCategory.CONFIG,
        value_getter="threshold",
    ),
    LanternatorNumberSpec(
        key=CONF_DEBOUNCE_SECONDS,
        name="Debounce time",
        translation_key="debounce_time",
        icon="mdi:timer-sand",
        min_value=10,
        max_value=600,
        step=10,
        mode=NumberMode.BOX,
        unit=UnitOfTime.SECONDS,
        entity_category=EntityCategory.CONFIG,
        value_getter="debounce",
    ),
    LanternatorNumberSpec(
        key=CONF_POLLING_MINUTES,
        name="Polling interval",
        translation_key="polling_interval",
        icon="mdi:update",
        min_value=1,
        max_value=60,
        step=1,
        mode=NumberMode.BOX,
        unit=UnitOfTime.MINUTES,
        entity_category=EntityCategory.CONFIG,
        value_getter="polling_minutes",
    ),
    LanternatorNumberSpec(
        key=CONF_BRIGHTNESS,
        name="Brightness",
        translation_key="brightness",
        icon="mdi:brightness-percent",
        min_value=1,
        max_value=255,
        step=1,
        mode=NumberMode.SLIDER,
        unit=None,
        entity_category=EntityCategory.CONFIG,
        value_getter="brightness",
    ),
    LanternatorNumberSpec(
        key=CONF_COLOR_TEMP,
        name="Color temperature",
        translation_key="color_temperature",
        icon="mdi:thermometer",
        min_value=153,
        max_value=500,
        step=1,
        mode=NumberMode.BOX,
        unit="mireds",
        entity_category=EntityCategory.CONFIG,
        value_getter="color_temp",
    ),
    LanternatorNumberSpec(
        key=CONF_RGB_COLOR_R,
        name="RGB Red",
        translation_key="rgb_red",
        icon="mdi:palette",
        min_value=0,
        max_value=255,
        step=1,
        mode=NumberMode.BOX,
        unit=None,
        entity_category=EntityCategory.CONFIG,
        value_getter="rgb_r",
    ),
    LanternatorNumberSpec(
        key=CONF_RGB_COLOR_G,
        name="RGB Green",
        translation_key="rgb_green",
        icon="mdi:palette",
        min_value=0,
        max_value=255,
        step=1,
        mode=NumberMode.BOX,
        unit=None,
        entity_category=EntityCategory.CONFIG,
        value_getter="rgb_g",
    ),
    LanternatorNumberSpec(
        key=CONF_RGB_COLOR_B,
        name="RGB Blue",
        translation_key="rgb_blue",
        icon="mdi:palette",
        min_value=0,
        max_value=255,
        step=1,
        mode=NumberMode.BOX,
        unit=None,
        entity_category=EntityCategory.CONFIG,
        value_getter="rgb_b",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """REQ: Setup delle entità number per questa istanza."""
    coordinator: LanternatorCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        LanternatorNumber(coordinator, spec) for spec in NUMBER_SPECS
    ])


class LanternatorNumber(CoordinatorEntity, NumberEntity):
    """
    REQ: Entità number configurabile da UI.
    Aggiorna il coordinator a runtime e persiste il valore nella config entry.
    """

    def __init__(
        self,
        coordinator: LanternatorCoordinator,
        spec: LanternatorNumberSpec,
    ) -> None:
        """Inizializza dalla specifica."""
        super().__init__(coordinator)
        self._spec = spec

        # REQ (HA entity ID bug): _attr_name in inglese
        self._attr_name = spec.name
        self._attr_translation_key = spec.translation_key
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{spec.key}"
        )
        self._attr_icon = spec.icon
        self._attr_native_min_value = spec.min_value
        self._attr_native_max_value = spec.max_value
        self._attr_native_step = spec.step
        self._attr_mode = spec.mode
        self._attr_native_unit_of_measurement = spec.unit
        self._attr_entity_category = spec.entity_category
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> float | None:
        """REQ: Valore corrente dal coordinator."""
        return getattr(self.coordinator, self._spec.value_getter)

    async def async_set_native_value(self, value: float) -> None:
        """
        REQ: Aggiorna il parametro a runtime nel coordinator.
        Il coordinator persiste il valore nella config entry.
        """
        await self.coordinator.async_update_parameter(
            self._spec.key, value
        )
        self.async_write_ha_state()
