"""
Lanternator – Integration Setup
REQ: Setup dell'integrazione. Crea il coordinator e avvia i listener.
     Supporta setup/unload per istanze multiple indipendenti.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import LanternatorCoordinator

_LOGGER = logging.getLogger(__name__)

type LanternatorConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: LanternatorConfigEntry) -> bool:
    """
    REQ: Setup di una singola istanza dell'automazione.
    Crea il coordinator con i parametri dalla config entry e avvia.
    """
    coordinator = LanternatorCoordinator(hass, dict(entry.data))

    # Primo refresh per inizializzare il polling
    await coordinator.async_config_entry_first_refresh()

    # Avvia i listener event-driven
    await coordinator.async_start()

    # Salva il coordinator per poterlo fermare all'unload
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    _LOGGER.info("Lanternator entry loaded: %s", entry.title)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: LanternatorConfigEntry
) -> bool:
    """REQ: Rimuovi l'istanza — ferma listener e coordinator."""
    coordinator: LanternatorCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
    await coordinator.async_stop()
    _LOGGER.info("Lanternator entry unloaded: %s", entry.title)
    return True
