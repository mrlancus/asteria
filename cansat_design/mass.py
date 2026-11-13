"""Mass budget, ballast, volume check and battery life."""

import itertools
import math
from dataclasses import dataclass


@dataclass
class MassBudget:
    components_g: float
    parachute_g: float
    built_up_g: float          # components (+ parachute if it counts towards the limit)
    ballast_to_min_g: float    # ballast needed to reach the 300 g minimum
    ballast_to_design_g: float # ballast needed to reach the design mass
    total_g: float             # flight mass with design ballast
    any_estimates: bool


def ballast_needed(built_up_g: float, target_g: float) -> float:
    return max(0.0, target_g - built_up_g)


def mass_budget(cfg, parachute_g: float) -> MassBudget:
    comps = sum(c.mass_g * c.qty for c in cfg.components)
    built = comps + (parachute_g if cfg.mass.parachute_counts_in_mass else 0.0)
    to_min = ballast_needed(built, cfg.mass.min_kg * 1000)
    to_design = ballast_needed(built, cfg.mass.design_mass_kg * 1000)
    return MassBudget(
        components_g=comps,
        parachute_g=parachute_g,
        built_up_g=built,
        ballast_to_min_g=to_min,
        ballast_to_design_g=to_design,
        total_g=built + to_design,
        any_estimates=any(c.estimate for c in cfg.components),
    )


def inner_size_mm(env) -> tuple[float, float]:
    """Usable inner (diameter, height) of the can after the shell walls and end caps."""
    return env.diameter_mm - 2 * env.wall_thickness_mm, env.height_mm - 2 * env.wall_thickness_mm


def box_fits_in_cylinder(size_mm, diameter_mm: float, height_mm: float) -> bool:
    """True if a box fits in the cylinder in any orientation (one side along the axis)."""
    for a, b, c in itertools.permutations(size_mm):
        if c <= height_mm and math.hypot(a, b) <= diameter_mm:
            return True
    return False


@dataclass
class VolumeCheck:
    inner_volume_cm3: float
    usable_volume_cm3: float
    components_cm3: float
    ballast_cm3: float
    misfits: list[str]          # components that cannot fit in any orientation

    @property
    def used_cm3(self) -> float:
        return self.components_cm3 + self.ballast_cm3

    @property
    def ok(self) -> bool:
        return not self.misfits and self.used_cm3 <= self.usable_volume_cm3


def volume_check(cfg, ballast_g: float) -> VolumeCheck:
    d, h = inner_size_mm(cfg.envelope)
    inner = math.pi * (d / 2) ** 2 * h / 1000
    comps, misfits = 0.0, []
    for c in cfg.components:
        if c.size_mm is None:
            continue
        comps += c.size_mm[0] * c.size_mm[1] * c.size_mm[2] * c.qty / 1000
        if not box_fits_in_cylinder(c.size_mm, d, h):
            misfits.append(c.name)
    return VolumeCheck(
        inner_volume_cm3=inner,
        usable_volume_cm3=inner * cfg.envelope.packing_efficiency,
        components_cm3=comps,
        ballast_cm3=ballast_g / cfg.mass.ballast_density_g_cm3,
        misfits=misfits,
    )


def battery_life_h(cfg) -> tuple[float, float]:
    """Return (total average current in mA, estimated runtime in hours)."""
    current = sum(c.current_ma * c.qty for c in cfg.components)
    usable = cfg.mission.battery_mah * cfg.mission.battery_usable_fraction
    return current, (usable / current if current > 0 else math.inf)
