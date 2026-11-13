# Kickoff prompt for Claude Code

Paste this into Claude Code from the repo root.

---

Read CLAUDE.md first – it has the full competition rules, our mission, hardware and parachute plan.

Build a Python package in this repo called `cansat_design` – a design calculator for our CanSat, focused on the parachute. No compilation steps, keep dependencies to numpy, scipy and matplotlib.

**1. Inputs (one config file, `config.yaml` or a dataclass with defaults)**
- Can envelope: height 115 mm, diameter 66 mm (editable)
- CanSat mass (default 0.325 kg) and mass limits 0.300–0.350 kg
- Component list with masses and dimensions (seed it with the hardware in CLAUDE.md, rough masses are fine and clearly marked as estimates) → total mass, ballast needed to reach 300 g, volume check against the can
- Parachute parameters: shape (flat hexagon, flat circle, cruciform, hemispherical), Cd (default per shape, overridable), spill-hole diameter as % of canopy width, shroud line length, number of lines, canopy fabric areal density (g/m²), line mass, swivel mass
- Air: density (default 1.225 kg/m³), or compute it from altitude/temperature/pressure
- Target descent speed (default 12 m/s) and allowed range 10–15 m/s
- Launch apogee (default 400 m)

**2. Calculations**
- Required canopy area for the target speed: A = 2mg / (ρ·Cd·v²), correcting for the spill-hole area and its effect on Cd (use a simple, clearly documented approximation)
- Canopy geometry for each shape: side length, across-flats/across-corners widths, cruciform arm sizes, gore pattern for the hemispherical option
- Fabric area with seam allowance, parachute mass, and its effect on total mass
- Terminal velocity for a given canopy (the reverse calculation) and a pass/fail check against 10–15 m/s
- Opening shock estimate at deployment and a check against the 50 N attachment requirement (state assumptions)
- Descent time from apogee and number of telemetry packets at 1 Hz

**3. Descent simulation**
- Time-step ODE (scipy) from deployment: gravity + drag, density varying with altitude, time to reach terminal velocity
- Optional pendulum swing model of the can under the canopy (line length, initial disturbance, damping) → swing angle vs time, so we can compare spill-hole options for the light-sensor mission
- Plots: altitude, speed and swing angle vs time (matplotlib, saved to `outputs/`)

**4. Outputs**
- A CLI: `python -m cansat_design` prints a clear summary (mass budget, ballast, canopy size per shape, predicted descent speed, pass/fail against every rule in CLAUDE.md) and saves plots
- A parameter sweep: descent speed vs canopy size and vs CanSat mass, and swing vs spill-hole size
- Export the chosen canopy outline as a full-size SVG (with seam allowance and spill hole) that we can print on A4 sheets or laser-cut
- A short `README.md` explaining how to use it and every assumption

**5. Testing**
- Targeted tests only: area formula round-trips with terminal velocity, hexagon geometry, mass/ballast maths, and the 10–15 m/s check. No exhaustive suites.

Keep it simple and readable – other students on the team will use and edit it. Use en dashes (–), never em dashes (—). Commit in sensible steps.
