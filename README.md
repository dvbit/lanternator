# Lanternator

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A Home Assistant custom integration that manages a relay + smart bulb pair under a porch, turning the light on/off based on ambient lux with hysteresis, debounce, automatic state restoration, and manual override.

## Features

- **Lux-based control** with configurable threshold and fixed ±5 lux hysteresis
- **Debounce** — lux condition must persist for a configurable time before acting
- **Relay always ON** — the smart bulb stays powered and reachable at all times
- **Automatic restoration** — if a user accidentally toggles the relay or bulb, the desired state is immediately restored
- **Manual override** — an `input_boolean` disables all automation; when turned OFF, the automation re-evaluates immediately
- **Safety polling** — periodic check to ensure the actual state matches the desired state
- **Optional bulb parameters** — brightness, color temperature (mireds), RGB color
- **Multi-instance** — configure multiple lanterns independently via the UI
- **Multilingual** — EN, IT, FR, ES, DE

## How It Works

### Desired State Logic

| Condition | Desired State |
|---|---|
| Lux < (threshold − 5) for `debounce` seconds | **ON**: relay ON, bulb ON |
| Lux > (threshold + 5) for `debounce` seconds | **OFF**: relay ON, bulb OFF |
| Lux in dead band (threshold ± 5) | No change |

### Restoration Behavior

| Scenario | Action |
|---|---|
| User turns relay OFF, desired = ON | Relay ON → wait for bulb → bulb ON |
| User turns relay OFF, desired = OFF | Relay ON (keep alive) |
| User turns bulb OFF, desired = ON | Bulb ON |
| User turns bulb ON, desired = OFF | Bulb OFF |

### Override

When the override `input_boolean` is ON, the automation does not act. When it returns to OFF, the desired state is immediately re-evaluated without debounce.

## Installation

### HACS (recommended)

1. Open HACS → Integrations → ⋮ → Custom repositories
2. Add `https://github.com/dvbit/lanternator` as **Integration**
3. Install **Lanternator**
4. Restart Home Assistant

### Manual

Copy `custom_components/lanternator/` to your `config/custom_components/` directory and restart.

## Configuration

Go to **Settings → Devices & Services → Add Integration → Lanternator**.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| Relay switch | `switch.*` | required | Entity controlling power to the bulb |
| Smart bulb | `light.*` | required | The smart bulb entity |
| Lux sensor | `sensor.*` | required | Ambient light sensor (lux) |
| Override toggle | `input_boolean.*` | required | Disables automation when ON |
| Lux threshold | number | 20 | Lux level for on/off (±5 hysteresis) |
| Debounce time | number (seconds) | 120 | How long the lux condition must persist |
| Polling interval | number (minutes) | 5 | Safety polling interval |
| Brightness | number (1-255) | — | Optional: fixed brightness |
| Color temperature | number (mireds) | — | Optional: fixed color temp |
| RGB Red | number (0-255) | — | Optional: red channel |
| RGB Green | number (0-255) | — | Optional: green channel |
| RGB Blue | number (0-255) | — | Optional: blue channel |

## Usage Examples

### Example 1: Basic porch light

- Relay: `switch.porch_relay`
- Bulb: `light.porch_bulb`
- Lux sensor: `sensor.outdoor_lux`
- Override: `input_boolean.porch_override`
- Threshold: 20 lux (default)
- Debounce: 120 seconds (default)

The bulb turns ON when ambient light drops below 15 lux for 2 minutes, and OFF when it rises above 25 lux for 2 minutes.

### Example 2: Warm white at 50% brightness

Same as above, plus:
- Brightness: 128
- Color temperature: 370 mireds

### Example 3: Multiple lanterns

Add the integration multiple times, each with a different relay/bulb/sensor combination. Each instance operates independently.

### Example 4: Colored accent light

- Relay: `switch.garden_relay`
- Bulb: `light.garden_spot`
- Lux sensor: `sensor.garden_lux`
- Override: `input_boolean.garden_override`
- Threshold: 10 lux
- Debounce: 60 seconds
- RGB: R=255, G=180, B=50 (warm amber)

## Specification

This integration was built from the following consolidated requirement:

- The relay is upstream of the smart bulb (in series) and must remain ON at all times to keep the bulb powered and reachable.
- Desired state is determined by ambient lux with fixed ±5 hysteresis and configurable debounce.
- State restoration is immediate (no debounce) when a user accidentally changes the relay or bulb.
- Manual override via `input_boolean` fully disables the automation; returning to OFF triggers immediate re-evaluation without debounce.
- Periodic polling acts as a safety net, respecting debounce for lux evaluation.

## License

MIT
