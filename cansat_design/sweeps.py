"""Parameter sweeps: descent speed vs canopy size and mass, swing vs spill-hole size."""

import numpy as np

from . import parachute as P
from .descent import simulate_swing, swing_damping


def speed_vs_area(d, areas_m2=None) -> dict:
    """Terminal speed at ground for each shape over a range of gross canopy areas."""
    pc = d.cfg.parachute
    areas = np.linspace(0.02, 0.10, 81) if areas_m2 is None else np.asarray(areas_m2)
    out = {"area_m2": areas}
    for s in P.SHAPES:
        cd0 = pc.cd if (pc.cd is not None and s == pc.shape) else P.SHAPES[s].cd0
        v = []
        for a in areas:
            c = P.canopy_geometry(s, a, pc.spill_hole_pct, pc.cruciform_span_ratio, pc.n_gores)
            v.append(P.terminal_velocity(d.mass_kg, d.rho, P.drag_area(c, cd0, pc.vent_cd_loss)))
        out[s] = np.array(v)
    return out


def speed_vs_mass(d, masses_kg=None) -> dict:
    """Terminal speed of the chosen canopy for a range of flight masses."""
    m = np.linspace(0.29, 0.36, 71) if masses_kg is None else np.asarray(masses_kg)
    return {"mass_kg": m, "speed_m_s": np.sqrt(2 * m * P.G / (d.rho * d.drag_area_m2))}


def swing_vs_spill(d, spills_pct=None) -> dict:
    """For each shape and spill-hole size, resize the canopy to the target speed and
    simulate the swing. Returns settle time (s) and canopy width (m)."""
    cfg, pc, ms = d.cfg, d.cfg.parachute, d.cfg.mission
    spills = np.arange(0, 31, 2.0) if spills_pct is None else np.asarray(spills_pct)
    out = {"spill_pct": spills}
    for s in P.SHAPES:
        settle, width = [], []
        for sp in spills:
            c = P.size_canopy(pc, d.mass_kg, d.rho, ms.target_speed_m_s, shape=s, spill_pct=sp)
            L = P.line_length(pc, c) + pc.riser_length_m + cfg.envelope.height_mm / 2000
            r = simulate_swing(L, ms.swing_initial_deg, swing_damping(P.SHAPES[s].swing_zeta, sp),
                               d.mass_kg, d.rho, can_cd=ms.can_side_cd,
                               duration_s=max(d.descent.descent_time_s, 1.0),
                               threshold_deg=ms.swing_threshold_deg)
            settle.append(r.settle_time_s)
            width.append(c.width_m)
        out[s] = {"settle_s": np.array(settle), "width_m": np.array(width)}
    return out


def save_csv(path, header: list[str], columns: list) -> None:
    np.savetxt(path, np.column_stack(columns), delimiter=",", header=",".join(header),
               comments="", fmt="%.5g")
