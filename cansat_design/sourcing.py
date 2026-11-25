"""Supplier metadata, checked 16 Nov 2026. Prices always come from Config.
Amazon links are searches, not verified product listings. This module has no
third-party dependencies, allowing parts and exports to load before Pyodide.
"""
import json
from dataclasses import asdict
from urllib.parse import quote_plus
from .config import Config

HUT = "https://thepihut.com/products/"
RADIO = HUT + "sx1262-433mhz-lora-node-module-for-raspberry-pi-pico"
SOURCES = [
    ("Raspberry Pi Pico 2", "Raspberry Pi Pico 2 soldered headers", HUT + "raspberry-pi-pico-2", "The Pi Hut", "Select the pre-soldered headers option; Pico 2, not the original Pico."),
    ("SX1262", "Waveshare Pico SX1262 433MHz", RADIO, "The Pi Hut", "Choose the Pico 433 MHz board, not 868/915 MHz. Confirm the supplied battery and antenna."),
    ("600 mAh", "3.7V 600mAh LiPo battery JST", RADIO, "LoRa kit contents", "Budgeted as included with the LoRa kit. Confirm bundle, connector polarity and peak-current rating."),
    ("Pico Omnibus", "Pimoroni Pico Omnibus PIM556", "https://shop.pimoroni.com/products/pico-omnibus", "Pimoroni", "Dual expander; Pico sold separately."),
    ("433 MHz IPEX", "433MHz IPEX U.FL spring antenna", None, "", "Check connector and external length against the design. Budget is for a pack."),
    ("AS7341", "Adafruit AS7341 STEMMA QT 4698", HUT + "adafruit-as7341-10-channel-light-color-sensor-breakout", "The Pi Hut", "Adafruit STEMMA QT board (ADA4698); cable sold separately."),
    ("LTR390", "Adafruit LTR390 STEMMA QT 4831", HUT + "adafruit-ltr390-uv-light-sensor-stemma-qt-qwiic", "The Pi Hut", "Adafruit STEMMA QT board (ADA4831); cable sold separately."),
    ("SHT45", "Adafruit SHT45 STEMMA QT 5665", HUT + "adafruit-sensirion-sht45-precision-temperature-humidity-sensor-stemma-qt-qwiic", "The Pi Hut", "Choose the intended PTFE/no-PTFE variant. Breakout, not USB Trinkey."),
    ("BMP388", "Adafruit BMP388 STEMMA QT 3966", HUT + "adafruit-bmp388-precision-barometric-pressure-and-altimeter-ada3966", "The Pi Hut", "Adafruit STEMMA QT revision (ADA3966), not a different manufacturer's board."),
    ("LSM6DSO32", "Adafruit LSM6DSO32 4692", HUT + "adafruit-lsm6dso32-6-dof-accelerometer-and-gyroscope", "The Pi Hut", "LSM6DSO32 for the planned acceleration range; cable sold separately."),
    ("BNO085", "Adafruit BNO085 STEMMA QT 4754", HUT + "adafruit-9-dof-orientation-imu-fusion-breakout-bno085-bno080-stemma-qt-qwiic", "The Pi Hut", "Adafruit BNO085 (ADA4754), not BNO055. Check current stock."),
    ("ATGM336H", "ATGM336H GPS UART module patch antenna", None, "", "Exact breakout not selected. Check UART voltage, antenna, dimensions and headers."),
    ("STEMMA QT cables", "STEMMA QT Qwiic JST SH 4 pin cable female jumper", None, "", "Seven leads in the mass model; line cost covers the cable bundle. Check lengths and connector genders."),
    ("STEMMA QT to female", "STEMMA QT Qwiic female socket cable", None, "", "Ground receiver lead; choose female sockets for the Pico headers."),
    ("PTFE", "PTFE sheet 1mm white", None, "", "Material for two diffuser windows; verify optical transmission by calibration."),
    ("PETG shell", "PETG filament 1.75mm", None, "", "Custom school-printed shell and bulkheads. Link is for filament, not a finished part; £0 assumes school stock."),
    ("Fasteners", "M2 screws nuts nylon hot glue tape", None, "", "Workshop consumables; £0 assumes existing stock. Add a budget if buying new."),
    ("A7670E", "Waveshare A7670E Cat-1 HAT", HUT + "a7670e-lte-cat-1-hat-for-raspberry-pi-2g-gsm-gprs", "The Pi Hut", "Sold out at Pi Hut on 19 Nov – use Notify me. Wire its UART, power-key and power to the Pico; turn 2G off."),
    ("LTE FPC", "SparkFun WRL-17841 LTE FPC antenna", "https://proto-pic.co.uk/product/antenna-wide-band-4g-lte-internal-lora-wrl-17841", "Proto-Pic", "u.FL, 53 × 24 mm, sticks inside the shell wall. Check it matches the HAT's antenna socket."),
    ("U3V40F5", "Pololu U3V40F5 5V step-up regulator", HUT + "5v-step-up-voltage-regulator-u3v40f5", "The Pi Hut", "5 V out from 1.3–5 V in, ~4 A input, 15 × 15 mm, 1.5 g. No short-circuit protection; gets hot under load. Feed from VSYS after the master switch."),
    ("1000", "1000uF low ESR electrolytic capacitor 6.3V", None, "", "Check voltage rating, polarity, dimensions and ESR for the modem supply."),
    ("microSD breakout", "Adafruit micro SD breakout 3V 4682", HUT + "adafruit-micro-sd-spi-or-sdio-card-breakout-board-3v-only", "The Pi Hut", "3 V only (fine for the Pico). Wire to SPI0: GP16–GP19. MicroPython sdcard driver."),
    ("microSD card", "microSD card 16GB", None, "", "Any 8–16 GB card, FAT32. A branded or industrial card copes better with cold and vibration."),
    ("PAYG SIM", "giffgaff SIM", "https://www.giffgaff.com/", "giffgaff", "Free SIM, ~£6 2 GB goodybag. Turn the PIN off, set the APN; check launch-site coverage."),
    ("shipping", "", "https://thepihut.com/pages/delivery", "Pi Hut delivery", "Pi Hut DHL next day £9.99 + Amazon ~£4.99 (free with Prime) + Proto-Pic ~£5 – confirm at checkout."),
]

