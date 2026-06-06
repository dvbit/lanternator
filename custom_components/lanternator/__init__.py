"""
Lanternator – Integration Setup
REQ: Setup dell'integrazione. Crea il coordinator, avvia i listener,
     e forwarda le piattaforme sensor e number per il device.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import LanternatorCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    REQ: Setup di una singola istanza dell'automazione.
    Crea il coordinator con i parametri dalla config entry e avvia.
    """
    coordinator = LanternatorCoordinator(hass, entry)

    # Primo refresh per inizializzare il polling
    await coordinator.async_config_entry_first_refresh()

    # Avvia i listener event-driven
    await coordinator.async_start()

    # Salva il coordinator per poterlo usare dalle piattaforme
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # REQ: Forward delle piattaforme sensor e number per il device
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info("Lanternator entry loaded: %s", entry.title)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """REQ: Rimuovi l'istanza — ferma listener, rimuovi piattaforme e coordinator."""
    # Unload delle piattaforme
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator: LanternatorCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_stop()
        _LOGGER.info("Lanternator entry unloaded: %s", entry.title)

    return unload_ok
