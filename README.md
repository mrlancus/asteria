# Asteria – CanSat 2026–27

Our UK CanSat entry: a mini descent probe measuring how the atmosphere changes the light satellites see.

- `CLAUDE.md` – full project context: rules, mission, hardware, parachute plan
- `PROMPT.md` – kickoff prompt for Claude Code to build the parachute and design calculator

Parts list and budget: kept in a separate sheet.

---

## `cansat_design` – parachute and design calculator

A small Python package that sizes the parachute, builds the mass budget, simulates the descent and checks everything against the competition rules in `CLAUDE.md`.

### Quick start

```bash
pip install -r requirements.txt
python -m cansat_design                      # summary + plots, CSVs and SVG pattern in outputs/
python -m cansat_design --shape cruciform --spill 15 --mass 0.33
python -m cansat_design --no-plots           # summary only
python -m pytest                             # targeted physics tests
```

Options: `--shape {flat_hexagon,flat_circle,cruciform,hemispherical}`, `--mass` (kg), `--speed` (m/s), `--spill` (% of width), `--apogee` (m), `--outdir`, `--no-plots`.

**Everything else is edited in `cansat_design/config.py`** – one file of dataclasses with defaults (units in every name). When a real part arrives, weigh it, update its `mass_g` and set `estimate=False`.

### What's where

| File | What it does |
|---|---|
| `config.py` | All inputs: can envelope, component list, mass limits, parachute, air, mission |
| `atmosphere.py` | Air density – fixed, from measured T and p, or ISA |
| `mass.py` | Mass budget, ballast, volume check, battery life |
| `parachute.py` | Sizing, geometry for each shape, fabric/parachute mass, terminal velocity, opening shock |
| `optics.py` | Secondary mission: sun position, expected signal per AS7341 band (Rayleigh + haze), tilt error, canopy field of view |
| `telemetry.py` | LoRa packet airtime and duty cycle, flash logging budget |
| `descent.py` | ODE descent simulation and pendulum swing model |
| `design.py` | Runs everything and does the rule checks |
| `sweeps.py`, `plots.py` | Parameter sweeps and matplotlib figures |
| `svg_export.py` | Full-size canopy pattern + A4 print tiles |

### Outputs (in `outputs/`, not committed)

- `descent.png` – altitude, speed and swing angle vs time
- `sweep_speed_vs_area.png` – descent speed vs canopy area for every shape
- `sweep_speed_vs_mass.png` – descent speed vs flight mass for the chosen canopy
- `sweep_swing_vs_spill.png` – swing settle time and required canopy width vs spill-hole size
- `mission_signal_vs_tilt.png` – expected dimming per wavelength band vs the reading error from tilt
- `*.csv` – the sweep data, for our own analysis
- `canopy_pattern.svg` – full-size pattern for laser cutting (units are mm)
- `canopy_A4_rRcC.svg` – the same pattern split into A4 pages with 10 mm overlap. **Print at 100 % / "actual size"** and check the 100 mm scale bar before cutting.

Pattern key: solid black = cut line (includes seam allowance), dashed blue = stitch line / finished edge, red + = shroud line attachment. For the hemispherical canopy the SVG is **one gore** – cut it `n_gores` times.

### Assumptions (read before trusting a number)

**Sizing.** At terminal velocity drag = weight, so Cd·A = 2mg / (ρ·v²). The flight mass used is the design mass (325 g by default); ballast makes up the difference. We assume the 300–350 g limit **includes the parachute** (`parachute_counts_in_mass`) – conservative; check with the organisers.

**Drag coefficients** are referenced to the nominal (constructed) fabric area S0, the usual parachute-handbook convention: flat hexagon 0.80, flat circle 0.75, cruciform 0.70, hemispherical 0.70 (≈ 1.4 if you reference the projected, inflated area instead). These are typical published values, not measurements – **drop tests decide the real Cd**. Override with `Parachute.cd`.

**Canopy width** W means: across flats (hexagon), diameter (circle), total span (cruciform), inflated diameter (hemisphere). The spill-hole % and line length use W.

**Spill hole.** With λ = hole area / gross area, we take Cd·A = Cd0 · S_gross · (1 − λ) · (1 − k·λ): we lose the hole's area and also a little Cd for the air leaking through. k = 1 by default (`vent_cd_loss`) – a simple, slightly conservative approximation. Small vents (< ~5 % of area) change drag only a few percent. The calculator enlarges the canopy to compensate automatically.

**Geometry.** Hexagon: A = (3√3/2)·s², across flats √3·s, across corners 2s. Circle: A = πD²/4. Cruciform: two w × L strips crossing, A = 2Lw − w², L = 3w by default (arms as long as they are wide). Hemisphere: S0 = 2πr², each of N gores is a flat strip with half-width (πr/N)·sin(s/r) at arc distance s from the apex; the spill hole is a spherical cap.

**Fabric and parachute mass.** Fabric = net canopy area + seam allowance × every cut edge (hem folded once). Mass = fabric × areal density (ripstop ~40 g/m²) + lines × length × g/m + swivel + tape/thread. Line length = 1.25 × W by default.

**Density.** 1.225 kg/m³ unless you give measured T and p (ideal gas, dry air) or switch on ISA for the site elevation. In the simulation, density falls with height following the ISA ratio, so the CanSat falls slightly faster at apogee than at the ground – both are checked.

