"""Matplotlib figures, saved as PNG into outputs/."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from . import parachute as P  # noqa: E402

# Fixed colour per shape (never re-ordered), validated categorical palette
SHAPE_COLOURS = {
    "flat_hexagon": "#2a78d6",
    "flat_circle": "#eb6834",
    "cruciform": "#1baf7a",
    "hemispherical": "#eda100",
}
INK, INK2, GRID, BAND, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#ecebe7", "#fcfcfb"
FOOTER = "Generated with cansat_design (Python, written with Claude Code, Nov 2026)"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlecolor": INK,
    "axes.titlelocation": "left", "font.size": 9, "lines.linewidth": 2,
    "legend.frameon": False, "legend.labelcolor": INK2,
})


def _speed_band(ax, ms, horizontal=True):
    span = ax.axhspan if horizontal else ax.axvspan
    span(ms.min_speed_m_s, ms.max_speed_m_s, color=BAND, zorder=0)
    if horizontal:
        ax.text(1.0, ms.max_speed_m_s, f"allowed {ms.min_speed_m_s:.0f}–{ms.max_speed_m_s:.0f} m/s ",
                transform=ax.get_yaxis_transform(), ha="right", va="bottom", color=INK2, fontsize=8)


def _save(fig, outdir, name):
    fig.text(0.01, 0.005, FOOTER, color=INK2, fontsize=6.5, ha="left", va="bottom")
    path = Path(outdir) / name
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_descent(d, outdir):
    r, ms = d.descent, d.cfg.mission
    c = SHAPE_COLOURS[d.canopy.shape]
    fig, (a1, a2, a3) = plt.subplots(3, 1, figsize=(7, 8.5), sharex=True)
    a1.plot(r.t, r.h, color=c)
    a1.set_title("Altitude after canopy opening")
    a1.set_ylabel("Height above ground (m)")

    _speed_band(a2, ms)
    a2.plot(r.t, r.v, color=c, label="Simulated speed")
    a2.plot(r.t, r.v_terminal, color=INK2, lw=1, ls="--", label="Local terminal speed")
    if np.isfinite(r.time_to_terminal_s):
        a2.axvline(r.time_to_terminal_s, color=INK2, lw=0.8, ls=":")
        a2.annotate(f"within 2 % of terminal\nafter {r.time_to_terminal_s:.1f} s",
                    (r.time_to_terminal_s, r.v_terminal[0]), xytext=(8, 12),
                    textcoords="offset points", color=INK2, fontsize=8)
    a2.set_title("Descent speed")
    a2.set_ylabel("Speed (m/s)")
    a2.legend(loc="upper right")

    s = d.swing
    a3.axhspan(-ms.swing_threshold_deg, ms.swing_threshold_deg, color=BAND, zorder=0)
    a3.plot(s.t, s.theta_deg, color=c, lw=1.5)
    a3.set_title(f"Swing angle (ζ = {s.zeta:.2f}, L = {s.length_m:.2f} m – illustrative model)")
    a3.set_ylabel("Swing angle (°)")
    a3.set_xlabel("Time since canopy opening (s)")
    fig.tight_layout()
    return _save(fig, outdir, "descent.png")


def plot_sweeps(d, sva, svm, svs, outdir):
    ms, pc = d.cfg.mission, d.cfg.parachute
    paths = []

    fig, ax = plt.subplots(figsize=(7, 4.2))
    _speed_band(ax, ms)
    for s in P.SHAPES:
        ax.plot(sva["area_m2"], sva[s], color=SHAPE_COLOURS[s], label=P.SHAPES[s].label)
    ax.set_ylim(5, 25)
    ax.set_title(f"Descent speed vs canopy area ({d.mass_kg * 1000:.0f} g, {pc.spill_hole_pct:.0f} % spill hole)")
    ax.set_xlabel("Gross canopy area before spill hole (m²)")
    ax.set_ylabel("Terminal speed (m/s)")
    ax.legend(loc="upper right")
    fig.tight_layout()
    paths.append(_save(fig, outdir, "sweep_speed_vs_area.png"))

    fig, ax = plt.subplots(figsize=(7, 4.2))
    _speed_band(ax, ms)
    for m_g, txt in [(d.cfg.mass.min_kg * 1000, " min mass"), (d.cfg.mass.max_kg * 1000, " max mass")]:
        ax.axvline(m_g, color=INK2, lw=0.8, ls="--")
        ax.text(m_g, 0.02, txt, transform=ax.get_xaxis_transform(), color=INK2, fontsize=8)
    ax.plot(svm["mass_kg"] * 1000, svm["speed_m_s"], color=SHAPE_COLOURS[d.canopy.shape])
    ax.set_ylim(8, 17)
    ax.set_title(f"Descent speed vs CanSat mass ({P.SHAPES[d.canopy.shape].label}, "
                 f"{d.canopy.width_m * 100:.1f} cm wide)")
    ax.set_xlabel("Flight mass (g)")
    ax.set_ylabel("Terminal speed (m/s)")
    fig.tight_layout()
    paths.append(_save(fig, outdir, "sweep_speed_vs_mass.png"))

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7, 6.5), sharex=True)
    for s in P.SHAPES:
        col = SHAPE_COLOURS[s]
        a1.plot(svs["spill_pct"], svs[s]["settle_s"], color=col, label=P.SHAPES[s].label)
        a2.plot(svs["spill_pct"], svs[s]["width_m"] * 100, color=col, label=P.SHAPES[s].label)
    a1.set_title(f"Time for swing to stay below {ms.swing_threshold_deg:.0f}° "
                 f"(from {ms.swing_initial_deg:.0f}°) – placeholder damping, calibrate")
    a1.set_ylabel("Settle time (s)")
    a1.legend(loc="upper right")
    a2.set_title(f"Canopy width needed for {ms.target_speed_m_s:.0f} m/s")
    a2.set_ylabel("Canopy width (cm)")
    a2.set_xlabel("Spill-hole diameter (% of canopy width)")
    a2.legend(loc="upper left")
    fig.tight_layout()
    paths.append(_save(fig, outdir, "sweep_swing_vs_spill.png"))
    return paths


def plot_mission(d, outdir):
    """Secondary mission: expected change per band vs the reading error from tilt."""
    if not d.bands:
        return None
    from .optics import tilt_error_pct
    opt = d.cfg.optics
    bands = sorted(d.bands, key=lambda b: b.wavelength_nm)
    wl = [b.wavelength_nm for b in bands]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7, 6.5), sharex=True)
    a1.plot(wl, [abs(b.global_change_pct) for b in bands], "o-", color="#eb6834", label="Level sensor (direct + diffuse)")
    a1.plot(wl, [abs(b.direct_change_pct) for b in bands], "o-", color="#1baf7a", label="Direct sunlight only")
    a1.set_title(f"Expected dimming from {d.cfg.mission.apogee_m:.0f} m to the ground (simple model, "
                 f"sun {d.sun_elevation_deg:.0f}° up)")
    a1.set_ylabel("Change (%)")
    a1.legend(loc="upper right")
    ramp = ["#2a78d6", "#6ea3e6", "#a9c8f0"]          # one hue: larger angle error = darker
    for e, col in zip(sorted(opt.angle_errors_deg, reverse=True), ramp):
        a2.plot(wl, [tilt_error_pct(b.direct_fraction, d.sun_elevation_deg, e) for b in bands], "o-",
                color=col, label=f"{e:.0f}° angle error")
    a2.set_title("Reading error from tilting towards the sun")
    a2.set_ylabel("Error (%)")
    a2.set_xlabel("Wavelength (nm) – AS7341 bands, LTR390 UV at ~320 nm")
    a2.legend(loc="upper left")
    fig.tight_layout()
    return _save(fig, outdir, "mission_signal_vs_tilt.png")
