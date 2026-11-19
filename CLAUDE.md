# UK CanSat 2026–27 – project context

Team of 4–6 students (aged 18) entering the UK CanSat competition (ESERO-UK / STEM Learning, on behalf of ESA). This file is the shared context for Claude Code. Read it before doing anything in this repo.

## House style
- Use en dashes (–), never em dashes (—), in all prose, comments and docs.
- Prefer surgical changes over rewrites.
- Testing: targeted tests for the physics and maths only – don't write exhaustive test suites.
- Python 3.11+, no compilation steps. Keep dependencies light (numpy, scipy, matplotlib; pyyaml only if needed).
- Report anonymity: never put student names in generated report material – use "Student 1", "Student 2", etc.
- Any AI-generated text, code or figures used in competition reports must be referenced (tool name and date). Note this in generated outputs where relevant.

## Competition rules (from the official requirements doc)
- All components must fit inside a standard soda can: **115 mm height, 66 mm diameter** (parachute excepted).
- Radio/GPS antennas may be mounted externally on the **top or bottom only**, max **30 mm** long. Nothing may extend beyond the can's diameter until it has left the rocket.
- **Mass: 300–350 g.** Lighter CanSats must carry ballast up to 300 g.
- Must run for **3 continuous hours** on battery. Battery must be easily accessible. Must have an easily accessible **master power switch**.
- Solar panel optional, cannot replace the battery.
- Recovery system (parachute) must be reusable; bright fabric recommended. Motorised drones/paragliders forbidden.
- Parachute connection must withstand **50 N** and must be tested.
- Descent rate: **10–15 m/s recommended, minimum 10 m/s.** The launch provider checks parachutes and will swap incorrectly sized ones.
- Must withstand **20 g** launch acceleration.
- Budget: **≤ £400** (ground support equipment excluded). We do not have the £50 kit.
- Radio frequency must be changeable in software and within UK regulations (433 MHz band, keep transmit power to 10 dBm / 10 mW ERP).
- Primary mission (compulsory): after release and during descent, measure **air temperature and air pressure** and transmit as telemetry **once every second** to the ground station.
- Real flight: launched to a few hundred metres, so descent lasts roughly **20–40 s** at 10–15 m/s.

## PDR (Preliminary Design Review) report
8 pages max (excluding cover), optional 10-page appendix, submitted as PDF. Sections: Team & Mission (roles, missions), Software Design (languages, libraries, block diagram, indicative code), Project Planning (6–8 milestones, team skills, top 3 risks), CanSat Design & Initial Build (mechanical, electrical, landing & recovery with parachute sizing calc, ground support equipment), Testing (own tests with pass criteria), Outreach.

## Mission

**Framing:** a mini planetary descent probe demonstrating compact atmospheric-optics instruments. Analogues: ESA Huygens (DISR + HASI measured spectral light, temperature and pressure under a parachute on Titan), Perseverance MEDA (UV, light and dust on Mars), Sentinel-5P (UV, aerosols). A CanSat is "a simulation of a real satellite" in the sense of having real satellite subsystems.

**Overall objective:** investigate how atmospheric conditions affect the light passing through the atmosphere, by measuring it at every height as the CanSat falls.

**Primary mission (upgraded):** temperature and pressure telemetry every second, plus: altitude from the hypsometric equation using measured temperature, lapse-rate profile (look for inversions/stable layers), descent rate and parachute drag coefficient from pressure data.

**Secondary mission (official wording, Nov 2026):** after release and during descent, investigate atmospheric optical properties by measuring spectral light intensity across multiple wavelengths and monitoring ultraviolet radiation. Aim: investigate how atmospheric conditions influence the scattering, attenuation and absorption of light, demonstrating measurement techniques applicable to atmospheric research on other planets.

Quantities and planned rates. The competition minimum is 1 Hz; we **log faster to flash** (full rate only after launch detection, binary format) and **transmit telemetry at 1 Hz**. Rates are a starting point – adjust after bench tests.

