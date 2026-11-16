"""Run the whole design calculation for a Config and check it against the rules."""

import math
from dataclasses import dataclass, field

from . import optics as O
from . import parachute as P
from . import telemetry as T
from .atmosphere import G, density_profile, ground_density
from .descent import simulate_descent, simulate_swing, swing_damping
from .mass import battery_life_h, mass_budget, volume_check


@dataclass
class Check:
    rule: str
    value: str
    status: str   # PASS | FAIL | WARN | MANUAL


@dataclass
class Design:
    cfg: object
    rho: float
    mass_kg: float          # mass the canopy is sized for (flight mass)
    canopy: P.Canopy
    cd0: float
    drag_area_m2: float
    chute: P.ParachuteMass
    budget: object
    volume: object
    v_terminal: float
    opening_n: float
    speed_for_50n: float
    descent: object
    swing: object
    packets: int
    all_shapes: dict = field(default_factory=dict)   # shape -> (Canopy, ParachuteMass)
    checks: list = field(default_factory=list)
    # Cost
    cost_flight_gbp: float = 0.0
    cost_ground_gbp: float = 0.0
    # Secondary mission
    sun_elevation_deg: float = 0.0
    sun_azimuth_deg: float = 0.0
    bands: list = field(default_factory=list)        # optics.BandSignal per band
    ratio_signal_pct: float = 0.0                    # blue/red change, level sensor
    ratio_direct_signal_pct: float = 0.0             # blue/red change, direct beam only
    ratio_noise_pct: dict = field(default_factory=dict)  # angle error (deg) -> blue/red tilt error (%)
    canopy_view: object = None
    # Data and radio
    airtime_s: float = 0.0
    duty_cycle: float = 0.0
    log: object = None


def design(cfg) -> Design:
    pc, ms = cfg.parachute, cfg.mission
    rho = ground_density(cfg.air)
    cd0 = P.cd_of(pc)

    # Parachute mass feeds back into the flight mass only if the design mass is
    # exceeded, so a few fixed-point iterations are plenty.
    mass_kg = cfg.mass.design_mass_kg
    for _ in range(5):
        canopy = P.size_canopy(pc, mass_kg, rho, ms.target_speed_m_s)
        chute = P.parachute_mass(pc, canopy)
        budget = mass_budget(cfg, chute.total_g)
        flight_g = budget.total_g + (0 if cfg.mass.parachute_counts_in_mass else chute.total_g)
        mass_kg = flight_g / 1000

    cda = P.drag_area(canopy, cd0, pc.vent_cd_loss)
    vt = P.terminal_velocity(mass_kg, rho, cda)

    rho_fn = density_profile(cfg.air)
    desc = simulate_descent(mass_kg, cda, rho_fn, ms.apogee_m, pc.opening_speed_m_s, pc.inflation_time_s)
    L = P.line_length(pc, canopy) + pc.riser_length_m + cfg.envelope.height_mm / 2000
    zeta = swing_damping(P.SHAPES[pc.shape].swing_zeta, pc.spill_hole_pct)
    swing = simulate_swing(L, ms.swing_initial_deg, zeta, mass_kg, rho,
                           can_cd=ms.can_side_cd, duration_s=max(desc.descent_time_s, 1.0),
                           threshold_deg=ms.swing_threshold_deg)

    all_shapes = {}
    for s in P.SHAPES:
        c = P.size_canopy(pc, mass_kg, rho, ms.target_speed_m_s, shape=s)
        all_shapes[s] = (c, P.parachute_mass(pc, c))

    d = Design(cfg, rho, mass_kg, canopy, cd0, cda, chute, budget,
               volume_check(cfg, budget.ballast_to_design_g), vt,
               P.opening_shock(pc, cda, rho), P.speed_for_load(pc, cda, rho, pc.attachment_rating_n),
               desc, swing, int(desc.descent_time_s * ms.telemetry_hz), all_shapes)
    mission_extras(d)
    d.checks = rule_checks(d)
    return d


