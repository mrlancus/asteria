"""Draws the PDR system block diagram and software flow diagram as SVG.
Run: python docs/diagrams/make_diagrams.py   (PNG copies are rendered separately)"""
from pathlib import Path

OUT = Path(__file__).parent
FONT = "Arial, Helvetica, sans-serif"
C = {  # fill, stroke
    "power": ("#fde8e8", "#c62b2b"), "obc": ("#e8eefb", "#2a5bb8"), "primary": ("#fff0e0", "#d9731a"),
    "secondary": ("#e3f6ec", "#1b8f5a"), "attitude": ("#e8f1fb", "#2a78d6"), "comms": ("#f1e9fb", "#7442b8"),
    "nav": ("#eef6f8", "#0f8fa3"), "mech": ("#f0f0ee", "#6b6a64"), "ground": ("#f7f7f5", "#52514e"),
}
DATA, POWER, RADIO, MECH = "#2a5bb8", "#c62b2b", "#7442b8", "#6b6a64"


class Svg:
    def __init__(self, w, h):
        self.w, self.h, self.els = w, h, []

    def box(self, x, y, w, h, lines, kind, bold_first=True, r=8, size=13):
        f, s = C[kind]
        self.els.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{f}" stroke="{s}" stroke-width="1.6"/>')
        n = len(lines)
        y0 = y + h / 2 - (n - 1) * (size + 3) / 2 + size * 0.35
        for i, t in enumerate(lines):
            wt = "bold" if (i == 0 and bold_first) else "normal"
            sz = size if i == 0 else size - 2
            col = "#111" if i == 0 else "#444"
            self.text(x + w / 2, y0 + i * (size + 3), t, sz, wt, "middle", col)

    def group(self, x, y, w, h, label, colour="#9a9994", dash="6,4"):
        self.els.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="none" stroke="{colour}" '
                        f'stroke-width="1.4" stroke-dasharray="{dash}"/>')
        self.text(x + 12, y + 20, label, 13, "bold", "start", colour)

    def text(self, x, y, t, size=12, weight="normal", anchor="start", colour="#222"):
        t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.els.append(f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
                        f'text-anchor="{anchor}" fill="{colour}">{t}</text>')

    def line(self, pts, colour, width=2, dash=None, arrow_end=True, arrow_start=False, label=None, lpos=None,
             lsize=11, lanchor="middle"):
        d = "M " + " L ".join(f"{x},{y}" for x, y in pts)
        da = f' stroke-dasharray="{dash}"' if dash else ""
        mk = colour.strip("#")
        me = f' marker-end="url(#a{mk})"' if arrow_end else ""
        ms = f' marker-start="url(#s{mk})"' if arrow_start else ""
        self.els.append(f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="{width}"{da}{me}{ms}/>')
        if label:
            x, y = lpos
            self.els.append(f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{lsize}" text-anchor="{lanchor}" '
                            f'fill="{colour}" font-weight="bold" paint-order="stroke" stroke="#fff" stroke-width="4">{label}</text>')

    def save(self, name, title):
        defs = "".join(
            f'<marker id="a{c.strip("#")}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>'
            f'<marker id="s{c.strip("#")}" viewBox="0 0 10 10" refX="1" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
            f'<path d="M10,0 L0,5 L10,10 z" fill="{c}"/></marker>' for c in (DATA, POWER, RADIO, MECH))
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">'
               f'<title>{title}</title><defs>{defs}</defs><rect width="100%" height="100%" fill="#ffffff"/>'
               + "\n".join(self.els) + "</svg>")
        (OUT / name).write_text(svg, encoding="utf-8")


def legend(s, x, y, items):
    for i, (kind, label) in enumerate(items):
        xx = x + i * 175
        if kind in C:
            f, st = C[kind]
            s.els.append(f'<rect x="{xx}" y="{y - 11}" width="22" height="14" rx="3" fill="{f}" stroke="{st}" stroke-width="1.4"/>')
        else:
            colour, dash = kind
            s.line([(xx, y - 4), (xx + 24, y - 4)], colour, 2.4, dash, arrow_end=False)
        s.text(xx + 30, y, label, 12)


