"""Time-step descent and swing simulations (scipy solve_ivp)."""

import math
from dataclasses import dataclass

import numpy as np
from scipy.integrate import solve_ivp

from .atmosphere import G


@dataclass
class DescentResult:
    t: np.ndarray          # s since canopy opening
    h: np.ndarray          # m above ground
    v: np.ndarray          # m/s, positive = downwards
    drag_n: np.ndarray     # drag force on the canopy
    v_terminal: np.ndarray # local terminal speed at each height
    time_to_terminal_s: float
    descent_time_s: float
    landing_speed_m_s: float
    peak_drag_n: float


def simulate_descent(mass_kg, drag_area_m2, rho_fn, h0_m, v0_m_s=0.0,
                     inflation_time_s=0.3, tolerance=0.02) -> DescentResult:
    """1D vertical descent: m·dv/dt = m·g − ½·ρ(h)·CdA(t)·v·|v|.

    The canopy drag area grows linearly from 0 to full over inflation_time_s.
    'Time to terminal' = first time the speed is within `tolerance` (2 %) of the
    local terminal speed and stays there.
    """
    def cda(t):
        return drag_area_m2 * (min(1.0, t / inflation_time_s) if inflation_time_s > 0 else 1.0)

    def rhs(t, y):
        h, v = y
        return [-v, G - 0.5 * rho_fn(h) * cda(t) * v * abs(v) / mass_kg]

    def ground(t, y):
        return y[0]
    ground.terminal, ground.direction = True, -1

    sol = solve_ivp(rhs, (0, 600), [h0_m, v0_m_s], events=ground, max_step=0.02,
                    rtol=1e-8, atol=1e-8)
    t, (h, v) = sol.t, sol.y
    rho = np.array([rho_fn(x) for x in h])
    drag = 0.5 * rho * np.array([cda(x) for x in t]) * v * np.abs(v)
    vt = np.sqrt(2 * mass_kg * G / (rho * drag_area_m2))
    off = np.abs(v - vt) / vt > tolerance
    idx = np.nonzero(off)[0]
    t_term = float(t[idx[-1] + 1]) if idx.size and idx[-1] + 1 < t.size else (0.0 if not idx.size else math.nan)
    return DescentResult(t, h, v, drag, vt, t_term, float(t[-1]), float(v[-1]), float(drag.max()))


@dataclass
class SwingResult:
    t: np.ndarray
    theta_deg: np.ndarray
    zeta: float
    length_m: float
    period_s: float
    settle_time_s: float   # time after which |θ| stays below the threshold


def swing_damping(shape_zeta: float, spill_pct: float, gain: float = 0.5) -> float:
    """Damping ratio of the canopy swing: ζ = ζ_shape + gain × (spill % / 100).

    PLACEHOLDER model: a 20 % spill hole adds 0.10 to ζ. This is NOT measured –
    film drop tests, measure how fast the swing dies away in Tracker and refit.
    """
    return shape_zeta + gain * spill_pct / 100


def simulate_swing(length_m, theta0_deg, zeta, mass_kg, rho=1.225, can_side_area_m2=0.066 * 0.115,
                   can_cd=1.0, duration_s=40.0, threshold_deg=5.0) -> SwingResult:
    """Pendulum of the can under the canopy (pivot at the canopy, canopy falling steadily):

        θ'' = −(g/L)·sin θ − 2ζω·θ' − (ρ·Cd·A·L / 2m)·θ'·|θ'|

    The linear term stands in for canopy damping (depends on spill hole); the
    quadratic term is the air drag on the can as it swings sideways.
    """
    w = math.sqrt(G / length_m)
    kq = 0.5 * rho * can_cd * can_side_area_m2 * length_m / mass_kg

    def rhs(t, y):
        th, om = y
        return [om, -(G / length_m) * math.sin(th) - 2 * zeta * w * om - kq * om * abs(om)]

    t_eval = np.linspace(0, duration_s, int(duration_s * 50) + 1)
    sol = solve_ivp(rhs, (0, duration_s), [math.radians(theta0_deg), 0.0], t_eval=t_eval,
                    rtol=1e-8, atol=1e-10)
    th = np.degrees(sol.y[0])
    above = np.nonzero(np.abs(th) > threshold_deg)[0]
    settle = 0.0 if not above.size else (math.inf if above[-1] == th.size - 1 else float(sol.t[above[-1] + 1]))
    return SwingResult(sol.t, th, zeta, length_m, 2 * math.pi / w, settle)
