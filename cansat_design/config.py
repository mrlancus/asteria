"""All design inputs in one place – edit the defaults here.

Units are in the field names: _m, _mm, _kg, _g, _m_s, _pa, _c, etc.
Every component mass, size and current is a rough ESTIMATE until we weigh and
measure the real parts – replace them as parts arrive and set estimate=False.
"""

from dataclasses import dataclass, field


@dataclass
class Envelope:
    """The soda-can envelope from the competition rules."""
    height_mm: float = 115.0
    diameter_mm: float = 66.0
    wall_thickness_mm: float = 2.0      # PETG shell wall / end caps (our design choice)
    packing_efficiency: float = 0.6     # fraction of the inner volume we can realistically fill
    antenna_external_mm: float = 30.0   # spring antenna sticking out of the top/bottom
    antenna_max_mm: float = 30.0        # rule limit


@dataclass
class Component:
    name: str
    mass_g: float
    size_mm: tuple | None = None        # bounding box (L, W, H); None = not volume-checked (e.g. the shell itself)
    current_ma: float = 0.0             # average current draw, for the battery-life check
    qty: int = 1
    estimate: bool = True               # True until weighed / measured


def default_components() -> list[Component]:
    """Seeded from the hardware list in CLAUDE.md. ALL VALUES ARE ESTIMATES."""
    return [
        Component("Raspberry Pi Pico 2 (with headers)", 4.0, (51, 21, 12), current_ma=25),
        Component("Waveshare SX1262 433 MHz LoRa module", 8.0, (51, 21, 10), current_ma=15),  # TX ~45 mA bursts, averaged at 1 Hz
        Component("600 mAh LiPo (with LoRa module)", 12.0, (48, 30, 6)),
        Component("Pimoroni Pico Omnibus", 12.0, (94, 52, 15)),
        Component("433 MHz IPEX spring antenna", 2.0, None),
        Component("Adafruit AS7341 spectral sensor", 1.5, (25, 18, 5), current_ma=0.5),
        Component("Adafruit LTR390 UV + ambient light", 1.2, (25, 18, 5), current_ma=0.1),
        Component("Adafruit SHT45 temp + humidity", 1.0, (25, 18, 5), current_ma=0.1),
        Component("Adafruit BMP388 pressure", 1.2, (25, 18, 5), current_ma=0.7),
        Component("Adafruit LSM6DSO32 IMU", 1.5, (25, 18, 5), current_ma=0.6),
        Component("Adafruit BNO085 9-DoF orientation", 2.0, (25, 18, 5), current_ma=12),
        Component("ATGM336H GPS + patch antenna", 8.0, (30, 25, 10), current_ma=25),
        Component("STEMMA QT cables + jumper leads", 1.5, (30, 10, 5), qty=7),
        Component("PTFE 1 mm diffusers", 0.5, None, qty=2),
        Component("3D-printed PETG shell + bulkheads", 60.0, None),
        Component("Fasteners, hot glue, tape", 10.0, (20, 20, 10)),
    ]


@dataclass
class MassLimits:
    design_mass_kg: float = 0.325       # what we ballast up to and size the parachute for
    min_kg: float = 0.300
    max_kg: float = 0.350
    ballast_density_g_cm3: float = 7.85  # steel; use 11.3 for lead
    parachute_counts_in_mass: bool = True  # assume the 300–350 g limit includes the parachute (conservative)


@dataclass
class Parachute:
    shape: str = "flat_hexagon"         # flat_hexagon | flat_circle | cruciform | hemispherical
    cd: float | None = None             # None = use the default for the shape (see parachute.SHAPES)
    spill_hole_pct: float = 18.0        # spill-hole diameter as % of canopy width
    vent_cd_loss: float = 1.0           # k in Cd_eff = Cd0·(1 − k·λ), see README
    line_length_factor: float = 1.25    # shroud line length as a multiple of canopy width (1–1.5)
    line_length_m: float | None = None  # set to override the factor
    n_lines: int | None = None          # None = shape default
    riser_length_m: float = 0.15        # swivel + riser between the line confluence and the can
    fabric_g_m2: float = 40.0           # ripstop nylon ~35–45 g/m²
    line_g_m: float = 1.0               # light braided nylon cord
    swivel_g: float = 3.0
    reinforcement_g: float = 2.0        # tape, thread, line attachment patches
    seam_allowance_mm: float = 10.0     # hem / seam added around every cut edge
    cruciform_span_ratio: float = 3.0   # total span / arm width (3 = arms as long as they are wide)
    n_gores: int = 8                    # hemispherical only
    # Opening shock (see README for assumptions)
    opening_speed_m_s: float = 20.0     # speed of the CanSat when the canopy opens
    opening_load_factor: float = 1.8    # Cx – conservative value for solid flat canopies
    inflation_time_s: float = 0.3       # used in the descent simulation
    attachment_rating_n: float = 50.0   # rule: connection must withstand 50 N


@dataclass
class Air:
    density_kg_m3: float = 1.225        # used if nothing below is set
    use_isa: bool = False               # True = ISA density at site_elevation_m
    site_elevation_m: float = 0.0
    temperature_c: float | None = None  # set both T and p to compute density from a measurement
    pressure_pa: float | None = None


@dataclass
class Mission:
    target_speed_m_s: float = 12.0
    min_speed_m_s: float = 10.0
    max_speed_m_s: float = 15.0
    apogee_m: float = 400.0             # deployment height above ground
    telemetry_hz: float = 1.0
    launch_g: float = 20.0
    battery_mah: float = 600.0
    battery_usable_fraction: float = 0.8
    required_runtime_h: float = 3.0
    tx_power_dbm: float = 10.0
    max_tx_power_dbm: float = 10.0
    # Swing model
    swing_initial_deg: float = 20.0     # disturbance at deployment
    swing_threshold_deg: float = 5.0    # tilt we consider "good enough" for the light sensors
    can_side_cd: float = 1.0            # drag of the can moving sideways (cylinder side-on)


@dataclass
class Config:
    envelope: Envelope = field(default_factory=Envelope)
    components: list[Component] = field(default_factory=default_components)
    mass: MassLimits = field(default_factory=MassLimits)
    parachute: Parachute = field(default_factory=Parachute)
    air: Air = field(default_factory=Air)
    mission: Mission = field(default_factory=Mission)
