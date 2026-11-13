"""Air density – fixed, from a measurement, or from the International Standard Atmosphere."""

import math

G = 9.80665          # m/s²
R_AIR = 287.05       # J/(kg·K), dry air
T0 = 288.15          # K, ISA sea level
P0 = 101325.0        # Pa, ISA sea level
LAPSE = 0.0065       # K/m, ISA troposphere lapse rate


def isa(altitude_m: float) -> tuple[float, float, float]:
    """ISA temperature (K), pressure (Pa) and density (kg/m³) at an altitude (valid below 11 km)."""
    t = T0 - LAPSE * altitude_m
    p = P0 * (t / T0) ** (G / (R_AIR * LAPSE))
    return t, p, p / (R_AIR * t)


def density_from_pt(pressure_pa: float, temperature_c: float) -> float:
    """Ideal gas: ρ = p / (R·T)."""
    return pressure_pa / (R_AIR * (temperature_c + 273.15))


def ground_density(air) -> float:
    """Density at ground level from an Air config: measurement > ISA > fixed value."""
    if air.temperature_c is not None and air.pressure_pa is not None:
        return density_from_pt(air.pressure_pa, air.temperature_c)
    if air.use_isa:
        return isa(air.site_elevation_m)[2]
    return air.density_kg_m3


def density_profile(air):
    """Return rho(h) for height h above ground: ground density scaled by the ISA ratio."""
    rho_ground = ground_density(air)
    rho_isa_ground = isa(air.site_elevation_m)[2]

    def rho(h_m: float) -> float:
        return rho_ground * isa(air.site_elevation_m + max(h_m, 0.0))[2] / rho_isa_ground

    return rho