| Quantity | Sensor | Log rate | Reason |
|---|---|---|---|
| Air pressure (primary) | BMP388 | ~25 Hz | canopy opening dynamics, descent rate, Cd |
| Air temperature, relative humidity (primary) | SHT45 | ~5 Hz | sensor lag ~2 s (T) / ~4 s (RH) – average noise, lag-correct |
| Spectral light intensity, multiple wavelength bands | AS7341 (1×, facing up) | ~5 Hz | ~7 samples per ~1.4 s swing (swing scanner) |
| UV radiation intensity | LTR390 (UV mode) | ~2 Hz | UV needs ~100 ms integration |
| Ambient visible light intensity | LTR390 (ALS mode, alternating with UV) | ~2 Hz | |
| Absolute orientation (tilt + heading) | BNO085 | 100 Hz | tilt correction of the light data |
| 3-axis angular velocity and acceleration | LSM6DSO32 | 104 Hz (FIFO) | launch detection, 20 g peak, swing |
| GPS position and altitude | ATGM336H | 1 Hz | location, drift/wind (GPS altitude ±10 m) |
| Ground reference: spectral, UV, visible | AS7341 + LTR390 on the ground station | same as flight | separates sky changes from height changes |
| Telemetry packet (LoRa) | SX1262 | 1 Hz | rule; UK 433 MHz band 10 mW ERP and (to confirm, IR 2030) ≤10 % duty cycle. Compulsory T/P plus a downsampled copy of all science (~186 bytes, SF7/500 kHz, ~7 % duty) as the backup if 4G drops |
| Full-rate data (4G) | A7670E LTE Cat-1 | all streams at full rate | **assume the CanSat is not recovered** – everything is sent live over 4G (~3.4 KB/s ≈ 35 kbps with overhead, ~4 MB per flight); write to flash first, send from the buffer, resend after signal drops (in the rocket, after landing); UDP or MQTT with sequence numbers |

Data volume: the 4G stream is the primary science copy, the LoRa packet the backup. Flash (send buffer, bonus copy if recovered): ~3 KB/s binary at full rate → ~2 MB per 10 min; tight on Pico 2 flash alongside CircuitPython, so full rate only after launch detection; microSD optional insurance.

Why each measurement:
- **Spectral intensity (most important):** how each wavelength band changes during descent → wavelength-dependent scattering and attenuation, relevant to aerosols, clouds and haze on other planets. Blue should be affected more than red (Rayleigh scattering).
- **UV:** planetary atmospheres absorb UV to different degrees → atmospheric shielding and surface radiation environments.
- **Temperature and humidity:** context for optical changes (haze trapped under inversions, aerosol swelling in humid air).
- **IMU:** movement and orientation, to account for sensor pointing during descent.
- **GPS:** ties optical readings to location, altitude and flight conditions.

**Measurement method ("package 2", chosen Nov 2026):** the effect we want is small – over a 400 m descent the blue/red ratio should change by only ~1–2 % (Rayleigh ~1 % in blue, haze ~2–6 %), while a 5° tilt towards the sun changes raw readings by ~±10 %. So:
1. **Colour ratios** (e.g. blue/red) are the main result – tilt and clouds largely cancel.
2. **Swing reduced at source:** spill hole, line length, swivel (see the `cansat_design` swing sweep).
3. **Tilt correction:** BNO085 orientation + sun position (GPS time/location) → angle between sensor and sun; only nearly-level samples used where needed.
4. **Direct/diffuse split per band:** block the sun with a small disc at the pad (diffuse only) before launch.
5. **Bench calibration** of the sensor's angular (cosine) response with the PTFE diffuser.
6. **Ground reference station:** identical AS7341 + LTR390 logging on the ground, time-aligned via telemetry packets.
7. **Canopy shading:** canopy covers ~10° half-angle above the sensors (~3–6 % of diffuse light, orange tints it) – measure on the ground per band and correct; it cannot shadow the sun unless swing exceeds ~27° (April final, midday). Sensor window off-centre on the top cap; radio antenna on the bottom.
Expected accuracy (estimates, to be confirmed by simulation): colour ratio ±0.3–0.6 %, raw intensity ±2–4 %. Package 3 (DIY sun sensor) rejected for now – small extra accuracy for a lot of work; possible later showcase.

**Success criteria:**
- Minimum: spectral, UV and orientation data logged for the whole descent at ≥1 Hz and telemetry received at 1 Hz.
- Full: blue/red ratio vs height with uncertainty ≤ ±0.5 %, compared with a Rayleigh + haze prediction.
- Extended: any of – direct/diffuse split from the swing ("swing scanner"), haze Ångström exponent, solar-heating correction of the SHT45, measured swing vs the `cansat_design` swing model, post-landing sky/UV readings.

**What we do with the data:**
1. Intensity per wavelength band at each height; plot vs height per band.
2. Band ratios (e.g. blue/red) and UV/visible ratio vs height → wavelength-dependent attenuation.
3. Explain changes with temperature/humidity layers.
4. Correct for tilt (BNO085 + sun position + direct/diffuse split) and compare with the ground reference.
5. Validate: pad and post-landing readings, Met Office radiosonde soundings, ERA5, CAMS aerosol forecasts.

**How the missions link:** optical changes vs temperature/humidity layers from the primary-mission profile; humidity explains haze scattering; light sensors estimate solar heating error on the temperature sensor; one combined telemetry stream.

**Known limitations (state in reports):** 20–40 s descent over a few hundred metres, so changes may be small and may not cross a layer boundary (a flat profile is still a valid result); parachute swing changes sensor pointing – reduced with IMU data, not removed; depends on weather and sun position; one flight demonstrates the method, not a definitive dataset.