# ------------------------------------------------------------------ system block diagram
def system():
    s = Svg(1700, 1100)
    s.text(20, 34, "Asteria CanSat – system block diagram", 22, "bold")
    s.text(20, 56, "UK CanSat 2026–27 · atmospheric optics descent probe", 13, "normal", "start", "#555")

    s.group(20, 75, 1150, 905, "CANSAT (inside a 115 × 66 mm can, 300–350 g)", "#333", "0")
    s.group(1215, 75, 465, 905, "GROUND SEGMENT (not in the £400 budget)", "#333", "0")

    # Power
    s.group(40, 105, 360, 250, "Power")
    s.box(60, 140, 150, 70, ["LiPo battery", "3.7 V, 600 mAh"], "power")
    s.box(230, 140, 150, 70, ["Charger + regulator", "Waveshare LoRa board"], "power")
    s.box(60, 260, 150, 70, ["Master switch", "easy to reach"], "power")
    s.box(230, 260, 150, 70, ["3.3 V rail", "Pico + sensors"], "power")
    s.line([(210, 175), (230, 175)], POWER)
    s.line([(305, 210), (305, 235), (135, 235), (135, 260)], POWER)
    s.line([(210, 295), (230, 295)], POWER)

    # Computer
    s.box(450, 330, 250, 120, ["Raspberry Pi Pico 2", "RP2350 on-board computer", "CircuitPython", "launch / landing detection"], "obc", size=15)
    s.box(495, 495, 145, 75, ["Flash log", "full rate, binary", "= 4G send buffer"], "obc")
    s.line([(567, 450), (567, 495)], DATA, arrow_start=True)
    s.line([(380, 295), (420, 295), (420, 360), (450, 360)], POWER, label="3.3 V", lpos=(425, 330), lanchor="start")

    # Sensors on the I2C chain
    s.group(740, 105, 410, 585, "Sensors – one I²C chain (STEMMA QT)")
    bus_x = 770
    s.line([(bus_x, 160), (bus_x, 605)], DATA, 3, arrow_end=False)
    rows = [
        (155, "primary", ["BMP388 – air pressure", "primary · I²C 0x77"]),
        (220, "primary", ["SHT45 – air temperature + humidity", "primary · I²C 0x44"]),
        (315, "secondary", ["AS7341 – spectral light, 10 bands", "secondary · faces up · I²C 0x39"]),
        (380, "secondary", ["LTR390 – UV + visible light", "secondary · I²C 0x53"]),
        (485, "attitude", ["BNO085 – absolute orientation", "tilt correction · I²C 0x4A"]),
        (550, "attitude", ["LSM6DSO32 – accel ±32 g + gyro", "launch/landing, swing · I²C 0x6A"]),
    ]
    for y, kind, lines in rows:
        s.box(800, y, 330, 55, lines, kind, size=13)
        s.line([(bus_x, y + 27), (800, y + 27)], DATA, 2, arrow_end=False)
    s.text(800, 148, "Primary mission", 11, "bold", "start", C["primary"][1])
    s.text(800, 308, "Secondary mission", 11, "bold", "start", C["secondary"][1])
    s.text(800, 478, "Orientation and motion", 11, "bold", "start", C["attitude"][1])
    s.text(800, 640, "PTFE diffuser over the light sensors", 11, "normal", "start", "#555")
    s.text(800, 658, "3.3 V to every sensor through the chain", 11, "normal", "start", POWER)
    s.line([(700, 375), (bus_x, 375)], DATA, 2.4, arrow_end=False, label="I²C", lpos=(735, 368))

    # GPS
    s.box(800, 715, 330, 64, ["ATGM336H GPS + patch antenna", "position, time (UTC), altitude"], "nav")
    s.line([(700, 420), (725, 420), (725, 747), (800, 747)], DATA, arrow_start=True, label="UART 0", lpos=(730, 705), lanchor="start")

    # Comms
    s.group(40, 600, 660, 230, "Communications")
    s.box(60, 640, 290, 74, ["SX1262 LoRa radio, 433 MHz", "10 mW · 1 Hz telemetry (T, P", "+ backup copy of all science)"], "comms")
    s.box(380, 640, 300, 74, ["A7670E 4G LTE (Cat-1)", "full-rate data, sent live", "1000 µF capacitor on supply"], "comms")
    s.box(60, 750, 290, 56, ["433 MHz spring antenna", "≤ 30 mm, bottom of the can"], "comms")
    s.box(380, 750, 300, 56, ["Flexible LTE antenna", "inside the PETG shell wall"], "comms")
    s.line([(205, 714), (205, 750)], RADIO, 2, arrow_end=False)
    s.line([(530, 714), (530, 750)], RADIO, 2, arrow_end=False)
    s.line([(470, 450), (470, 590), (205, 590), (205, 640)], DATA, arrow_start=True, label="SPI", lpos=(300, 584))
    s.line([(665, 450), (665, 640)], DATA, arrow_start=True, label="UART 1 + power key", lpos=(560, 625), lanchor="start")
    s.line([(135, 330), (135, 360), (30, 360), (30, 732), (365, 732), (365, 700), (380, 700)], POWER,
           label="3.7 V battery (bursts ~1 A)", lpos=(212, 745), lsize=10.5, lanchor="start")

    # Recovery
    s.box(60, 895, 640, 60, ["Recovery: parachute (ripstop nylon, spill hole) → snap swivel → eye bolt in the top cap",
                             "mechanical only · connection tested to 50 N · 10–15 m/s descent"], "mech")
    s.box(800, 895, 330, 60, ["Ballast", "steel washers to reach 300–350 g"], "mech")

    # Ground segment
    s.box(1240, 140, 420, 74, ["Ground receiver", "Pico 2 + SX1262 LoRa, 433 MHz"], "comms")
    s.box(1240, 270, 250, 74, ["Ground reference", "AS7341 + LTR390", "(same as on the CanSat)"], "secondary")
    s.box(1240, 420, 420, 90, ["Laptop", "live display, logging, Python analysis", "(tilt correction, colour ratios, plots)"], "ground")
    s.box(1240, 600, 420, 74, ["Internet server", "receives 4G data (UDP / MQTT)"], "ground")
    s.box(1240, 730, 420, 74, ["Mobile network", "pay-as-you-go SIM in the CanSat"], "ground")
    s.line([(1365, 270), (1365, 214)], DATA, label="I²C", lpos=(1395, 248))
    s.line([(1580, 214), (1580, 420)], DATA, label="USB", lpos=(1610, 320))
    s.line([(1450, 600), (1450, 510)], DATA, label="internet", lpos=(1490, 560))
    s.line([(1450, 730), (1450, 674)], DATA)

    # Radio links across the boundary
    s.line([(205, 806), (205, 845), (1185, 845), (1185, 177), (1240, 177)], RADIO, 2.4, "8,6",
           label="433 MHz LoRa · 1 packet/s", lpos=(980, 838))
    s.line([(530, 806), (530, 872), (1200, 872), (1200, 767), (1240, 767)], RADIO, 2.4, "8,6",
           label="4G LTE · full-rate data (~35 kbps)", lpos=(980, 888))

    legend(s, 20, 1015, [((DATA, None), "Data"), ((POWER, None), "Power"), ((RADIO, "8,6"), "Radio link"),
                         ("primary", "Primary mission"), ("secondary", "Secondary mission"), ("attitude", "Orientation"),
                         ("comms", "Communications"), ("mech", "Mechanical")])
    s.text(20, 1060, "I²C addresses are board defaults – check against each datasheet. Diagram drawn with Claude Code (Anthropic), "
                     "Nov 2026 – reference as AI-assisted.", 11, "normal", "start", "#666")
    s.save("system_block_diagram.svg", "Asteria CanSat system block diagram")


