"""Run the whole design calculation for a Config and check it against the rules."""

import math
from dataclasses import dataclass, field

from . import parachute as P
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
    d.checks = rule_checks(d)
    return d


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
    for rule in ["Master power switch easily accessible", "Battery easily accessible",
                 "Radio frequency changeable in software", "Parachute reusable, bright fabric, no motorised recovery",
                 "Nothing beyond can diameter until released", "Budget ≤ £400 (see parts sheet)"]:
        checks.append(Check(rule, "check by hand", "MANUAL"))
    return checks
