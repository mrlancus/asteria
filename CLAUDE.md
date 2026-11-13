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

**Framing:** a mini planetary descent probe / airborne demonstrator for an Earth-observation instrument. Analogues: ESA Huygens (DISR + HASI measured spectral light, temperature and pressure under a parachute on Titan), Perseverance MEDA, Sentinel-2 and CERES (reflectance/albedo), Sentinel-5P (UV). A CanSat is "a simulation of a real satellite" in the sense of having real satellite subsystems; the mission concept should be valid both from orbit and in the descent test.

**Overall objective:** measure how the atmosphere changes the light that satellites see, by recording it at every height as the CanSat falls.

**Primary mission (upgraded):** temperature and pressure telemetry every second, plus: altitude from the hypsometric equation using measured temperature, lapse-rate profile (look for inversions/stable layers), descent rate and parachute drag coefficient from pressure data.

**Secondary mission:** spectral albedo and atmospheric optics during descent.
- Upward AS7341 (10 channels, 415 nm to NIR) = incoming light reference; downward AS7341 = light reflected from the ground.
- Reflectance = down ÷ up per wavelength → albedo, surface type, rough vegetation index (NIR channel).
- LTR390 measures UV and how cloud/haze changes it.
- As the CanSat falls, there is less air between it and the ground, so the change in reflectance with height directly measures the atmospheric distortion that satellites must correct for (atmospheric correction). Blue should be affected more than red (Rayleigh scattering).

**What we do with the data:**
1. Reflectance per wavelength at each height.
2. Plot reflectance vs height per colour.
3. Explain changes with temperature/humidity layers (haze trapped under inversions, swelling in humid air).
4. Build a simple atmospheric correction model from our own data.
5. Validate: pad and post-landing readings, Met Office radiosonde soundings, ERA5, CAMS aerosol forecasts.

**How the missions link:** light ratios vs temperature/humidity layers; humidity explains haze scattering; upward light sensor estimates solar heating error on the temperature sensor; one combined telemetry stream.

**Known limitations (state in reports):** 20–40 s descent, may not cross a layer boundary (a flat profile is still a valid result); parachute swing reduced using channel ratios + IMU tilt, not removed; depends on weather and sun; one flight demonstrates the method, not a definitive dataset.

## Hardware (solderless build, ~£151 flight + ~£20 ground station)
- Raspberry Pi Pico 2 with headers (flight computer, MicroPython or CircuitPython)
- Waveshare SX1262 433 MHz LoRa module for Pico (includes 600 mAh LiPo, charger, power switch = master switch). Note: SX1262, not SX127x – needs an SX126x driver.
- Pimoroni Pico Omnibus (holds Pico + LoRa module, spare pins). 94 × 52 mm, mounts lengthwise.
- 433 MHz IPEX spring antenna (≤30 mm external)
- 2× Adafruit AS7341 (STEMMA QT) – same I2C address 0x39, so one on each I2C bus
- Adafruit LTR390 UV (STEMMA QT)
- Adafruit SHT45 temperature + humidity (STEMMA QT) – primary air temperature sensor
- Adafruit BMP388 pressure (STEMMA QT) – primary pressure sensor (BME280 considered as an alternative/backup)
- Adafruit LSM6DSO32 IMU (±32 g) – tilt/swing correction, launch/landing detection
- ATGM336H GPS (UART) – recovery and wind profile from drift
- STEMMA QT cables + 2× STEMMA QT-to-female-socket leads; female jumpers for GPS
- PTFE 1 mm diffuser over sensor windows (passes UV)
- Data logged to Pico flash (full rate after launch detection); SD module optional
- Orange ripstop nylon canopy, ball-bearing swivel, 3D-printed PETG shell, ballast to 300–350 g
- Ground station: second Pico 2 + SX1262 module on a laptop over USB
- Secure every plug-in connector (hot glue/tape) for 20 g.

## Parachute design plan
- Sizing: drag = weight at terminal velocity → A = 2mg / (ρ·Cd·v²). Baseline: m = 0.325 kg, v = 12 m/s, Cd ≈ 0.8 (flat hexagon), ρ = 1.225 kg/m³ → A ≈ 0.045 m², hexagon side ≈ 13 cm, ≈ 23 cm across flats.
- Spill hole 15–20% of canopy width to reduce swing (important for the light sensors); enlarge canopy slightly to compensate.
- Shroud lines 1–1.5× canopy width, one per corner, swivel to stop spin. Cruciform canopy is a lower-swing alternative.
- Tests: 5 kg hang test (50 N); drop tests from ≥10 m with a 325 g dummy, filmed and analysed in Tracker; adjust size until 10–15 m/s.
- Software: Python (sizing + descent model), OpenRocket (cross-check), ANSYS Student Fluent or SimScale (rigid-canopy CFD to compare spill holes and shapes – comparison, not ground truth), Inkscape/Fusion 360 (patterns), Fusion 360 FEA (shell under 20 g, mount under 50 N), Tracker (drop-test video analysis).
