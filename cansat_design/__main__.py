"""Command line: python -m cansat_design [options]

Prints the design summary, runs the sweeps, saves plots, CSVs and the canopy SVG.
"""

import argparse
from pathlib import Path

from . import parachute as P
from . import sweeps
from .config import Config
from .design import design


def summary(d) -> str:
    cfg, pc, ms, b = d.cfg, d.cfg.parachute, d.cfg.mission, d.budget
    out = []
    add = out.append
    add("=" * 72)
    add("CanSat design calculator – summary")
    add("=" * 72)
    add(f"Air density at ground: {d.rho:.3f} kg/m³   Target speed: {ms.target_speed_m_s:.1f} m/s   "
        f"Apogee: {ms.apogee_m:.0f} m")

    add("\nMASS BUDGET" + ("  (contains estimates – weigh the real parts)" if b.any_estimates else ""))
    for c in cfg.components:
        q = f" ×{c.qty}" if c.qty > 1 else ""
        add(f"  {c.name + q:<44} {c.mass_g * c.qty:7.1f} g{'  est.' if c.estimate else ''}")
    add(f"  {'Components total':<44} {b.components_g:7.1f} g")
    add(f"  {'Parachute (canopy, lines, swivel, tape)':<44} {b.parachute_g:7.1f} g")
    add(f"  {'Ballast to reach 300 g minimum':<44} {b.ballast_to_min_g:7.1f} g")
    add(f"  {f'Ballast to reach design mass {cfg.mass.design_mass_kg * 1000:.0f} g':<44} "
        f"{b.ballast_to_design_g:7.1f} g  ({d.volume.ballast_cm3:.1f} cm³)")
    add(f"  {'Flight mass':<44} {d.mass_kg * 1000:7.1f} g")

    v = d.volume
    add(f"\nVOLUME  inner {v.inner_volume_cm3:.0f} cm³, usable at {cfg.envelope.packing_efficiency:.0%} packing "
        f"{v.usable_volume_cm3:.0f} cm³, used {v.used_cm3:.0f} cm³ (components {v.components_cm3:.0f} + "
        f"ballast {v.ballast_cm3:.0f})")

    add(f"\nCANOPY SIZE PER SHAPE  (for {d.mass_kg * 1000:.0f} g at {ms.target_speed_m_s:.0f} m/s, "
        f"spill hole {pc.spill_hole_pct:.0f} % of width)")
    add(f"  {'Shape':<15}{'Cd0':>5}{'Area m²':>9}{'Width cm':>10}{'Hole cm':>9}{'Mass g':>8}  Dimensions")
    for s, (c, m) in d.all_shapes.items():
        cd0 = d.cd0 if s == pc.shape else P.SHAPES[s].cd0
        dims = ", ".join(f"{k} {val * 100:.1f}" for k, val in c.dims.items())
        mark = "*" if s == pc.shape else " "
        add(f" {mark}{P.SHAPES[s].label:<15}{cd0:5.2f}{c.gross_area_m2:9.4f}{c.width_m * 100:10.1f}"
            f"{c.hole_d_m * 100:9.1f}{m.total_g:8.1f}  {dims} cm")
    add("  (* = chosen shape; hemispherical needs "
        f"{pc.n_gores} gores of the shape in the SVG when chosen)")

    c, m = d.canopy, d.chute
    add(f"\nCHOSEN CANOPY: {P.SHAPES[c.shape].label}")
    add(f"  Drag area Cd·A = {d.drag_area_m2:.4f} m²  (Cd0 {d.cd0:.2f}, vent ratio λ = {c.vent_ratio:.3f})")
    add(f"  Fabric with {pc.seam_allowance_mm:.0f} mm seams: {m.fabric_area_m2:.4f} m² → {m.fabric_g:.1f} g")
    add(f"  Lines: {m.n_lines} × {m.line_length_m * 100:.0f} cm → {m.lines_g:.1f} g;  swivel {m.swivel_g:.0f} g, "
        f"tape/thread {m.reinforcement_g:.0f} g;  total {m.total_g:.1f} g")
    add(f"  Predicted terminal speed: {d.v_terminal:.2f} m/s at ground, "
        f"{d.descent.v_terminal[0]:.2f} m/s at apogee")
    add(f"  Opening shock: {d.opening_n:.1f} N (Cx {pc.opening_load_factor}, opening at {pc.opening_speed_m_s:.0f} m/s)")

    r = d.descent
    add(f"\nDESCENT SIMULATION  (from {ms.apogee_m:.0f} m, opening at {pc.opening_speed_m_s:.0f} m/s)")
    add(f"  Within 2 % of terminal speed after {r.time_to_terminal_s:.1f} s;  peak drag {r.peak_drag_n:.1f} N "
        "(no overshoot modelled)")
    add(f"  Descent time {r.descent_time_s:.1f} s (simple h/v: {ms.apogee_m / d.v_terminal:.1f} s), "
        f"landing at {r.landing_speed_m_s:.1f} m/s → {d.packets} telemetry packets at {ms.telemetry_hz:.0f} Hz")
    s = d.swing
    settle = f"{s.settle_time_s:.1f} s" if s.settle_time_s != float("inf") else "never in the descent"
    add(f"  Swing (illustrative): L {s.length_m:.2f} m, period {s.period_s:.2f} s, ζ {s.zeta:.2f}; "
        f"below {ms.swing_threshold_deg:.0f}° after {settle}")

    add("\nRULE CHECKS")
    for ch in d.checks:
        add(f"  [{ch.status:^6}] {ch.rule:<48} {ch.value}")
    add("\nNote: any figures or text from this tool used in reports must be referenced as AI-assisted "
        "(Claude Code, Nov 2026).")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m cansat_design", description=__doc__.split("\n")[2])
    ap.add_argument("--shape", choices=list(P.SHAPES), help="parachute shape")
    ap.add_argument("--mass", type=float, help="design flight mass in kg (e.g. 0.325)")
    ap.add_argument("--speed", type=float, help="target descent speed in m/s")
    ap.add_argument("--spill", type=float, help="spill-hole diameter as %% of canopy width")
    ap.add_argument("--apogee", type=float, help="deployment height in m")
    ap.add_argument("--outdir", default="outputs", help="folder for plots, CSVs and SVGs")
    ap.add_argument("--no-plots", action="store_true", help="only print the summary")
    a = ap.parse_args(argv)

    cfg = Config()
    if a.shape:
        cfg.parachute.shape = a.shape
    if a.mass:
        cfg.mass.design_mass_kg = a.mass
    if a.speed:
        cfg.mission.target_speed_m_s = a.speed
    if a.spill is not None:
        cfg.parachute.spill_hole_pct = a.spill
    if a.apogee:
        cfg.mission.apogee_m = a.apogee

    d = design(cfg)
    print(summary(d))
    if a.no_plots:
        return d

    from . import plots
    from .svg_export import export_svg

    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    sva, svm, svs = sweeps.speed_vs_area(d), sweeps.speed_vs_mass(d), sweeps.swing_vs_spill(d)
    files = [plots.plot_descent(d, out), *plots.plot_sweeps(d, sva, svm, svs, out)]
    shapes = list(P.SHAPES)
    sweeps.save_csv(out / "sweep_speed_vs_area.csv", ["area_m2", *shapes], [sva["area_m2"], *[sva[s] for s in shapes]])
    sweeps.save_csv(out / "sweep_speed_vs_mass.csv", ["mass_kg", "speed_m_s"], [svm["mass_kg"], svm["speed_m_s"]])
    sweeps.save_csv(out / "sweep_swing_vs_spill.csv",
                    ["spill_pct", *[f"{s}_settle_s" for s in shapes], *[f"{s}_width_m" for s in shapes]],
                    [svs["spill_pct"], *[svs[s]["settle_s"] for s in shapes], *[svs[s]["width_m"] for s in shapes]])
    svgs = export_svg(d.canopy, cfg.parachute, out)
    print(f"\nSaved {len(files)} plots, 3 CSVs and {len(svgs)} SVGs "
          f"(1 full-size + {len(svgs) - 1} A4 tiles) to {out}/")
    return d


if __name__ == "__main__":
    main()