def supplier_info(name):
    query, url, label, note = name, None, "", "Check the exact part and dimensions before ordering."
    for fragment, q, u, l, n in SOURCES:
        if fragment in name:
            query, url, label, note = q, u, l, n
            break
    links = [{"label": "Amazon search", "url": "https://www.amazon.co.uk/s?k=" + quote_plus(query), "kind": "search"}] if query else []
    if url:
        links.append({"label": label, "url": url, "kind": "product"})
    elif "STEMMA" in name:
        links.append({"label": "Pi Hut search", "url": "https://thepihut.com/search?type=product&q=" + quote_plus(query), "kind": "search"})
    return {"links": links, "note": note}

def parts_catalog(cfg=None):
    cfg = cfg or Config()
    rows = []
    for group, components in [("Flight", cfg.components), ("Ground", cfg.ground)]:
        for c in components:
            rows.append({**asdict(c), "id": group + ":" + c.name, "group": group, **supplier_info(c.name)})
    rows.append({"id": "Materials:parachute", "name": "Parachute materials bundle", "group": "Materials",
                 "qty": 1, "cost_gbp": cfg.parachute.materials_cost_gbp, "mass_g": None, "estimate": True,
                 "note": "One budget for ripstop, swivel, cord and reinforcement. Original allowance: £6.99 fabric + £4.58 swivel pack; confirm any extra cord/thread cost. Mass comes from canopy geometry.",
                 "links": [{"label": label + " search", "url": "https://www.amazon.co.uk/s?k=" + quote_plus(query), "kind": "search"}
                           for label, query in [("Amazon ripstop", "orange ripstop nylon fabric 40gsm"),
                                                ("Amazon swivel", "ball bearing fishing swivels"),
                                                ("Amazon cord", "lightweight braided nylon cord")]]})
    return {"rows": rows, "budget_gbp": cfg.mass.budget_gbp, "links_checked": "2026-11-16",
            "price_note": "Editable planning allowances from the project config, not live supplier quotes. Line budgets include packs and are not multiplied by quantity. Fast UK shipping is included as its own line."}

if __name__ == "__main__":
    print(json.dumps(parts_catalog(), ensure_ascii=True, indent=2))
