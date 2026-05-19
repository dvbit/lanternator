"""
Lanternator – Constants
REQ: Centralised keys, defaults and fixed hysteresis value.
"""

DOMAIN = "lanternator"

# --- Config keys (REQ: parametri di input) ---
CONF_RELAY = "relay"
CONF_LIGHT = "light"
CONF_LUX_SENSOR = "lux_sensor"
CONF_LUX_THRESHOLD = "lux_threshold"
CONF_DEBOUNCE_SECONDS = "debounce_seconds"
CONF_OVERRIDE = "override"
CONF_POLLING_MINUTES = "polling_minutes"
CONF_BRIGHTNESS = "brightness"
CONF_COLOR_TEMP = "color_temp"
CONF_RGB_COLOR_R = "rgb_color_r"
CONF_RGB_COLOR_G = "rgb_color_g"
CONF_RGB_COLOR_B = "rgb_color_b"

# --- Defaults (REQ: valori di default) ---
DEFAULT_LUX_THRESHOLD = 20
DEFAULT_DEBOUNCE_SECONDS = 120
DEFAULT_POLLING_MINUTES = 5

# --- Fixed hysteresis (REQ: isteresi fissa ±5 lux, non parametrica) ---
HYSTERESIS = 5

# --- Desired states (REQ: stato desiderato ACCESO / SPENTO) ---
STATE_ON = "on"
STATE_OFF = "off"
STATE_UNKNOWN = "unknown"

# --- Timeouts ---
BULB_AVAILABILITY_TIMEOUT = 10  # seconds to wait for bulb after relay on