# ------------------------------------------------------------------ software flow
def software():
    s = Svg(1700, 900)
    s.text(20, 34, "Asteria CanSat – flight software (state machine and main loop)", 22, "bold")
    s.text(20, 56, "CircuitPython on the Pico 2 · thresholds are starting values, tuned in bench and drop tests", 13, "normal", "start", "#555")

    s.group(20, 75, 1660, 330, "Flight states", "#333", "0")
    states = [
        (40, ["1. Start-up", "init sensors, radio, 4G", "self-test, log errors"], "obc"),
        (365, ["2. On the pad", "log + telemetry at 1 Hz", "4G connects, ground ref."], "obc"),
        (690, ["3. Launch / ascent", "full-rate logging", "(inside the rocket)"], "nav"),
        (1015, ["4. Descent", "full-rate logging, 1 Hz LoRa", "4G streams from buffer"], "secondary"),
        (1340, ["5. Landed", "keep sending the buffer", "beacon for recovery"], "comms"),
    ]
    for x, lines, kind in states:
        s.box(x, 120, 300, 110, lines, kind, size=16)
    trans = ["self-test done", "accel > ~3 g for 0.2 s", "pressure rising (falling",
             "still + pressure steady 5 s"]
    trans2 = ["", "(launch detected)", "height) after apogee", "(landing detected)"]
    for i, (a, b) in enumerate(zip(trans, trans2)):
        x0 = 40 + i * 325 + 300
        s.line([(x0, 175), (x0 + 25, 175)], DATA, 2.4)
        s.text(x0 + 12, 262, a, 11.5, "bold", "middle", DATA)
        s.text(x0 + 12, 278, b, 11.5, "normal", "middle", DATA)
    s.text(40, 330, "In every state: watchdog timer restarts the Pico if the code hangs; a failed sensor is logged and skipped, "
                    "the others keep running.", 13, "normal", "start", "#333")
    s.text(40, 352, "Timeout back-ups: if launch is missed, switch to full rate on a fall in pressure; if landing is missed, "
                    "after 10 minutes.", 13, "normal", "start", "#333")
    s.text(40, 374, "Telemetry once a second from power-on to the end – the compulsory primary mission (T and P).",
           13, "bold", "start", C["primary"][1])

    s.group(20, 425, 1660, 400, "Main loop (each pass ~5 ms; every sensor read on its own schedule)", "#333", "0")
    steps = [
        (40, ["Read sensors when due", "BMP388 25 Hz · SHT45 5 Hz", "AS7341 5 Hz · LTR390 2 Hz", "BNO085 100 Hz · LSM6DSO32 104 Hz", "GPS 1 Hz"], "primary"),
        (370, ["Timestamp + pack", "ms since boot + GPS time", "binary records"], "obc"),
        (700, ["Write to flash", "full rate after launch", "= the 4G send buffer"], "obc"),
        (1030, ["Every 1 s: LoRa packet", "T, P + 1 s means of all", "science · sequence number"], "comms"),
        (1360, ["4G sender", "sends unsent records", "resends after drop-outs"], "comms"),
    ]
    for x, lines, kind in steps:
        s.box(x, 480, 300, 150, lines, kind, size=15)
    for i in range(4):
        x0 = 40 + i * 330 + 300
        s.line([(x0, 555), (x0 + 30, 555)], DATA, 2.4)
    s.line([(1510, 630), (1510, 700), (190, 700), (190, 630)], DATA, 2, "5,4", label="repeat", lpos=(850, 694))
    s.text(40, 745, "On the ground (Python on the laptop): decode LoRa + 4G packets → merge by sequence number → "
                    "plots vs height → tilt correction (BNO085 + sun position)", 13, "normal", "start", "#333")
    s.text(40, 767, "→ colour ratios (blue/red) and UV/visible vs height → compare with the ground reference station "
                    "and a Rayleigh + haze prediction.", 13, "normal", "start", "#333")
    s.text(40, 800, "Libraries: adafruit_bmp3xx, adafruit_sht4x, adafruit_as7341, adafruit_ltr390, adafruit_bno08x, "
                    "adafruit_lsm6ds, adafruit_gps, SX126x driver (to confirm), A7670E AT commands over UART.",
           12, "normal", "start", "#555")

    legend(s, 20, 855, [("primary", "Sensors"), ("obc", "Processing / storage"), ("nav", "Launch phase"),
                        ("secondary", "Descent (science)"), ("comms", "Communications")])
    s.text(20, 885, "Diagram drawn with Claude Code (Anthropic), Nov 2026 – reference as AI-assisted.", 11, "normal", "start", "#666")
    s.save("software_flow.svg", "Asteria CanSat flight software flow")


if __name__ == "__main__":
    system()
    software()
    print("wrote", *sorted(p.name for p in OUT.glob("*.svg")))
