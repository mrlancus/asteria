"""Secondary mission: sun position, expected optical signal and tilt error.

A deliberately simple single-scattering model – good for order-of-magnitude
planning (PDR expected-signal table), NOT a radiative-transfer code:
- Rayleigh optical depth (Hansen & Travis 1974 fit), scaled by the fraction of
  the air column below a height (ISA pressure ratio).
- Aerosol optical depth tau_550 · (λ/550)^-α, spread with an exponential
  scale height.
- Horizontal sensor: direct D = e^(-τ·m), diffuse = B·(1 − D) where B is the
  share of scattered light that still reaches the sensor (downward fraction,
  aerosol absorption removed). Ozone absorption ignored (matters < 330 nm).
"""

import math
from dataclasses import dataclass
from datetime import datetime

from .atmosphere import P0, isa


def sun_position(when_utc: datetime, lat_deg: float, lon_deg: float) -> tuple[float, float]:
    """Sun elevation and azimuth (degrees, azimuth from north) – low-precision almanac, ~0.1°."""
    d = (when_utc - datetime(2000, 1, 1, 12, 0)).total_seconds() / 86400
    g = math.radians(357.529 + 0.98560028 * d)
    q = 280.459 + 0.98564736 * d
    lam = math.radians(q + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    eps = math.radians(23.439 - 0.00000036 * d)
    ra = math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))
    dec = math.asin(math.sin(eps) * math.sin(lam))
    gmst_h = (18.697374558 + 24.06570982441908 * d) % 24
    ha = math.radians(gmst_h * 15 + lon_deg) - ra
    lat = math.radians(lat_deg)
    el = math.asin(math.sin(lat) * math.sin(dec) + math.cos(lat) * math.cos(dec) * math.cos(ha))
    az = math.atan2(-math.sin(ha), math.tan(dec) * math.cos(lat) - math.sin(lat) * math.cos(ha))
    return math.degrees(el), math.degrees(az) % 360


def rayleigh_tau(wavelength_nm: float) -> float:
    """Sea-level Rayleigh optical depth (Hansen & Travis 1974)."""
    um = wavelength_nm / 1000
    return 0.008569 * um ** -4 * (1 + 0.0113 * um ** -2 + 0.00013 * um ** -4)


def aerosol_tau(wavelength_nm: float, aod_550: float, angstrom: float) -> float:
    return aod_550 * (wavelength_nm / 550) ** -angstrom


def horizontal_irradiance(tau_r, tau_a, airmass, opt) -> tuple[float, float]:
    """(direct, global) on a level sensor, as fractions of the light above the atmosphere."""
    tau = tau_r + tau_a
    direct = math.exp(-tau * airmass)
    b = (opt.rayleigh_down_fraction * tau_r + opt.aerosol_down_fraction * opt.aerosol_ssa * tau_a) / tau
    return direct, direct + b * (1 - direct)


@dataclass
class BandSignal:
    wavelength_nm: float
    direct_fraction: float     # share of the light at the ground that comes straight from the sun
    global_change_pct: float   # change in a level sensor's reading from the top of the drop to the ground
    direct_change_pct: float   # change in the direct beam alone (what a direct/diffuse split recovers)


def band_signals(opt, sun_elevation_deg: float, drop_m: float, site_elevation_m: float = 0.0) -> list[BandSignal]:
    """Expected change in each band between the release height and the ground."""
    m = 1 / math.sin(math.radians(sun_elevation_deg))          # air mass (flat-Earth, fine above ~10°)
    p_ratio = isa(site_elevation_m + drop_m)[1] / isa(site_elevation_m)[1]
    ground_column = isa(site_elevation_m)[1] / P0
    out = []
    for wl in opt.bands_nm:
        tr = rayleigh_tau(wl) * ground_column
        ta = aerosol_tau(wl, opt.aod_550, opt.angstrom)
        tr_top = tr * p_ratio
        ta_top = ta * math.exp(-drop_m / opt.aerosol_scale_height_m)
        d_bot, g_bot = horizontal_irradiance(tr, ta, m, opt)
        d_top, g_top = horizontal_irradiance(tr_top, ta_top, m, opt)
        out.append(BandSignal(wl, d_bot / g_bot, 100 * (g_bot / g_top - 1), 100 * (d_bot / d_top - 1)))
    return out


def tilt_error_pct(direct_fraction: float, sun_elevation_deg: float, angle_error_deg: float) -> float:
    """Worst-case reading error when the sensor is tilted angle_error_deg towards the sun."""
    z = math.radians(90 - sun_elevation_deg)
    e = math.radians(angle_error_deg)
    return 100 * direct_fraction * (math.cos(z - e) / math.cos(z) - 1)


def ratio_error_pct(err_a_pct: float, err_b_pct: float) -> float:
    return 100 * ((1 + err_a_pct / 100) / (1 + err_b_pct / 100) - 1)


@dataclass
class CanopyView:
    half_angle_deg: float      # angular radius of the canopy seen from the sensor
    diffuse_blocked_pct: float # share of isotropic sky light (cosine-weighted) it covers
    sun_block_swing_deg: float # swing towards the sun needed before the canopy shades it


def canopy_view(canopy_width_m, line_length_m, riser_m, inflated_ratio, sun_elevation_deg) -> CanopyView:
    r = 0.5 * inflated_ratio * canopy_width_m
    dist = riser_m + math.sqrt(max(line_length_m ** 2 - r ** 2, 0.0))
    half = math.degrees(math.atan2(r, dist))
    return CanopyView(half, 100 * math.sin(math.radians(half)) ** 2, (90 - sun_elevation_deg) - half)
