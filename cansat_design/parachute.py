"""Parachute sizing, geometry, mass, terminal velocity and opening shock.

Conventions (see README for the reasoning):
- Cd0 is referenced to the canopy's nominal (constructed) fabric area S0, the
  usual convention in parachute handbooks (e.g. Knacke). For flat shapes S0 is
  the flat outline area; for the hemisphere it is the curved surface area.
- "Canopy width" W (used for the spill-hole % and line length) is: across flats
  for the hexagon, diameter for the circle, total span for the cruciform and
  inflated diameter for the hemisphere.
- Spill hole: λ = hole area / gross area. Drag area = Cd0 · S_gross·(1 − λ) · (1 − k·λ),
  i.e. we lose the fabric area AND a little Cd. k = 1 by default (tunable).
"""

import math
from dataclasses import dataclass, field

import numpy as np

from .atmosphere import G


@dataclass(frozen=True)
class ShapeInfo:
    cd0: float          # default drag coefficient on nominal area
    n_lines: int        # default number of shroud lines
    swing_zeta: float   # base damping ratio for the swing model – a GUESS, calibrate from drop tests
    label: str


SHAPES = {
    "flat_hexagon": ShapeInfo(0.80, 6, 0.04, "Flat hexagon"),
    "flat_circle": ShapeInfo(0.75, 8, 0.03, "Flat circle"),
    "cruciform": ShapeInfo(0.70, 8, 0.10, "Cruciform"),
    "hemispherical": ShapeInfo(0.70, 8, 0.05, "Hemispherical"),  # ≈ 1.4 on projected area
}


def required_drag_area(mass_kg: float, rho: float, v: float) -> float:
    """Drag = weight at terminal velocity → Cd·A = 2mg / (ρ·v²)."""
    return 2 * mass_kg * G / (rho * v ** 2)


def terminal_velocity(mass_kg: float, rho: float, drag_area_m2: float) -> float:
    """Reverse of required_drag_area: v = √(2mg / (ρ·Cd·A))."""
    return math.sqrt(2 * mass_kg * G / (rho * drag_area_m2))


def required_area(mass_kg: float, rho: float, cd: float, v: float) -> float:
    """Plain A = 2mg / (ρ·Cd·v²) with no spill hole."""
    return required_drag_area(mass_kg, rho, v) / cd


def speed_in_range(v: float, vmin: float = 10.0, vmax: float = 15.0) -> bool:
    return vmin <= v <= vmax


# ---------------------------------------------------------------- geometry

def hexagon_side(area_m2: float) -> float:
    """Regular hexagon: A = (3√3/2)·s²."""
    return math.sqrt(2 * area_m2 / (3 * math.sqrt(3)))


@dataclass
class Canopy:
    shape: str
    gross_area_m2: float           # outline (or full hemisphere) area before the spill hole
    spill_pct: float
    width_m: float                 # reference width W
    hole_d_m: float
    hole_area_m2: float
    perimeter_m: float             # total cut-edge length to hem (outer edges + hole)
    dims: dict = field(default_factory=dict)       # named dimensions for printing (m)
    pieces: list = field(default_factory=list)     # flat cut pieces: list of (N,2) arrays in m
    n_pieces: int = 1              # how many times to cut each piece (gores)

    @property
    def net_area_m2(self) -> float:
        return self.gross_area_m2 - self.hole_area_m2

    @property
    def vent_ratio(self) -> float:
        return self.hole_area_m2 / self.gross_area_m2


def _hexagon(area, p):
    s = hexagon_side(area)
    flats, corners = math.sqrt(3) * s, 2 * s
    d = p * flats
    ang = np.radians(np.arange(6) * 60 + 30)       # flat edges top and bottom
    outline = np.column_stack([s * np.cos(ang), s * np.sin(ang)])
    return Canopy("flat_hexagon", area, p * 100, flats, d, math.pi * d ** 2 / 4,
                  6 * s + math.pi * d,
                  {"side": s, "across flats": flats, "across corners": corners},
                  [outline])


def _circle(area, p):
    D = math.sqrt(4 * area / math.pi)
    d = p * D
    ang = np.linspace(0, 2 * math.pi, 181)[:-1]
    outline = np.column_stack([D / 2 * np.cos(ang), D / 2 * np.sin(ang)])
    return Canopy("flat_circle", area, p * 100, D, d, math.pi * d ** 2 / 4,
                  math.pi * (D + d), {"diameter": D}, [outline])


def _cruciform(area, p, ratio):
    # Two w × L rectangles crossing: A = 2·L·w − w² = w²(2r − 1)
    w = math.sqrt(area / (2 * ratio - 1))
    L = ratio * w
    arm = (L - w) / 2
    d = p * L
    h, a = w / 2, L / 2
    outline = np.array([
        [h, h], [h, a], [-h, a], [-h, h], [-a, h], [-a, -h],
        [-h, -h], [-h, -a], [h, -a], [h, -h], [a, -h], [a, h],
    ])
    return Canopy("cruciform", area, p * 100, L, d, math.pi * d ** 2 / 4,
                  4 * L + math.pi * d,
                  {"arm width": w, "arm length (beyond centre square)": arm, "total span": L},
                  [outline])


