"""
Lanternator – Coordinator
REQ: Logica centrale che gestisce stato desiderato, debounce lux,
     ripristino immediato, polling di sicurezza, override.
     Espone DeviceInfo per raggruppare le entità sotto un device.
     Espone metodi per aggiornare parametri a runtime dalle entità number.
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
    REQ: Coordinator che gestisce una singola coppia relay/lampadina.
    - Calcola stato desiderato in base ai lux con isteresi e debounce
    - Ripristina immediatamente se stato attuale diverge
    - Polling periodico come rete di sicurezza
    - Override disabilita ogni intervento
    - Espone DeviceInfo per raggruppare tutte le entità
    - Espone metodi per aggiornare parametri a runtime
    """

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Inizializza con i parametri dalla config entry."""
        self.config_entry = config_entry
        config = dict(config_entry.data)

        self._relay: str = config[CONF_RELAY]
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
            name=f"{DOMAIN}_{self._relay}",
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
            sw_version="1.1.0",
            configuration_url="https://github.com/dvbit/lanternator",
        )

    # ------------------------------------------------------------------
    # Public properties for sensor entities
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
        """Soglia lux corrente."""
        return self._threshold

    @property
    def debounce(self) -> int:
        """Debounce corrente in secondi."""
        return self._debounce

    @property
    def polling_minutes(self) -> int:
        """Intervallo polling corrente in minuti."""
        return self._polling_minutes

    @property
    def brightness(self) -> int | None:
        """Brightness corrente."""
        return self._brightness

    @property
    def color_temp(self) -> int | None:
        """Color temperature corrente."""
        return self._color_temp

    @property
    def rgb_r(self) -> int | None:
        """RGB Red corrente."""
        return self._rgb_color[0] if self._rgb_color else None

    @property
    def rgb_g(self) -> int | None:
        """RGB Green corrente."""
        return self._rgb_color[1] if self._rgb_color else None

    @property
    def rgb_b(self) -> int | None:
        """RGB Blue corrente."""
        return self._rgb_color[2] if self._rgb_color else None

    # ------------------------------------------------------------------
    # Runtime parameter updates (REQ: configurabili da UI via number)
    # ------------------------------------------------------------------

    async def async_update_parameter(self, key: str, value: Any) -> None:
        """
        REQ: Aggiorna un parametro a runtime e persisti nella config entry.
        Chiamato dalle entità number quando l'utente modifica un valore.
        """
        # Aggiorna il valore interno
        if key == CONF_LUX_THRESHOLD:
            self._threshold = float(value)
        elif key == CONF_DEBOUNCE_SECONDS:
            self._debounce = int(value)
        elif key == CONF_POLLING_MINUTES:
            self._polling_minutes = int(value)
            # REQ: Aggiorna anche l'intervallo di polling del coordinator
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

        # Persisti nella config entry
        new_data = dict(self.config_entry.data)
        new_data[key] = value
        self.hass.config_entries.async_update_entry(
            self.config_entry, data=new_data
        )

        _LOGGER.info("Lanternator parameter %s updated to %s", key, value)

        # Rivaluta stato se il parametro lux è cambiato
        if key == CONF_LUX_THRESHOLD:
            await self._evaluate_lux_immediate()

    # ------------------------------------------------------------------
    # Setup & teardown
    # ------------------------------------------------------------------

    async def async_start(self) -> None:
        """REQ: Registra listener su relay, lampadina, sensore lux, override."""

        # REQ trigger 1: Cambio valore del sensore lux
        self._unsub_listeners.append(
            async_track_state_change_event(
                self.hass, self._lux_sensor, self._handle_lux_change
            )
        )

        # REQ trigger 2: Cambio stato del relay
        self._unsub_listeners.append(
            async_track_state_change_event(
                self.hass, self._relay, self._handle_device_change
            )
        )

        # REQ trigger 3: Cambio stato della lampadina
        self._unsub_listeners.append(
            async_track_state_change_event(
                self.hass, self._light, self._handle_device_change
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
            "Lanternator started for relay=%s light=%s", self._relay, self._light
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

        # REQ: Il polling non bypassa il debounce, rivaluta come un cambio lux
        self._evaluate_lux_with_debounce()

        # Verifica coerenza stato attuale vs desiderato
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
        REQ trigger 2/3: Cambio stato relay o lampadina.
        Se diverge dallo stato desiderato, ripristina immediatamente.
        """
        if self._is_override_on():
            return

        # REQ: Ignora cambi causati dalle nostre stesse azioni
        if self._acting:
            return

        # REQ: Ignora transizioni verso unavailable/unknown (non sono azioni utente)
        new_state: State | None = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return

        # REQ: Ripristino immediato (senza debounce)
        self.hass.async_create_task(self._enforce_desired_state())

    @callback
    def _handle_override_change(self, event: Event) -> None:
        """
        REQ: Quando override torna a OFF, rivaluta immediatamente
             (senza debounce) e ripristina.
        """
        new_state: State | None = event.data.get("new_state")
        if new_state is None:
            return

        if new_state.state == STATE_OFF:
            _LOGGER.info("Lanternator override OFF — immediate re-evaluation")
            # REQ: Override OFF → rivalutazione immediata senza debounce
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
        # REQ: Fascia morta — mantenere stato corrente, non agire
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
            # REQ: Fascia morta — cancella eventuale debounce pendente
            self._cancel_debounce()
            return

        if new_desired == self._desired_state:
            # Già nello stato desiderato corretto, cancella debounce
            self._cancel_debounce()
            return

        # REQ: Nuova zona diversa dallo stato desiderato → avvia/riavvia debounce
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
            """
            REQ: Timer scade → verifica che la condizione sia ancora valida,
                 aggiorna stato desiderato, esegui azione.
            """
            self._debounce_cancel = None
            lux = self._get_current_lux()
            if lux is None:
                return

            # Ricontrolla che la condizione sia ancora valida
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
        """
        REQ: Valutazione immediata (usata all'avvio e quando override torna OFF).
        Nessun debounce.
        """
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
        - Relay deve essere ON
        - Lampadina deve essere ON (con brightness/color_temp/rgb se configurati)
        """
        relay_state = self.hass.states.get(self._relay)

        # REQ: Se relay è OFF → accendere il relay
        if relay_state is None or relay_state.state != STATE_ON:
            _LOGGER.info("Lanternator: turning relay ON (%s)", self._relay)
            await self.hass.services.async_call(
                "switch", "turn_on", {"entity_id": self._relay}, blocking=True
            )
            # REQ: Attendere che la lampadina diventi disponibile (timeout 10s)
            await self._wait_for_light_available()

        # REQ: Se la lampadina è OFF → comandare la lampadina su ON
        light_state = self.hass.states.get(self._light)
        if light_state is None or light_state.state != STATE_ON:
            _LOGGER.info("Lanternator: turning light ON (%s)", self._light)
            await self._turn_on_light()

    async def _enforce_off(self) -> None:
        """
        REQ: Stato desiderato SPENTO — relay ON, lampadina OFF.
        Il relay deve restare sempre acceso per mantenere la lampadina raggiungibile.
        """
        relay_state = self.hass.states.get(self._relay)

        # REQ: Se relay è OFF → riaccendi (relay sempre ON)
        if relay_state is None or relay_state.state != STATE_ON:
            _LOGGER.info(
                "Lanternator: turning relay ON (keep alive) (%s)", self._relay
            )
            await self.hass.services.async_call(
                "switch", "turn_on", {"entity_id": self._relay}, blocking=True
            )
            await self._wait_for_light_available()

        # REQ: Se la lampadina è ON → spegni
        light_state = self.hass.states.get(self._light)
        if light_state is not None and light_state.state == STATE_ON:
            _LOGGER.info("Lanternator: turning light OFF (%s)", self._light)
            await self.hass.services.async_call(
                "light", "turn_off", {"entity_id": self._light}, blocking=True
            )

    async def _turn_on_light(self) -> None:
        """
        REQ: Accende la lampadina applicando i parametri opzionali
        (brightness, color_temp, rgb_color) se configurati.
        """
        service_data: dict[str, Any] = {"entity_id": self._light}

        # REQ: Parametri opzionali lampadina
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
        """
        REQ: Attende che la lampadina diventi disponibile dopo l'accensione del relay.
        Timeout di BULB_AVAILABILITY_TIMEOUT secondi.
        """
        for _ in range(BULB_AVAILABILITY_TIMEOUT * 2):  # check ogni 0.5s
            state = self.hass.states.get(self._light)
            if state is not None and state.state not in (
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
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