def mission_extras(d: Design) -> None:
    """Cost, secondary-mission optics, radio airtime and logging budget."""
    cfg, opt = d.cfg, d.cfg.optics
    d.cost_flight_gbp = sum(c.cost_gbp for c in cfg.components) + cfg.parachute.materials_cost_gbp
    d.cost_ground_gbp = sum(c.cost_gbp for c in cfg.ground)

    d.sun_elevation_deg, d.sun_azimuth_deg = O.sun_position(cfg.launch.time_utc, cfg.launch.latitude_deg,
                                                            cfg.launch.longitude_deg)
    if d.sun_elevation_deg > 5:
        d.bands = O.band_signals(opt, d.sun_elevation_deg, cfg.mission.apogee_m, cfg.air.site_elevation_m)
        blue, red = (next(b for b in d.bands if b.wavelength_nm == w) for w in opt.ratio_pair_nm)
        d.ratio_signal_pct = O.ratio_error_pct(blue.global_change_pct, red.global_change_pct)
        d.ratio_direct_signal_pct = O.ratio_error_pct(blue.direct_change_pct, red.direct_change_pct)
        for e in opt.angle_errors_deg:
            d.ratio_noise_pct[e] = abs(O.ratio_error_pct(
                O.tilt_error_pct(blue.direct_fraction, d.sun_elevation_deg, e),
                O.tilt_error_pct(red.direct_fraction, d.sun_elevation_deg, e)))
    pc = cfg.parachute
    d.canopy_view = O.canopy_view(d.canopy.width_m, P.line_length(pc, d.canopy), pc.riser_length_m,
                                  pc.inflated_width_ratio, d.sun_elevation_deg)

    r = cfg.radio
    d.airtime_s = T.lora_airtime_s(r.payload_bytes, r.spreading_factor, r.bandwidth_hz, r.coding_rate,
                                   r.preamble_symbols)
    d.duty_cycle = d.airtime_s * r.packets_per_s
    d.log = T.log_budget(cfg.logging)