def gore_outline(r: float, n_gores: int, s_start: float = 0.0, n_pts: int = 60) -> np.ndarray:
    """Flat pattern of one hemispherical gore (without seam allowance).

    s is the arc length from the apex along a meridian, from s_start (spill hole
    edge) to the skirt at π·r/2. Half-width at s = (π·r / N)·sin(s / r).
    Returns a closed polygon, x across the gore, y along it (apex end at y = 0).
    """
    s = np.linspace(s_start, math.pi * r / 2, n_pts)
    half = math.pi * r / n_gores * np.sin(s / r)
    right = np.column_stack([half, s])
    left = np.column_stack([-half[::-1], s[::-1]])
    return np.vstack([right, left])


def _hemisphere(area, p, n_gores):
    r = math.sqrt(area / (2 * math.pi))          # S0 = 2πr²
    W = 2 * r                                    # inflated diameter
    d = p * W
    theta = math.asin(min(p, 1.0))               # spill-hole cap half-angle
    hole_area = 2 * math.pi * r ** 2 * (1 - math.cos(theta))
    gore = gore_outline(r, n_gores, r * theta)
    edges = np.diff(np.vstack([gore, gore[:1]]), axis=0)
    gore_perim = float(np.hypot(edges[:, 0], edges[:, 1]).sum())
    return Canopy("hemispherical", area, p * 100, W, d, hole_area, n_gores * gore_perim,
                  {"radius": r, "inflated diameter": W, "gore length": math.pi * r / 2 - r * theta,
                   "gore max width": 2 * math.pi * r / n_gores},
                  [gore], n_pieces=n_gores)


def canopy_geometry(shape: str, gross_area_m2: float, spill_pct: float,
                    cruciform_ratio: float = 3.0, n_gores: int = 8) -> Canopy:
    p = spill_pct / 100
    if not 0 <= p < 0.5:
        raise ValueError("spill hole must be 0–50 % of canopy width")
    if shape == "flat_hexagon":
        return _hexagon(gross_area_m2, p)
    if shape == "flat_circle":
        return _circle(gross_area_m2, p)
    if shape == "cruciform":
        return _cruciform(gross_area_m2, p, cruciform_ratio)
    if shape == "hemispherical":
        return _hemisphere(gross_area_m2, p, n_gores)
    raise ValueError(f"unknown shape {shape!r}, choose from {list(SHAPES)}")


# ---------------------------------------------------------------- sizing

def cd_of(pc) -> float:
    return pc.cd if pc.cd is not None else SHAPES[pc.shape].cd0


def drag_area(canopy: Canopy, cd0: float, k: float = 1.0) -> float:
    """Effective Cd·A with the spill-hole approximation."""
    lam = canopy.vent_ratio
    return cd0 * canopy.gross_area_m2 * (1 - lam) * (1 - k * lam)


def size_canopy(pc, mass_kg: float, rho: float, v: float, shape: str | None = None,
                spill_pct: float | None = None) -> Canopy:
    """Find the canopy that gives terminal speed v for mass_kg, including the spill hole."""
    shape = shape or pc.shape
    spill = pc.spill_hole_pct if spill_pct is None else spill_pct
    cd0 = pc.cd if (pc.cd is not None and shape == pc.shape) else SHAPES[shape].cd0
    # λ does not depend on scale, so build a unit-area canopy to get it
    lam = canopy_geometry(shape, 1.0, spill, pc.cruciform_span_ratio, pc.n_gores).vent_ratio
    gross = required_drag_area(mass_kg, rho, v) / (cd0 * (1 - lam) * (1 - pc.vent_cd_loss * lam))
    return canopy_geometry(shape, gross, spill, pc.cruciform_span_ratio, pc.n_gores)


# ---------------------------------------------------------------- mass

@dataclass
class ParachuteMass:
    fabric_area_m2: float
    fabric_g: float
    lines_g: float
    line_length_m: float
    n_lines: int
    swivel_g: float
    reinforcement_g: float

    @property
    def total_g(self) -> float:
        return self.fabric_g + self.lines_g + self.swivel_g + self.reinforcement_g


def line_length(pc, canopy: Canopy) -> float:
    return pc.line_length_m if pc.line_length_m is not None else pc.line_length_factor * canopy.width_m


def n_lines_for(pc, canopy: Canopy) -> int:
    if canopy.shape == "hemispherical":
        return pc.n_gores
    if pc.n_lines is not None and canopy.shape == pc.shape:
        return pc.n_lines
    return SHAPES[canopy.shape].n_lines


def parachute_mass(pc, canopy: Canopy) -> ParachuteMass:
    """Fabric area = net area + seam allowance × every cut edge (hem folded once)."""
    fabric = canopy.net_area_m2 + canopy.perimeter_m * pc.seam_allowance_mm / 1000
    n = n_lines_for(pc, canopy)
    ll = line_length(pc, canopy)
    return ParachuteMass(fabric, fabric * pc.fabric_g_m2, n * ll * pc.line_g_m, ll, n,
                         pc.swivel_g, pc.reinforcement_g)


# ---------------------------------------------------------------- loads

def opening_shock(pc, drag_area_m2: float, rho: float) -> float:
    """F = Cx · ½ρv² · Cd·A at the opening speed (Knacke's opening-load-factor method)."""
    return pc.opening_load_factor * 0.5 * rho * pc.opening_speed_m_s ** 2 * drag_area_m2


def speed_for_load(pc, drag_area_m2: float, rho: float, load_n: float) -> float:
    """Opening speed at which the shock would reach load_n."""
    return math.sqrt(2 * load_n / (pc.opening_load_factor * rho * drag_area_m2))
