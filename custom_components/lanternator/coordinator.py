"""
Lanternator – Coordinator
REQ: Logica centrale che gestisce stato desiderato, debounce lux,
     ripristino immediato, polling di sicurezza, override.
     Relay opzionale: se assente, gestisce solo la lampadina smart.
     Quando la lampadina passa da unavailable ad available, applica
     lo stato desiderato in base alla soglia lux.
     Espone DeviceInfo per raggruppare le entità sotto un device.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback, Event, State
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_call_later,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

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
    DOMAIN,
    HYSTERESIS,
    BULB_AVAILABILITY_TIMEOUT,
    STATE_ON as DESIRED_ON,
    STATE_OFF as DESIRED_OFF,
    STATE_UNKNOWN as DESIRED_UNKNOWN,
)

_LOGGER = logging.getLogger(__name__)


class LanternatorCoordinator(DataUpdateCoordinator):
    """
    REQ: Coordinator che gestisce una singola coppia relay/lampadina
    (o solo lampadina se relay assente).
    - Calcola stato desiderato in base ai lux con isteresi e debounce
    - Ripristina immediatamente se stato attuale diverge
    - Quando la lampadina torna available, applica stato desiderato
    - Polling periodico come rete di sicurezza
    - Override disabilita ogni intervento
    """

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Inizializza con i parametri dalla config entry."""
        self.config_entry = config_entry
        config = dict(config_entry.data)

        # REQ: Relay opzionale — None se non configurato
        self._relay: str | None = config.get(CONF_RELAY) or None
        self._light: str = config[CONF_LIGHT]
        self._lux_sensor: str = config[CONF_LUX_SENSOR]
        self._override: str = config[CONF_OVERRIDE]
        self._threshold: float = config[CONF_LUX_THRESHOLD]
        self._debounce: int = config[CONF_DEBOUNCE_SECONDS]
        self._polling_minutes: int = config[CONF_POLLING_MINUTES]

        # REQ: Parametri opzionali lampadina (brightness, color_temp, rgb)
        self._brightness: int | None = config.get(CONF_BRIGHTNESS)
        self._color_temp: int | None = config.get(CONF_COLOR_TEMP)
        self._rgb_color: list[int] | None = None
        r = config.get(CONF_RGB_COLOR_R)
        g = config.get(CONF_RGB_COLOR_G)
        b = config.get(CONF_RGB_COLOR_B)
        if r is not None and g is not None and b is not None:
            self._rgb_color = [int(r), int(g), int(b)]

        # REQ: Stato desiderato — inizia come INDETERMINATO
        self._desired_state: str = DESIRED_UNKNOWN

        # REQ: Debounce — handle del timer cancellabile
        self._debounce_cancel: callback | None = None

        # Listener unsub handles
        self._unsub_listeners: list[callback] = []

        # REQ: Lock per serializzare le azioni di ripristino
        self._action_lock = asyncio.Lock()

        # Flag to suppress restore during our own actions
        self._acting = False

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self._relay or self._light}",
            # REQ: Polling periodico ogni polling_minuti come rete di sicurezza
            update_interval=timedelta(minutes=self._polling_minutes),
        )

    # ------------------------------------------------------------------
    # Device info (REQ: device che riunisce tutti i parametri)
    # ------------------------------------------------------------------

    @property
    def device_info(self) -> DeviceInfo:
        """REQ: DeviceInfo per raggruppare tutte le entità sotto un device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.entry_id)},
            name=self.config_entry.title,
            manufacturer="Lanternator",
            model="Porch Light Controller",
            sw_version="1.3.0",
            configuration_url="https://github.com/dvbit/lanternator",
        )

    # ------------------------------------------------------------------
    # Public properties for sensor/number entities
    # ------------------------------------------------------------------

    @property
    def desired_state(self) -> str:
        """REQ: Stato desiderato corrente (on/off/unknown)."""
        return self._desired_state

    @property
    def current_lux(self) -> float | None:
        """REQ: Valore lux corrente dal sensore."""
        return self._get_current_lux()

    @property
    def threshold(self) -> float:
        return self._threshold

    @property
    def debounce(self) -> int:
        return self._debounce

    @property
    def polling_minutes(self) -> int:
        return self._polling_minutes

    @property
    def brightness(self) -> int | None:
        return self._brightness

    @property
    def color_temp(self) -> int | None:
        return self._color_temp

    @property
    def rgb_r(self) -> int | None:
        return self._rgb_color[0] if self._rgb_color else None

    @property
    def rgb_g(self) -> int | None:
        return self._rgb_color[1] if self._rgb_color else None

    @property
    def rgb_b(self) -> int | None:
        return self._rgb_color[2] if self._rgb_color else None

    @property
    def has_relay(self) -> bool:
        """True se un relay è configurato."""
        return self._relay is not None

    # ------------------------------------------------------------------
    # Runtime parameter updates
    # ------------------------------------------------------------------

    async def async_update_parameter(self, key: str, value: Any) -> None:
        """
        REQ: Aggiorna un parametro a runtime e persisti nella config entry.
        """
        if key == CONF_LUX_THRESHOLD:
            self._threshold = float(value)
        elif key == CONF_DEBOUNCE_SECONDS:
            self._debounce = int(value)
        elif key == CONF_POLLING_MINUTES:
            self._polling_minutes = int(value)
            self.update_interval = timedelta(minutes=self._polling_minutes)
        elif key == CONF_BRIGHTNESS:
            self._brightness = int(value) if value is not None else None
        elif key == CONF_COLOR_TEMP:
            self._color_temp = int(value) if value is not None else None
        elif key == CONF_RGB_COLOR_R:
            if self._rgb_color is None:
                self._rgb_color = [0, 0, 0]
            self._rgb_color[0] = int(value)
        elif key == CONF_RGB_COLOR_G:
            if self._rgb_color is None:
                self._rgb_color = [0, 0, 0]
            self._rgb_color[1] = int(value)
        elif key == CONF_RGB_COLOR_B:
            if self._rgb_color is None:
                self._rgb_color = [0, 0, 0]
            self._rgb_color[2] = int(value)

        new_data = dict(self.config_entry.data)
        new_data[key] = value
        self.hass.config_entries.async_update_entry(
            self.config_entry, data=new_data
        )
        _LOGGER.info("Lanternator parameter %s updated to %s", key, value)

        if key == CONF_LUX_THRESHOLD:
            await self._evaluate_lux_immediate()

    # ------------------------------------------------------------------
    # Setup & teardown
    # ------------------------------------------------------------------

    async def async_start(self) -> None:
        """REQ: Registra listener su relay (se presente), lampadina, sensore lux, override."""

        # REQ trigger 1: Cambio valore del sensore lux
        self._unsub_listeners.append(
            async_track_state_change_event(
                self.hass, self._lux_sensor, self._handle_lux_change
            )
        )

        # REQ trigger 2: Cambio stato del relay (solo se configurato)
        if self._relay is not None:
            self._unsub_listeners.append(
                async_track_state_change_event(
                    self.hass, self._relay, self._handle_device_change
                )
            )

        # REQ trigger 3: Cambio stato della lampadina
        # Gestisce sia cambio on/off sia transizione unavailable→available
        self._unsub_listeners.append(
            async_track_state_change_event(
                self.hass, self._light, self._handle_light_change
            )
        )

        # REQ: Override — quando torna a OFF, rivaluta immediatamente
        self._unsub_listeners.append(
            async_track_state_change_event(
                self.hass, self._override, self._handle_override_change
            )
        )

        # Valutazione iniziale dei lux per determinare lo stato desiderato
        await self._evaluate_lux_immediate()

        _LOGGER.info(
            "Lanternator started for relay=%s light=%s",
            self._relay or "(none)",
            self._light,
        )

    async def async_stop(self) -> None:
        """Rimuovi tutti i listener e cancella debounce pendenti."""
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()
        self._cancel_debounce()

    # ------------------------------------------------------------------
    # Polling (REQ trigger 4: rete di sicurezza)
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> None:
        """
        REQ: Polling periodico — rivaluta stato desiderato (con debounce)
             e ripristina se necessario.
        """
        if self._is_override_on():
            return
        self._evaluate_lux_with_debounce()
        await self._enforce_desired_state()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    @callback
    def _handle_lux_change(self, event: Event) -> None:
        """REQ trigger 1: Cambio valore del sensore lux — rivaluta con debounce."""
        if self._is_override_on():
            return
        self._evaluate_lux_with_debounce()

    @callback
    def _handle_device_change(self, event: Event) -> None:
        """
        REQ trigger 2: Cambio stato relay.
        Se diverge dallo stato desiderato, ripristina immediatamente.
        """
        if self._is_override_on() or self._acting:
            return

        new_state: State | None = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return

        self.hass.async_create_task(self._enforce_desired_state())

    @callback
    def _handle_light_change(self, event: Event) -> None:
        """
        REQ trigger 3: Cambio stato lampadina.
        Gestisce due scenari:
        1. Cambio on/off utente → ripristino immediato se diverge
        2. Transizione unavailable→available → applica stato desiderato
           (REQ: riaccensione alimentazione lampadina smart senza relay)
        """
        if self._is_override_on():
            return

        old_state: State | None = event.data.get("old_state")
        new_state: State | None = event.data.get("new_state")
        if new_state is None:
            return

        # REQ: Transizione unavailable/unknown → available (qualsiasi stato on/off)
        # La lampadina è tornata raggiungibile → applica stato desiderato
        old_is_unavail = (
            old_state is None
            or old_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        )
        new_is_avail = new_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)

        if old_is_unavail and new_is_avail:
            _LOGGER.info(
                "Lanternator: light %s became available — enforcing desired state",
                self._light,
            )
            self.hass.async_create_task(self._enforce_desired_state())
            return

        # Ignora transizioni verso unavailable (non è azione utente)
        if not new_is_avail:
            return

        # Ignora cambi causati dalle nostre stesse azioni
        if self._acting:
            return

        # REQ: Cambio on/off utente → ripristino immediato
        self.hass.async_create_task(self._enforce_desired_state())

    @callback
    def _handle_override_change(self, event: Event) -> None:
        """REQ: Quando override torna a OFF, rivaluta immediatamente."""
        new_state: State | None = event.data.get("new_state")
        if new_state is None:
            return

        if new_state.state == STATE_OFF:
            _LOGGER.info("Lanternator override OFF — immediate re-evaluation")
            self.hass.async_create_task(self._evaluate_lux_immediate())

    # ------------------------------------------------------------------
    # Lux evaluation (REQ: isteresi ±5, debounce, fascia morta)
    # ------------------------------------------------------------------

    def _get_current_lux(self) -> float | None:
        """Legge il valore corrente del sensore lux."""
        state = self.hass.states.get(self._lux_sensor)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    def _compute_desired_from_lux(self, lux: float) -> str | None:
        """
        REQ: Calcola lo stato desiderato in base alla soglia con isteresi fissa ±5.
        - Lux < (soglia - 5) → ACCESO
        - Lux > (soglia + 5) → SPENTO
        - Fascia morta → None (nessun cambio)
        """
        threshold_low = self._threshold - HYSTERESIS
        threshold_high = self._threshold + HYSTERESIS

        if lux < threshold_low:
            return DESIRED_ON
        if lux > threshold_high:
            return DESIRED_OFF
        return None

    @callback
    def _evaluate_lux_with_debounce(self) -> None:
        """
        REQ: Avvia timer debounce. Se la condizione cambia durante il debounce,
             cancella e riavvia.
        """
        lux = self._get_current_lux()
        if lux is None:
            self._cancel_debounce()
            return

        new_desired = self._compute_desired_from_lux(lux)
        if new_desired is None:
            self._cancel_debounce()
            return

        if new_desired == self._desired_state:
            self._cancel_debounce()
            return

        self._cancel_debounce()
        _LOGGER.debug(
            "Lanternator debounce started: lux=%.1f → desired=%s (wait %ds)",
            lux,
            new_desired,
            self._debounce,
        )
        self._debounce_cancel = async_call_later(
            self.hass,
            self._debounce,
            self._debounce_expired_factory(new_desired),
        )

    def _debounce_expired_factory(self, candidate: str):
        """Crea callback per quando il debounce scade."""

        async def _debounce_expired(_now) -> None:
            """REQ: Timer scade → verifica condizione, aggiorna e applica."""
            self._debounce_cancel = None
            lux = self._get_current_lux()
            if lux is None:
                return

            confirmed = self._compute_desired_from_lux(lux)
            if confirmed != candidate:
                _LOGGER.debug(
                    "Lanternator debounce expired but condition changed: "
                    "candidate=%s, current=%s",
                    candidate,
                    confirmed,
                )
                return

            _LOGGER.info(
                "Lanternator desired state changed to %s (lux=%.1f)",
                candidate,
                lux,
            )
            self._desired_state = candidate
            await self._enforce_desired_state()

        return _debounce_expired

    async def _evaluate_lux_immediate(self) -> None:
        """REQ: Valutazione immediata (avvio, override OFF, cambio soglia)."""
        self._cancel_debounce()
        lux = self._get_current_lux()
        if lux is None:
            return

        new_desired = self._compute_desired_from_lux(lux)
        if new_desired is not None:
            self._desired_state = new_desired
            _LOGGER.info(
                "Lanternator immediate evaluation: desired=%s (lux=%.1f)",
                new_desired,
                lux,
            )
            await self._enforce_desired_state()

    @callback
    def _cancel_debounce(self) -> None:
        """Cancella il timer di debounce se attivo."""
        if self._debounce_cancel is not None:
            self._debounce_cancel()
            self._debounce_cancel = None

    # ------------------------------------------------------------------
    # State enforcement (REQ: ripristino immediato)
    # ------------------------------------------------------------------

    async def _enforce_desired_state(self) -> None:
        """
        REQ: Confronta stato attuale vs desiderato e ripristina se diverge.
        Serializzato con lock per evitare azioni concorrenti.
        """
        if self._desired_state == DESIRED_UNKNOWN:
            return

        async with self._action_lock:
            self._acting = True
            try:
                if self._desired_state == DESIRED_ON:
                    await self._enforce_on()
                else:
                    await self._enforce_off()
            finally:
                self._acting = False

    async def _enforce_on(self) -> None:
        """
        REQ: Stato desiderato ACCESO.
        Con relay: relay ON → attendi lampadina → lampadina ON
        Senza relay: lampadina ON (se available)
        """
        # REQ: Gestisci relay solo se configurato
        if self._relay is not None:
            relay_state = self.hass.states.get(self._relay)
            if relay_state is None or relay_state.state != STATE_ON:
                _LOGGER.info("Lanternator: turning relay ON (%s)", self._relay)
                await self.hass.services.async_call(
                    "switch", "turn_on", {"entity_id": self._relay}, blocking=True
                )
                await self._wait_for_light_available()

        # REQ: Lampadina ON — solo se available
        light_state = self.hass.states.get(self._light)
        if light_state is None or light_state.state in (
            STATE_UNAVAILABLE, STATE_UNKNOWN
        ):
            _LOGGER.debug(
                "Lanternator: light %s not available, skipping ON command",
                self._light,
            )
            return

        if light_state.state != STATE_ON:
            _LOGGER.info("Lanternator: turning light ON (%s)", self._light)
            await self._turn_on_light()

    async def _enforce_off(self) -> None:
        """
        REQ: Stato desiderato SPENTO.
        Con relay: relay ON (keep alive), lampadina OFF
        Senza relay: lampadina OFF (se available)
        """
        # REQ: Con relay → mantieni relay acceso per raggiungibilità lampadina
        if self._relay is not None:
            relay_state = self.hass.states.get(self._relay)
            if relay_state is None or relay_state.state != STATE_ON:
                _LOGGER.info(
                    "Lanternator: turning relay ON (keep alive) (%s)", self._relay
                )
                await self.hass.services.async_call(
                    "switch", "turn_on", {"entity_id": self._relay}, blocking=True
                )
                await self._wait_for_light_available()

        # REQ: Lampadina OFF — solo se available e accesa
        light_state = self.hass.states.get(self._light)
        if light_state is None or light_state.state in (
            STATE_UNAVAILABLE, STATE_UNKNOWN
        ):
            return

        if light_state.state == STATE_ON:
            _LOGGER.info("Lanternator: turning light OFF (%s)", self._light)
            await self.hass.services.async_call(
                "light", "turn_off", {"entity_id": self._light}, blocking=True
            )

    async def _turn_on_light(self) -> None:
        """REQ: Accende la lampadina con parametri opzionali."""
        service_data: dict[str, Any] = {"entity_id": self._light}

        if self._brightness is not None:
            service_data["brightness"] = self._brightness
        if self._color_temp is not None:
            service_data["color_temp"] = self._color_temp
        if self._rgb_color is not None:
            service_data["rgb_color"] = self._rgb_color

        await self.hass.services.async_call(
            "light", "turn_on", service_data, blocking=True
        )

    async def _wait_for_light_available(self) -> None:
        """REQ: Attende che la lampadina diventi disponibile (timeout 10s)."""
        for _ in range(BULB_AVAILABILITY_TIMEOUT * 2):
            state = self.hass.states.get(self._light)
            if state is not None and state.state not in (
                STATE_UNAVAILABLE, STATE_UNKNOWN,
            ):
                return
            await asyncio.sleep(0.5)
        _LOGGER.warning(
            "Lanternator: light %s did not become available within %ds",
            self._light,
            BULB_AVAILABILITY_TIMEOUT,
        )

    # ------------------------------------------------------------------
    # Override helper
    # ------------------------------------------------------------------

    def _is_override_on(self) -> bool:
        """REQ: Se override è ON, l'automazione non interviene."""
        state = self.hass.states.get(self._override)
        return state is not None and state.state == STATE_ON