**Open points:** AS7341 points up (assumed – confirm); LTR390 alternates UV/ALS modes in firmware; **firmware language: CircuitPython provisionally** (official Adafruit drivers for every sensor) – first confirm the `micropySX126X` radio driver works in CircuitPython on the Pico 2, otherwise MicroPython; the secondary-mission text above must be rewritten in our own words for reports (an older team's PDR uses very similar headings and phrasing).

## Hardware (solderless build, £219.13 flight incl. 4G and fast shipping + £45.34 ground station – parts sheet, 19 Nov 2026)
- Raspberry Pi Pico 2 with headers (flight computer, MicroPython or CircuitPython)
- Waveshare SX1262 433 MHz LoRa module for Pico (includes 600 mAh LiPo, charger, power switch = master switch). Note: SX1262, not SX127x – needs an SX126x driver.
- Pimoroni Pico Omnibus (holds Pico + LoRa module, spare pins). 94 × 52 mm, mounts lengthwise.
- 433 MHz IPEX spring antenna (≤30 mm external) – mounted on the **bottom** so the top cap stays clear for the light sensors
- 1× Adafruit AS7341 (STEMMA QT, 10 channels, 415 nm to NIR) – I2C address 0x39
- Adafruit LTR390 UV + ambient light (STEMMA QT)
- Adafruit SHT45 temperature + humidity (STEMMA QT) – primary air temperature sensor
- Adafruit BMP388 pressure (STEMMA QT) – primary pressure sensor (BME280 considered as an alternative/backup)
- Adafruit LSM6DSO32 IMU (6-DoF: accelerometer ±32 g + gyroscope, no magnetometer) – launch/landing detection, 20 g peak, swing
- Adafruit BNO085 9-DoF orientation sensor with on-chip fusion (STEMMA QT, I2C 0x4A, £27 at Pi Hut – often sold out) – absolute orientation for tilt correction; ±8 g only, so the LSM6DSO32 stays. I2C can be fiddly on some boards – UART-RVC mode is the fallback.
- ATGM336H GPS (UART) – recovery and wind profile from drift
- STEMMA QT cables + 1× STEMMA QT-to-female-socket lead (one sensor chain); female jumpers for GPS
- PTFE 1 mm diffuser over sensor windows (passes UV)
- **4G bulk link (Nov 2026): Waveshare A7670E LTE Cat-1 HAT** (65 × 30.5 mm, wired to the Pico with jumpers; Pi Hut sold out 19 Nov) (UART, power-key pin; 2G fallback turned off) – normal 4G network, so a cheap **pay-as-you-go SIM** for the CanSat works (not a student's own SIM; disable the PIN, set the APN). ~1 A transmit bursts → **1000 µF capacitor** on its supply and a brown-out test with the Pico; the 600 mAh LiPo's peak current must be confirmed. **Flexible FPC LTE antenna inside the PETG shell wall** (the 30 mm rule covers external antennas only). Check coverage at the launch site and that the organisers accept a cellular module. Its own UART – the GPS takes the other one; check pins against the LoRa board. SIM7080G (LTE-M) rejected: phone/PAYG SIMs usually can't use LTE-M.
- Data logged to Pico flash (full rate after launch detection) as the 4G send buffer; SD module optional
- Orange ripstop nylon canopy, ball-bearing swivel, 3D-printed PETG shell, ballast to 300–350 g
- Ground station: second Pico 2 + SX1262 module on a laptop over USB, plus the **ground reference** AS7341 + LTR390 (~£22, ground support equipment – excluded from the £400 budget, to confirm)
- Secure every plug-in connector (hot glue/tape) for 20 g.

## Parachute design plan
- Sizing: drag = weight at terminal velocity → A = 2mg / (ρ·Cd·v²). Baseline: m = 0.325 kg, v = 12 m/s, Cd ≈ 0.8 (flat hexagon), ρ = 1.225 kg/m³ → A ≈ 0.045 m², hexagon side ≈ 13 cm, ≈ 23 cm across flats.
- Spill hole 15–20% of canopy width to reduce swing (important for the light sensors); enlarge canopy slightly to compensate.
- Shroud lines 1–1.5× canopy width, one per corner, swivel to stop spin. Cruciform canopy is a lower-swing alternative.
- Tests: 5 kg hang test (50 N); drop tests from ≥10 m with a 325 g dummy, filmed and analysed in Tracker; adjust size until 10–15 m/s.
- Software: Python (sizing + descent model), OpenRocket (cross-check), ANSYS Student Fluent or SimScale (rigid-canopy CFD to compare spill holes and shapes – comparison, not ground truth), Inkscape/Fusion 360 (patterns), Fusion 360 FEA (shell under 20 g, mount under 50 N), Tracker (drop-test video analysis).
