# Flight computer pin map (Pico 2)

Proposed 25 Nov 2026 – wire it up on the bench and confirm before the final build. Generated with Claude Code (Anthropic), 25 Nov 2026.

The Waveshare SX1262 LoRa board fixes seven pins (from Waveshare's Pico-LoRa-SX1262 manual – check them against the 433 MHz board's silkscreen or wiki). Everything else is placed around them. "Pin" is the physical pin number on the Pico (1–40, counted anticlockwise from the USB end, top view). MicroPython code uses the GP numbers, not the physical pins.

## Allocation

| Function | Signal | GP | Pin | Connects to |
|---|---|---|---|---|
| GPS (UART0) | Pico TX | GP0 | 1 | GPS **RX** |
| | Pico RX | GP1 | 2 | GPS **TX** |
| LoRa (fixed) | BUSY | GP2 | 4 | SX1262 board |
| LoRa (fixed) | CS | GP3 | 5 | SX1262 board |
| Sensors (I²C0) | SDA | GP4 | 6 | STEMMA QT blue wire |
| | SCL | GP5 | 7 | STEMMA QT yellow wire |
| 4G (UART1) | Pico TX | GP8 | 11 | HAT header pin 8 (where a Pi's TXD would be) |
| | Pico RX | GP9 | 12 | HAT header pin 10 (where a Pi's RXD would be) |
| LoRa (fixed, SPI1) | SCK | GP10 | 14 | SX1262 board |
| | MOSI | GP11 | 15 | SX1262 board |
| | MISO | GP12 | 16 | SX1262 board |
| 4G | Power key | GP14 | 19 | HAT power-key pin – find it on the A7670E HAT wiki |
| LoRa (fixed) | RESET | GP15 | 20 | SX1262 board |
| LoRa (fixed) | DIO1 (interrupt) | GP20 | 26 | SX1262 board |
| GPS (optional) | PPS (1 pulse per second) | GP21 | 27 | GPS PPS pin, for precise time stamps |

Spare: GP6, GP7, GP13, GP16–GP19, GP22, GP26–GP28 (analogue inputs, e.g. battery voltage through a divider – check the LoRa board doesn't already use one). GP23, GP24, GP25 and GP29 are used inside the Pico board and are not on the header.

## Power

| From | To | Notes |
|---|---|---|
| LiPo → LoRa board master switch | Pico VSYS (pin 39) | Supplied through the LoRa board |
| Pico 3V3 OUT (pin 36) | STEMMA QT red wire, GPS VCC | Sensors + GPS ≈ 40 mA, well under the 300 mA limit |
| Pico GND (e.g. pin 38) | STEMMA QT black wire, GPS GND, HAT GND, boost GND | One common ground |
| VSYS (pin 39) | Pololu U3V40F5 VIN | Taken after the master switch, so the switch also turns the 4G off |
| U3V40F5 VOUT (5 V) | HAT 5 V (header pin 2 or 4) + 1000 µF capacitor | Capacitor across 5 V and GND, close to the HAT, observe polarity |

## Checks before wiring

- **Cross TX and RX.** Pico TX goes to the other device's RX. On the HAT, the Pico's TX goes to the pin a Raspberry Pi would use for *its* TX (pin 8), because the HAT is wired to receive from there.
- **4G HAT jumpers.** Set the logic level to 3.3 V (the Pico is not 5 V tolerant) and route the modem's UART to the 40-pin header, not USB. Check the jumper names on the HAT wiki.
- **Boost converter enable pin.** The U3V40F5's EN pin is pulled up to VIN, so it runs by default – leave it unconnected. Don't rely on EN to cut the 4G power: on many boost converters the input still passes through to the output when disabled (check Pololu's notes). Use the power key to sleep the modem on the pad instead.
- **Current through the master switch.** 4G bursts draw about 1.5 A from the battery through the LoRa board's switch and VSYS. Check the switch rating, and watch for resets during the brown-out test.
- **LoRa board extras.** Confirm the LoRa board uses no other GPIOs (for example a battery-sense pin on GP26–GP29).
