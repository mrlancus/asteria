"""Glue between the web page and the cansat_design package (runs in the browser via Pyodide).

The page sends a dict of inputs; we build a Config, run the same code as the
CLI and return plain data (text, tables, PNGs as base64, SVG strings).
"""

import base64
import json
from datetime import datetime
import os

from cansat_design import parachute as P
from cansat_design import plots, sweeps
from cansat_design.__main__ import summary
from cansat_design.config import Component, Config, default_components
from cansat_design.design import design
from cansat_design.svg_export import svg_files

OUT = "/tmp/out"


def defaults_json() -> str:
    cfg = Config()
    return json.dumps({
        "shapes": {k: v.label for k, v in P.SHAPES.items()},
        "components": [{"name": c.name, "mass_g": c.mass_g, "qty": c.qty, "estimate": c.estimate,
                        "size_mm": c.size_mm, "current_ma": c.current_ma, "cost_gbp": c.cost_gbp}
                       for c in default_components()],
        "shape": cfg.parachute.shape, "mass_g": cfg.mass.design_mass_kg * 1000,
        "speed": cfg.mission.target_speed_m_s, "spill": cfg.parachute.spill_hole_pct,
        "apogee": cfg.mission.apogee_m, "opening_speed": cfg.parachute.opening_speed_m_s,
        "fabric_g_m2": cfg.parachute.fabric_g_m2, "seam_mm": cfg.parachute.seam_allowance_mm,
        "line_factor": cfg.parachute.line_length_factor, "density": cfg.air.density_kg_m3,
        "launch_time": cfg.launch.time_utc.strftime("%Y-%m-%dT%H:%M"),
        "latitude": cfg.launch.latitude_deg, "longitude": cfg.launch.longitude_deg,
    })


def _png(path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def run(params_json: str, with_sweeps: bool = True) -> str:
    p = json.loads(params_json)
    cfg = Config()
    pc = cfg.parachute
    pc.shape = p["shape"]
    pc.spill_hole_pct = float(p["spill"])
    pc.opening_speed_m_s = float(p["opening_speed"])
    pc.fabric_g_m2 = float(p["fabric_g_m2"])
    pc.seam_allowance_mm = float(p["seam_mm"])
    pc.line_length_factor = float(p["line_factor"])
    pc.cd = float(p["cd"]) if p.get("cd") not in (None, "") else None
    cfg.mass.design_mass_kg = float(p["mass_g"]) / 1000
    cfg.mission.target_speed_m_s = float(p["speed"])
    cfg.mission.apogee_m = float(p["apogee"])
    cfg.air.density_kg_m3 = float(p["density"])
    if p.get("temperature_c") not in (None, "") and p.get("pressure_hpa") not in (None, ""):
        cfg.air.temperature_c = float(p["temperature_c"])
        cfg.air.pressure_pa = float(p["pressure_hpa"]) * 100
    cfg.components = [Component(c["name"], float(c["mass_g"]), tuple(c["size_mm"]) if c["size_mm"] else None,
                                float(c["current_ma"]), int(c["qty"]), bool(c["estimate"]),
                                float(c.get("cost_gbp") or 0))
                      for c in p["components"]]
    if p.get("launch_time"):
        cfg.launch.time_utc = datetime.fromisoformat(p["launch_time"])
    cfg.launch.latitude_deg = float(p.get("latitude") or cfg.launch.latitude_deg)
    cfg.launch.longitude_deg = float(p.get("longitude") or cfg.launch.longitude_deg)

    d = design(cfg)
    os.makedirs(OUT, exist_ok=True)
    images = {"descent": _png(plots.plot_descent(d, OUT))}
    if (mp := plots.plot_mission(d, OUT)):
        images["mission"] = _png(mp)
    if with_sweeps:
        sva, svm = sweeps.speed_vs_area(d), sweeps.speed_vs_mass(d)
        svs = sweeps.swing_vs_spill(d, spills_pct=range(0, 31, 5))   # coarser than the CLI, for speed
        for name, path in zip(["speed_vs_area", "speed_vs_mass", "swing_vs_spill"],
                              plots.plot_sweeps(d, sva, svm, svs, OUT)):
            images[name] = _png(path)

    shapes = []
    for s, (c, m) in d.all_shapes.items():
        shapes.append({"shape": P.SHAPES[s].label, "chosen": s == pc.shape,
                       "cd0": d.cd0 if s == pc.shape else P.SHAPES[s].cd0,
                       "area_m2": c.gross_area_m2, "width_cm": c.width_m * 100,
                       "hole_cm": c.hole_d_m * 100, "mass_g": m.total_g,
                       "dims": ", ".join(f"{k} {v * 100:.1f} cm" for k, v in c.dims.items())})
    b = d.budget
    return json.dumps({
        "summary": summary(d),
        "checks": [{"rule": c.rule, "value": c.value, "status": c.status} for c in d.checks],
        "shapes": shapes,
        "key": {
            "v_ground": d.v_terminal, "v_apogee": float(d.descent.v_terminal[0]),
            "flight_g": d.mass_kg * 1000, "ballast_min_g": b.ballast_to_min_g,
            "ballast_design_g": b.ballast_to_design_g, "components_g": b.components_g,
            "parachute_g": b.parachute_g, "descent_s": d.descent.descent_time_s,
            "packets": d.packets, "opening_n": d.opening_n,
            "width_cm": d.canopy.width_m * 100, "area_m2": d.canopy.gross_area_m2,
            "hole_cm": d.canopy.hole_d_m * 100, "shape": P.SHAPES[pc.shape].label,
            "cost_gbp": d.cost_flight_gbp, "budget_gbp": cfg.mass.budget_gbp, "ground_gbp": d.cost_ground_gbp,
            "ratio_signal_pct": d.ratio_signal_pct, "ratio_direct_pct": d.ratio_direct_signal_pct,
            "sun_el": d.sun_elevation_deg,
            "cell_kbps": d.cell_kbps, "cell_mb": d.cell_mb, "uplink_kbps": d.cfg.cellular.uplink_kbps,
        },
        "images": images,
        "svgs": svg_files(d.canopy, pc),
    })
