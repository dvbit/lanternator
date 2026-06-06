"""
Lanternator – Config Flow
REQ: Config flow UI a due step. Relay opzionale tramite checkbox.
     Step 1: entità base + "usa relay?"
     Step 2: relay (se richiesto) + parametri numerici
     Istanziabile più volte per più lanterne.
"""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.helpers import selector

from .const import (
    CONF_BRIGHTNESS,
    CONF_COLOR_TEMP,
    CONF_DEBOUNCE_SECONDS,
    CONF_LIGHT,
    CONF_LUX_SENSOR,
    CONF_LUX_THRESHOLD,
    CONF_OVERRIDE,
    CONF_POLLING_MINUTES,
    CONF_RELAY,
    CONF_RGB_COLOR_B,
    CONF_RGB_COLOR_G,
    CONF_RGB_COLOR_R,
    DEFAULT_DEBOUNCE_SECONDS,
    DEFAULT_LUX_THRESHOLD,
    DEFAULT_POLLING_MINUTES,
    DOMAIN,
)

# Chiave interna per la checkbox "usa relay" (non persistita nella config entry)
CONF_USE_RELAY = "use_relay"


class LanternatorConfigFlow(ConfigFlow, domain=DOMAIN):
    """REQ: Config flow a due step per istanziare l'automazione."""

    VERSION = 1

    def __init__(self) -> None:
        """Inizializza lo storage temporaneo tra step."""
        self._step1_data: dict = {}

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> dict:
        """
        REQ: Step 1 — entità obbligatorie + checkbox relay.
        Lampadina, sensore lux, override, e "Usa relay?".
        """
        if user_input is not None:
            # Salva i dati dello step 1 per combinarli nello step 2
            self._step1_data = user_input
            return await self.async_step_params()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_LIGHT): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="light")
                ),
                vol.Required(CONF_LUX_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_OVERRIDE): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="input_boolean")
                ),
                # REQ: Checkbox per abilitare il relay
                vol.Required(CONF_USE_RELAY, default=False): selector.BooleanSelector(),
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema)

    async def async_step_params(
        self, user_input: dict | None = None
    ) -> dict:
        """
        REQ: Step 2 — relay (se richiesto) + tutti i parametri numerici.
        """
        if user_input is not None:
            # Combina step 1 + step 2, rimuovi la chiave interna use_relay
            combined = {**self._step1_data, **user_input}
            use_relay = combined.pop(CONF_USE_RELAY, False)

            # Se use_relay è False, assicura che relay non sia nei dati
            if not use_relay:
                combined.pop(CONF_RELAY, None)

            # Unique ID basato su relay (se presente) o lampadina
            unique_key = combined.get(CONF_RELAY) or combined[CONF_LIGHT]
            await self.async_set_unique_id(unique_key)
            self._abort_if_unique_id_configured()

            title = unique_key.split(".")[-1].replace("_", " ").title()
            return self.async_create_entry(title=title, data=combined)

        # Costruisci lo schema in base alla scelta relay
        use_relay = self._step1_data.get(CONF_USE_RELAY, False)
        fields: dict = {}

        # REQ: Mostra il selector relay solo se richiesto
        if use_relay:
            fields[vol.Required(CONF_RELAY)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="switch")
            )

        # Parametri numerici (sempre presenti)
        fields[vol.Optional(CONF_LUX_THRESHOLD, default=DEFAULT_LUX_THRESHOLD)] = (
            selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=1000, step=1, mode="box")
            )
        )
        fields[vol.Optional(CONF_DEBOUNCE_SECONDS, default=DEFAULT_DEBOUNCE_SECONDS)] = (
            selector.NumberSelector(
                selector.NumberSelectorConfig(min=10, max=600, step=10, mode="box")
            )
        )
        fields[vol.Optional(CONF_POLLING_MINUTES, default=DEFAULT_POLLING_MINUTES)] = (
            selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=60, step=1, mode="box")
            )
        )
        # Parametri lampadina opzionali
        fields[vol.Optional(CONF_BRIGHTNESS)] = selector.NumberSelector(
            selector.NumberSelectorConfig(min=1, max=255, step=1, mode="slider")
        )
        fields[vol.Optional(CONF_COLOR_TEMP)] = selector.NumberSelector(
            selector.NumberSelectorConfig(min=153, max=500, step=1, mode="box")
        )
        fields[vol.Optional(CONF_RGB_COLOR_R)] = selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=255, step=1, mode="box")
        )
        fields[vol.Optional(CONF_RGB_COLOR_G)] = selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=255, step=1, mode="box")
        )
        fields[vol.Optional(CONF_RGB_COLOR_B)] = selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=255, step=1, mode="box")
        )

        return self.async_show_form(
            step_id="params", data_schema=vol.Schema(fields)
        )