**Opening shock** = Cx · ½ρv² · Cd·A (Knacke's opening-load-factor method), with Cx = 1.8 (conservative for solid flat canopies; the real factor is lower for light payloads like ours) and an opening speed of 20 m/s (a guess – the CanSat leaves the rocket near apogee and falls briefly before the canopy opens). The summary also gives the opening speed at which 50 N would be reached. **This does not replace the required 50 N (5 kg) hang test.**

**Descent simulation.** 1D vertical: m·dv/dt = mg − ½ρ(h)·Cd·A·v², starting at apogee with the opening speed, canopy drag area growing linearly over 0.3 s. No wind, no horizontal motion, no added-mass or overshoot effects. "Time to terminal" = when the speed stays within 2 % of the local terminal speed.

**Swing model – illustrative only.** The can is a pendulum of length (lines + riser + half the can) under a steadily falling canopy: θ'' = −(g/L)·sin θ − 2ζω·θ' − (ρ·Cd·A·L / 2m)·θ'|θ'|. The last term is real air drag on the can; the damping ratio ζ is **a placeholder**: ζ = ζ_shape + 0.5 × (spill % / 100) with ζ_shape = 0.04 hexagon, 0.03 circle, 0.10 cruciform, 0.05 hemisphere. This captures the known trend (spill holes and cruciforms swing less) but the numbers are guesses. **Calibrate from filmed drop tests**: track the can in Tracker, measure how fast the swing amplitude decays (amplitude ratio r between successive swings to opposite sides → ζ ≈ ln(1/r) / π for small ζ), then edit `SHAPES` in `parachute.py`. The settle-time curves are stepped because the swing crosses the 5° limit once per half-swing.

**Mass, volume and power.** Component masses, sizes and currents are estimates (marked `est.` in the summary). Volume check: every component's bounding box must fit the inner can (2 mm walls) in some orientation, and the total (plus ballast, steel 7.85 g/cm³) must be below 60 % of the inner volume – packing is never perfect. Battery life = 600 mAh × 80 % usable ÷ total average current; LoRa TX bursts are averaged at 1 Hz.

**Cost.** Each component's `cost_gbp` is the line cost from the team parts sheet (whole packs), plus parachute materials. The parts sheet is the source of truth – update both. Ground station parts are costed separately and assumed to be outside the £400 (ground support equipment).

**Secondary-mission signal (simple model – order of magnitude only).** Sun position from a low-precision almanac (~0.1°). Rayleigh optical depth from Hansen & Travis (1974), scaled by the fraction of the air column below each height (ISA). Haze: aerosol optical depth 0.15 at 550 nm, Ångström exponent 1.3, exponential with a 1 km scale height, 90 % of extinction scattered. A level sensor sees direct light e^(−τ·m) plus a share of the scattered light (half of Rayleigh, 75 % of aerosol), so much of what the direct beam loses comes back as diffuse light – the level-sensor signal is therefore several times smaller than the direct-beam signal. Ozone absorption is ignored (it matters below ~330 nm, so the UV row is rough). Tilt error assumes the worst case (tilted straight towards the sun) and a perfect cosine response. These are planning numbers for the PDR, not predictions: the haze amount and profile change day to day.

**Radio and logging.** LoRa airtime uses the Semtech SX126x formula (explicit header, CRC on); the UK 433 MHz duty-cycle limit of 10 % is our reading of IR 2030 – confirm. The logging budget sums each planned stream (rate × bytes per sample including a 4-byte timestamp) against an estimated 2 MB of free flash.

**Rules not computable here** (master switch, battery access, frequency in software, reusable recovery, nothing outside the can before release, £400 budget, 20 g launch load) are listed as MANUAL so they appear on the checklist.

### Referencing in reports

This package was written with an AI tool (Claude Code, Anthropic, November 2026). Any figure, table or text from it used in the PDR or other competition reports must be referenced as AI-assisted, with the tool name and date. Plots and SVGs carry a footer saying so.

### Website

`site/` is a static web page that runs the same `cansat_design` Python code in the browser (Pyodide – Python compiled to WebAssembly, loaded from the jsDelivr CDN). No server, no separate JavaScript copy of the maths: change the Python, push, and the website uses the new code. The first visit takes ~10–20 s while numpy, scipy and matplotlib download; after that each calculation takes about a second.

Try it locally:

```bash
bash site/build.sh
python3 -m http.server -d dist 8000      # then open http://localhost:8000
```

**Live site: https://asteria-cansat.pages.dev** (Cloudflare Pages project `asteria-cansat`).

Publishing is automatic (`.github/workflows/deploy.yml`): every push runs the tests, then deploys. A push to `main` updates the live site; a push to any other branch gets its own preview URL (printed at the end of the deploy step in the GitHub Actions log). If the tests fail, nothing is deployed. The workflow needs two repository secrets, `CLOUDFLARE_API_TOKEN` (a token with Cloudflare Pages: Edit) and `CLOUDFLARE_ACCOUNT_ID`, under Settings → Secrets and variables → Actions.

To deploy by hand instead: `bash site/build.sh`, then `npx wrangler pages deploy dist --project-name asteria-cansat --branch main`.

New `.py` files in `cansat_design/` are picked up by the website automatically (the build writes a file list).
