"""
Lanternator – Config Flow
REQ: Config flow UI con tutti i parametri. Relay opzionale.
     Campi opzionali per brightness, color_temp, rgb_color.
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


class LanternatorConfigFlow(ConfigFlow, domain=DOMAIN):
    """REQ: Config flow per istanziare l'automazione con parametri diversi."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> dict:
        """REQ: Step unico con tutti i parametri. Relay opzionale."""
        if user_input is not None:
            # REQ: Unique ID basato su relay (se presente) o lampadina
            unique_key = user_input.get(CONF_RELAY) or user_input[CONF_LIGHT]
            await self.async_set_unique_id(unique_key)
            self._abort_if_unique_id_configured()

            # Titolo leggibile dall'entity_id principale
            title = unique_key.split(".")[-1].replace("_", " ").title()
            return self.async_create_entry(title=title, data=user_input)

        # REQ: Schema — relay opzionale, lampadina obbligatoria
        data_schema = vol.Schema(
            {
                # --- REQ: Relay opzionale (se assente, solo lampadina smart) ---
                vol.Optional(CONF_RELAY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                # --- Entità obbligatorie ---
                vol.Required(CONF_LIGHT): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="light")
                ),
                vol.Required(CONF_LUX_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_OVERRIDE): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="input_boolean")
                ),
                # --- Parametri numerici con default ---
                vol.Optional(
                    CONF_LUX_THRESHOLD, default=DEFAULT_LUX_THRESHOLD
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=1000, step=1, mode="box"
                    )
                ),
                vol.Optional(
                    CONF_DEBOUNCE_SECONDS, default=DEFAULT_DEBOUNCE_SECONDS
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=10, max=600, step=10, mode="box"
                    )
                ),
                vol.Optional(
                    CONF_POLLING_MINUTES, default=DEFAULT_POLLING_MINUTES
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=60, step=1, mode="box"
                    )
                ),
                # --- Parametri lampadina opzionali ---
                vol.Optional(CONF_BRIGHTNESS): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=255, step=1, mode="slider"
                    )
                ),
                vol.Optional(CONF_COLOR_TEMP): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=153, max=500, step=1, mode="box"
                    )
                ),
                vol.Optional(CONF_RGB_COLOR_R): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=255, step=1, mode="box"
                    )
                ),
                vol.Optional(CONF_RGB_COLOR_G): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=255, step=1, mode="box"
                    )
                ),
                vol.Optional(CONF_RGB_COLOR_B): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=255, step=1, mode="box"
                    )
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema)
