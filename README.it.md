# Lanternator

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Integrazione custom per Home Assistant che gestisce una coppia relay + lampadina smart sotto un portico, accendendo e spegnendo la luce in base alla luminosità ambientale con isteresi, debounce, ripristino automatico e override manuale.

## Funzionalità

- **Controllo basato sui lux** con soglia configurabile e isteresi fissa ±5 lux
- **Debounce** — la condizione lux deve persistere per un tempo configurabile prima di agire
- **Relay sempre ON** — la lampadina smart resta alimentata e raggiungibile in ogni momento
- **Ripristino automatico** — se un utente spegne accidentalmente relay o lampadina, lo stato desiderato viene ripristinato immediatamente
- **Override manuale** — un `input_boolean` disabilita l'automazione; quando torna OFF, rivaluta immediatamente
- **Polling di sicurezza** — verifica periodica della coerenza stato attuale vs desiderato
- **Parametri lampadina opzionali** — luminosità, temperatura colore (mireds), colore RGB
- **Multi-istanza** — configura più lanterne indipendenti via UI
- **Multilingua** — EN, IT, FR, ES, DE

## Come Funziona

### Logica stato desiderato

| Condizione | Stato desiderato |
|---|---|
| Lux < (soglia − 5) per `debounce` secondi | **ACCESO**: relay ON, lampadina ON |
| Lux > (soglia + 5) per `debounce` secondi | **SPENTO**: relay ON, lampadina OFF |
| Lux nella fascia morta (soglia ± 5) | Nessun cambio |

### Comportamento di ripristino

| Scenario | Azione |
|---|---|
| Utente spegne relay, desiderato = ACCESO | Relay ON → attesa lampadina → lampadina ON |
| Utente spegne relay, desiderato = SPENTO | Relay ON (mantenimento) |
| Utente spegne lampadina, desiderato = ACCESO | Lampadina ON |
| Utente accende lampadina, desiderato = SPENTO | Lampadina OFF |

### Override

Quando l'`input_boolean` di override è ON, l'automazione non interviene. Quando torna OFF, lo stato desiderato viene rivalutato immediatamente senza debounce.

## Installazione

### HACS (consigliato)

1. Apri HACS → Integrazioni → ⋮ → Repository personalizzati
2. Aggiungi `https://github.com/dvbit/lanternator` come **Integrazione**
3. Installa **Lanternator**
4. Riavvia Home Assistant

### Manuale

Copia `custom_components/lanternator/` nella directory `config/custom_components/` e riavvia.

## Configurazione

Vai su **Impostazioni → Dispositivi e Servizi → Aggiungi Integrazione → Lanternator**.

### Parametri

| Parametro | Tipo | Default | Descrizione |
|---|---|---|---|
| Interruttore relay | `switch.*` | obbligatorio | Entità che alimenta la lampadina |
| Lampadina smart | `light.*` | obbligatorio | La lampadina smart |
| Sensore lux | `sensor.*` | obbligatorio | Sensore luminosità ambientale (lux) |
| Override | `input_boolean.*` | obbligatorio | Disabilita l'automazione quando ON |
| Soglia lux | numero | 20 | Livello lux per accensione/spegnimento (±5 isteresi) |
| Tempo debounce | numero (secondi) | 120 | Persistenza condizione lux prima di agire |
| Intervallo polling | numero (minuti) | 5 | Intervallo polling di sicurezza |
| Luminosità | numero (1-255) | — | Opzionale: luminosità fissa |
| Temperatura colore | numero (mireds) | — | Opzionale: temperatura colore fissa |
| RGB Rosso | numero (0-255) | — | Opzionale: canale rosso |
| RGB Verde | numero (0-255) | — | Opzionale: canale verde |
| RGB Blu | numero (0-255) | — | Opzionale: canale blu |

## Esempi di Utilizzo

### Esempio 1: Luce portico base

- Relay: `switch.porch_relay`
- Lampadina: `light.porch_bulb`
- Sensore lux: `sensor.outdoor_lux`
- Override: `input_boolean.porch_override`
- Soglia: 20 lux (default)
- Debounce: 120 secondi (default)

La lampadina si accende quando la luce ambientale scende sotto 15 lux per 2 minuti, e si spegne quando sale sopra 25 lux per 2 minuti.

### Esempio 2: Bianco caldo al 50% di luminosità

Come sopra, più:
- Luminosità: 128
- Temperatura colore: 370 mireds

### Esempio 3: Più lanterne

Aggiungi l'integrazione più volte, ciascuna con una diversa combinazione relay/lampadina/sensore. Ogni istanza opera indipendentemente.

### Esempio 4: Luce accento colorata

- Relay: `switch.garden_relay`
- Lampadina: `light.garden_spot`
- Sensore lux: `sensor.garden_lux`
- Override: `input_boolean.garden_override`
- Soglia: 10 lux
- Debounce: 60 secondi
- RGB: R=255, G=180, B=50 (ambra caldo)

## Specifica

Questa integrazione è stata costruita dal seguente requisito consolidato:

- Il relay è a monte della lampadina smart (in serie) e deve restare sempre acceso per mantenerla alimentata e raggiungibile.
- Lo stato desiderato è determinato dalla luminosità ambientale con isteresi fissa ±5 lux e debounce configurabile.
- Il ripristino è immediato (senza debounce) quando un utente cambia accidentalmente relay o lampadina.
- L'override manuale tramite `input_boolean` disabilita completamente l'automazione; il ritorno a OFF scatena una rivalutazione immediata senza debounce.
- Il polling periodico funge da rete di sicurezza, rispettando il debounce per la valutazione lux.

## Licenza

MIT