def _pf(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def rule_checks(d: Design) -> list[Check]:
    cfg, ms, env, pc = d.cfg, d.cfg.mission, d.cfg.envelope, d.cfg.parachute
    b, vol = d.budget, d.volume
    m_g = d.mass_kg * 1000
    current, runtime = battery_life_h(cfg)
    est = " (estimated masses)" if b.any_estimates else ""
    checks = [
        Check("Mass 300–350 g", f"{m_g:.0f} g{est}",
              _pf(cfg.mass.min_kg * 1000 - 1e-6 <= m_g <= cfg.mass.max_kg * 1000 + 1e-6)),
        Check("Fits in can (115 × 66 mm), volume", f"{vol.used_cm3:.0f} of {vol.usable_volume_cm3:.0f} cm³ usable"
              + (f"; won't fit: {', '.join(vol.misfits)}" if vol.misfits else ""), _pf(vol.ok)),
        Check(f"Antenna external ≤ {env.antenna_max_mm:.0f} mm", f"{env.antenna_external_mm:.0f} mm",
              _pf(env.antenna_external_mm <= env.antenna_max_mm)),
        Check("Descent rate 10–15 m/s (min 10)", f"{d.v_terminal:.1f} m/s at ground",
              _pf(P.speed_in_range(d.v_terminal, ms.min_speed_m_s, ms.max_speed_m_s))),
    ]
    # Air is thinner at apogee, so the canopy falls slightly faster there – check that too
    v_top = float(d.descent.v_terminal[0])
    checks.append(Check("Descent rate at apogee also ≤ 15 m/s", f"{v_top:.1f} m/s",
                        _pf(P.speed_in_range(v_top, ms.min_speed_m_s, ms.max_speed_m_s))))
    margin = pc.attachment_rating_n / d.opening_n
    checks.append(Check(f"Opening shock ≤ {pc.attachment_rating_n:.0f} N attachment",
                        f"{d.opening_n:.1f} N at {pc.opening_speed_m_s:.0f} m/s (×{margin:.1f} margin; "
                        f"50 N reached at {d.speed_for_50n:.0f} m/s)",
                        "PASS" if margin >= 1.5 else ("WARN" if margin >= 1 else "FAIL")))
    checks.append(Check("Parachute connection tested to 50 N", "5 kg hang test – not yet done", "MANUAL"))
    checks.append(Check(f"Withstand {ms.launch_g:.0f} g launch",
                        f"mounts must hold {ms.launch_g * d.mass_kg * G:.0f} N total – verify by FEA/test", "MANUAL"))
    checks.append(Check(f"Battery runs ≥ {ms.required_runtime_h:.0f} h",
                        f"{runtime:.1f} h at {current:.0f} mA avg (estimated currents)",
                        _pf(runtime >= ms.required_runtime_h)))
    checks.append(Check(f"TX power ≤ {ms.max_tx_power_dbm:.0f} dBm (433 MHz)", f"{ms.tx_power_dbm:.0f} dBm",
                        _pf(ms.tx_power_dbm <= ms.max_tx_power_dbm)))
    checks.append(Check("Telemetry at 1 Hz during descent",
                        f"{d.packets} packets in {d.descent.descent_time_s:.0f} s from {ms.apogee_m:.0f} m",
                        _pf(ms.telemetry_hz >= 1.0)))
    checks.append(Check(f"Budget ≤ £{cfg.mass.budget_gbp:.0f} (flight hardware)",
                        f"£{d.cost_flight_gbp:.2f} (ground station £{d.cost_ground_gbp:.2f}, not counted)",
                        _pf(d.cost_flight_gbp <= cfg.mass.budget_gbp)))
    r = cfg.radio
    checks.append(Check(f"Radio duty cycle ≤ {r.max_duty_cycle:.0%} (433 MHz band)",
                        f"{d.duty_cycle:.1%} ({d.airtime_s * 1000:.0f} ms per {r.payload_bytes}-byte packet, "
                        f"SF{r.spreading_factor})", _pf(d.duty_cycle <= r.max_duty_cycle)))
    checks.append(Check(f"All science sent live: packet ≤ {r.max_payload_bytes} B",
                        f"{r.payload_bytes} bytes, {r.payload_bytes * r.packets_per_s:.0f} B/s live "
                        f"({len(r.packet)} fields)", _pf(r.payload_bytes <= r.max_payload_bytes)))
    need = cfg.logging.full_rate_minutes_needed
    checks.append(Check(f"Flash backup holds ≥ {need:.0f} min of full-rate log",
                        f"{d.log.minutes_available:.1f} min at {d.log.bytes_per_s / 1000:.1f} KB/s "
                        f"({cfg.logging.free_flash_mb:.1f} MB free, estimate)",
                        "PASS" if d.log.minutes_available >= need else "WARN"))   # bonus copy only
    if d.bands:
        best = min(d.ratio_noise_pct)
        snr = abs(d.ratio_signal_pct) / d.ratio_noise_pct[best]
        checks.append(Check("Secondary: blue/red signal ≥ 2× tilt error",
                            f"signal {abs(d.ratio_signal_pct):.2f} % vs error {d.ratio_noise_pct[best]:.2f} % "
                            f"at {best:.0f}° (×{snr:.1f}); direct beam {abs(d.ratio_direct_signal_pct):.1f} %",
                            "PASS" if snr >= 2 else ("WARN" if snr >= 1 else "FAIL")))
        checks.append(Check("Canopy can't shade the sun in steady descent",
                            f"needs a {d.canopy_view.sun_block_swing_deg:.0f}° swing towards the sun "
                            f"(sun {d.sun_elevation_deg:.0f}° up)",
                            _pf(d.canopy_view.sun_block_swing_deg > ms.swing_initial_deg)))
    for rule in ["Master power switch easily accessible", "Battery easily accessible",
                 "Radio frequency changeable in software", "Parachute reusable, bright fabric, no motorised recovery",
                 "Nothing beyond can diameter until released"]:
        checks.append(Check(rule, "check by hand", "MANUAL"))
    return checks
