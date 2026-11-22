"""Targeted tests of the physics and maths only. Run: python -m pytest"""

import math

import pytest

from cansat_design import parachute as P
from cansat_design.config import Config, Component
from cansat_design.descent import simulate_descent
from cansat_design.mass import ballast_needed, box_fits_in_cylinder, mass_budget


def test_area_formula_round_trips_with_terminal_velocity():
    m, rho, cd, v = 0.325, 1.225, 0.8, 12.0
    area = P.required_area(m, rho, cd, v)
    assert area == pytest.approx(0.0452, abs=1e-4)          # CLAUDE.md baseline
    assert P.terminal_velocity(m, rho, cd * area) == pytest.approx(v)


def test_sized_canopy_with_spill_hole_hits_target_speed():
    pc = Config().parachute
    for shape in P.SHAPES:
        c = P.size_canopy(pc, 0.325, 1.225, 12.0, shape=shape, spill_pct=18)
        cda = P.drag_area(c, P.SHAPES[shape].cd0, pc.vent_cd_loss)
        assert P.terminal_velocity(0.325, 1.225, cda) == pytest.approx(12.0)
        assert c.hole_area_m2 > 0


def test_hexagon_geometry():
    s = 0.13
    area = 3 * math.sqrt(3) / 2 * s ** 2
    assert P.hexagon_side(area) == pytest.approx(s)
    c = P.canopy_geometry("flat_hexagon", area, 0)
    assert c.dims["across flats"] == pytest.approx(math.sqrt(3) * s)
    assert c.dims["across corners"] == pytest.approx(2 * s)
    # The outline polygon really has that area (shoelace formula)
    x, y = c.pieces[0][:, 0], c.pieces[0][:, 1]
    shoelace = 0.5 * abs(sum(x[i] * y[i - 1] - x[i - 1] * y[i] for i in range(len(x))))
    assert shoelace == pytest.approx(area)


def test_hemisphere_gore_area_matches_surface():
    # 8 flat gores should add up to (almost) the hemisphere's surface 2πr²
    c = P.canopy_geometry("hemispherical", 0.05, 0, n_gores=8)
    x, y = c.pieces[0][:, 0], c.pieces[0][:, 1]
    gore = 0.5 * abs(sum(x[i] * y[i - 1] - x[i - 1] * y[i] for i in range(len(x))))
    assert 8 * gore == pytest.approx(0.05, rel=0.03)


def test_mass_and_ballast():
    assert ballast_needed(250, 300) == 50
    assert ballast_needed(320, 300) == 0
    cfg = Config()
    cfg.components = [Component("a", 100, None), Component("b", 20, None, qty=3)]
    b = mass_budget(cfg, parachute_g=10)
    assert b.components_g == 160
    assert b.ballast_to_min_g == pytest.approx(130)       # 300 − 160 − 10
    assert b.ballast_to_design_g == pytest.approx(155)    # 325 − 160 − 10
    assert b.total_g == pytest.approx(325)


def test_omnibus_fits_lengthwise_only():
    assert box_fits_in_cylinder((94, 52, 15), 62, 111)
    assert not box_fits_in_cylinder((94, 52, 15), 62, 90)


def test_speed_range_check():
    assert P.speed_in_range(10.0) and P.speed_in_range(15.0) and P.speed_in_range(12)
    assert not P.speed_in_range(9.9)
    assert not P.speed_in_range(15.1)


def test_simulation_settles_to_terminal_velocity():
    cda = P.required_drag_area(0.325, 1.225, 12.0)
    r = simulate_descent(0.325, cda, lambda h: 1.225, h0_m=400, v0_m_s=20)
    assert r.landing_speed_m_s == pytest.approx(12.0, rel=1e-3)
    assert r.descent_time_s == pytest.approx(400 / 12, rel=0.05)


def test_lora_airtime_matches_semtech():
    from cansat_design.telemetry import lora_airtime_s
    # SF7, 125 kHz, CR 4/5, 8-symbol preamble, 10-byte payload: 41.2 ms (Semtech calculator)
    assert lora_airtime_s(10) == pytest.approx(0.04122, abs=2e-4)


def test_sun_position_at_equinox():
    from datetime import datetime
    from cansat_design.optics import sun_position
    el, az = sun_position(datetime(2027, 3, 20, 12, 0), 52.0, 0.0)
    assert el == pytest.approx(90 - 52, abs=1.0)            # declination ≈ 0 at the equinox
    assert az == pytest.approx(180, abs=5)


def test_rayleigh_optical_depth():
    from cansat_design.optics import rayleigh_tau
    assert rayleigh_tau(550) == pytest.approx(0.097, abs=0.002)
    assert rayleigh_tau(450) / rayleigh_tau(680) == pytest.approx((680 / 450) ** 4, rel=0.1)  # ~λ⁻⁴


def test_live_packet_fits_duty_cycle():
    from cansat_design.telemetry import lora_airtime_s
    r = Config().radio
    assert r.payload_bytes == sum(n * b for _, n, b in r.packet) <= r.max_payload_bytes
    assert lora_airtime_s(r.payload_bytes, r.spreading_factor, r.bandwidth_hz) * r.packets_per_s <= r.max_duty_cycle


def _area(poly):
    x, y = poly[:, 0], poly[:, 1]
    return 0.5 * abs(sum(x[i] * y[i - 1] - x[i - 1] * y[i] for i in range(len(x))))


def test_new_shapes_have_the_right_area():
    assert _area(P.canopy_geometry("flat_square", 0.05, 0).pieces[0]) == pytest.approx(0.05)
    for shape in ("flat_octagon", "flat_pentagon", "flat_dodecagon", "cruciform_long"):
        assert _area(P.canopy_geometry(shape, 0.05, 0).pieces[0]) == pytest.approx(0.05)
    hexa, gon = P.canopy_geometry("flat_hexagon", 0.05, 0), P._polygon(0.05, 0, 6, "x")
    assert gon.width_m == pytest.approx(hexa.width_m)          # generic polygon agrees with the hexagon
    c = P.canopy_geometry("conical", 0.05, 20, n_gores=8)
    assert 8 * _area(c.pieces[0]) == pytest.approx(0.05 * (1 - 0.2 ** 2), rel=0.03)  # flat gores ≈ cone surface
    assert c.hole_area_m2 == pytest.approx(0.05 * 0.2 ** 2)


def test_fabric_layout_keeps_pieces_on_the_fabric_and_apart():
    from matplotlib.path import Path as MplPath
    from cansat_design.layout import LayoutItem, build_layout
    lay = build_layout(Config(), [LayoutItem("flat_hexagon", 18, 12, 2, True), LayoutItem("conical", 18, 12, 1)],
                       width_mm=600, length_mm=800)
    assert lay.counts[0] >= 2 and lay.counts[1] == 1
    for p in lay.placed:
        assert p.cut.min() >= 0 and p.cut[:, 0].max() <= 600 and p.cut[:, 1].max() <= 800
    for i, a in enumerate(lay.placed):          # no cut outline has a vertex inside another piece
        for b in lay.placed[i + 1:]:
            assert not MplPath(b.cut).contains_points(a.cut).any()
