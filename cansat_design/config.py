"""All design inputs in one place – edit the defaults here.

Units are in the field names: _m, _mm, _kg, _g, _m_s, _pa, _c, etc.
Every component mass, size and current is a rough ESTIMATE until we weigh and
measure the real parts – replace them as parts arrive and set estimate=False.
"""

from dataclasses import dataclass, field
from datetime import datetime


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
    cost_gbp: float = 0.0               # what we pay for this line (whole pack), from the parts sheet


# Costs mirror the team parts sheet (prices checked 12–13 Nov 2026) – the sheet is the
# source of truth, update both. Parachute fabric and swivels are in Parachute.materials_cost_gbp.
def default_components() -> list[Component]:
    """Flight hardware, seeded from CLAUDE.md. MASSES, SIZES AND CURRENTS ARE ESTIMATES."""
    return [
        Component("Raspberry Pi Pico 2 (with headers)", 4.0, (51, 21, 12), current_ma=25, cost_gbp=5.80),
        Component("Waveshare SX1262 433 MHz LoRa module", 8.0, (51, 21, 10), current_ma=15, cost_gbp=13.90),  # TX ~45 mA bursts, averaged at 1 Hz
        Component("600 mAh LiPo (with LoRa module)", 12.0, (48, 30, 6)),
        Component("Pimoroni Pico Omnibus", 12.0, (94, 52, 15), cost_gbp=8.40),
        Component("433 MHz IPEX spring antenna", 2.0, None, cost_gbp=6.99),                 # 5-pack
        Component("Adafruit AS7341 spectral sensor", 1.5, (25, 18, 5), current_ma=0.5, cost_gbp=15.60),
        Component("Adafruit LTR390 UV + ambient light", 1.2, (25, 18, 5), current_ma=0.1, cost_gbp=4.80),
        Component("Adafruit SHT45 temp + humidity", 1.0, (25, 18, 5), current_ma=0.1, cost_gbp=12.10),
        Component("Adafruit BMP388 pressure", 1.2, (25, 18, 5), current_ma=0.7, cost_gbp=9.70),
        Component("Adafruit LSM6DSO32 IMU", 1.5, (25, 18, 5), current_ma=0.6, cost_gbp=11.20),
        Component("Adafruit BNO085 9-DoF orientation", 2.0, (25, 18, 5), current_ma=12, cost_gbp=27.00),
        Component("ATGM336H GPS + patch antenna", 8.0, (30, 25, 10), current_ma=25, cost_gbp=7.52),
        Component("STEMMA QT cables + jumper leads", 1.5, (30, 10, 5), qty=7, cost_gbp=18.22),  # cable kit + lead + jumpers
        Component("PTFE 1 mm diffusers", 0.5, None, qty=2, cost_gbp=4.75),
        Component("3D-printed PETG shell + bulkheads", 60.0, None),                          # school printer
        Component("Fasteners, hot glue, tape", 10.0, (20, 20, 10)),
        # 4G bulk link – parts sheet 19 Nov 2026 (antenna and capacitor prices are estimates)
        Component("Waveshare A7670E LTE Cat-1 HAT (4G)", 20.0, (65, 31, 10), current_ma=30, cost_gbp=27.60),  # mostly idle on the pad; ~1 A TX bursts
        Component("SparkFun LTE FPC antenna (inside the shell wall)", 2.0, None, cost_gbp=5.00),
        Component("1000 µF capacitor (4G supply)", 2.0, (16, 10, 10), cost_gbp=3.00),
        Component("Pololu U3V40F5 5 V boost converter (4G supply)", 1.5, (15, 15, 6), cost_gbp=5.28),  # HAT needs 5 V; price ex-VAT £4.40 – confirm
        Component("giffgaff PAYG SIM + 2 GB bundle", 0.5, None, cost_gbp=6.00),
        Component("Fast UK shipping (Pi Hut DHL, Amazon, Proto-Pic)", 0.0, None, cost_gbp=19.98, estimate=False),
    ]


def ground_components() -> list[Component]:
    """Ground support equipment – costed separately, outside the £400 budget (confirm with team leader)."""
    return [
        Component("Raspberry Pi Pico 2 (ground receiver)", 0, cost_gbp=5.80),
        Component("Waveshare SX1262 433 MHz LoRa module (ground)", 0, cost_gbp=13.90),
        Component("AS7341 (ground reference)", 0, cost_gbp=15.60),
        Component("LTR390 (ground reference)", 0, cost_gbp=4.80),
        Component("STEMMA QT to female socket lead (ground)", 0, cost_gbp=5.24),
    ]


@dataclass
class MassLimits:
    design_mass_kg: float = 0.325       # what we ballast up to and size the parachute for
    min_kg: float = 0.300
    max_kg: float = 0.350
    ballast_density_g_cm3: float = 7.85  # steel; use 11.3 for lead
    parachute_counts_in_mass: bool = True  # assume the 300–350 g limit includes the parachute (conservative)
    budget_gbp: float = 400.0           # flight hardware only; ground equipment excluded


@dataclass
class Parachute:
    shape: str = "flat_hexagon"         # flat_hexagon | flat_circle | cruciform | hemispherical | flat_square | flat_octagon | conical
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
    n_gores: int = 8                    # hemispherical and conical
    cone_half_angle_deg: float = 60.0   # conical: half-angle from the axis (90° = flat)
    # Opening shock (see README for assumptions)
    opening_speed_m_s: float = 20.0     # speed of the CanSat when the canopy opens
    opening_load_factor: float = 1.8    # Cx – conservative value for solid flat canopies
    inflation_time_s: float = 0.3       # used in the descent simulation
    attachment_rating_n: float = 50.0   # rule: connection must withstand 50 N
    materials_cost_gbp: float = 11.57   # ripstop 1 m £6.99 + swivel 10-pack £4.58 (parts sheet)
    inflated_width_ratio: float = 0.67  # inflated canopy diameter ÷ flat width (typical for flat canopies)


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
class Launch:
    """When and where – for the sun position. Default: national final, York area, midday."""
    time_utc: datetime = datetime(2027, 4, 28, 12, 0)
    latitude_deg: float = 54.0
    longitude_deg: float = -1.1


@dataclass
class Optics:
    """Simple atmosphere for the expected-signal estimate (order of magnitude only)."""
    bands_nm: tuple = (415, 445, 480, 515, 555, 590, 630, 680, 910, 320)  # AS7341 F1–F8, NIR; LTR390 UV ~320
    ratio_pair_nm: tuple = (445, 680)    # blue / red ratio used as the main result
    aod_550: float = 0.15                # aerosol optical depth at 550 nm (UK typical ~0.1–0.2)
    angstrom: float = 1.3                # aerosol Ångström exponent (small particles ~1.5, dust/sea salt ~0.5)
    aerosol_scale_height_m: float = 1000.0
    aerosol_ssa: float = 0.9             # single-scattering albedo (fraction scattered, not absorbed)
    rayleigh_down_fraction: float = 0.5  # share of Rayleigh-scattered light that heads down
    aerosol_down_fraction: float = 0.75  # aerosols scatter mostly forwards
    angle_errors_deg: tuple = (5.0, 2.0, 1.0)  # uncorrected 5° swing, level-only readings, BNO085-corrected


@dataclass
class Radio:
    """LoRa downlink: the compulsory 1 Hz T/P plus a downsampled copy of all the science, as the
    backup if the 4G link drops. Airtime from the Semtech formula."""
    spreading_factor: int = 7
    bandwidth_hz: float = 500e3          # wider band = shorter airtime (range is still km at 10 mW)
    coding_rate: int = 1                 # 1 = 4/5 … 4 = 4/8
    preamble_symbols: int = 8
    packets_per_s: float = 1.0
    max_duty_cycle: float = 0.10         # UK 433 MHz band (IR 2030) – confirm
    max_payload_bytes: int = 255         # SX1262 limit
    # Packet contents: (field, samples per packet, bytes per sample)
    packet: tuple = (
        ("Header: ID, sequence, time", 1, 7),
        ("Pressure (BMP388)", 5, 3),
        ("Temperature (SHT45)", 5, 2),
        ("Humidity (SHT45)", 1, 2),
        ("Spectral, 10 channels (AS7341)", 5, 20),
        ("Tilt + angle to sun per spectral sample", 5, 4),
        ("Orientation quaternion (BNO085)", 1, 8),
        ("UV + visible (LTR390)", 2, 4),
        ("GPS lat, lon, altitude", 1, 10),
        ("Swing/accel summary (LSM6DSO32)", 1, 4),
        ("Battery + status flags", 1, 2),
    )

    @property
    def payload_bytes(self) -> int:
        return sum(n * b for _, n, b in self.packet)


@dataclass
class Cellular:
    """4G bulk link (A7670E, LTE Cat-1, 2G fallback off): sends the full-rate log live.
    The CanSat is assumed NOT recoverable – the flash log is only a buffer for resending."""
    uplink_kbps: float = 100.0          # conservative usable uplink at weak signal (Cat-1 peak ~5 Mbps)
    overhead: float = 1.3               # UDP/IP + our headers + resends
    peak_current_a: float = 1.0         # TX bursts – confirm on the datasheet / measure
    battery_peak_a: float = 1.2         # what the 600 mAh LiPo can supply (~2C) – confirm
    active_minutes: float = 15.0        # sending at full rate: countdown, flight, after landing
    bundle_mb: float = 1000.0           # pay-as-you-go data bundle


@dataclass
class Logging:
    """Planned log streams (name, rate Hz, bytes per sample incl. 4-byte timestamp) – see CLAUDE.md."""
    streams: tuple = (
        ("BMP388 pressure + temp", 25, 12),
        ("SHT45 temp + RH", 5, 12),
        ("AS7341 11 channels", 5, 26),
        ("LTR390 UV/ALS", 4, 8),
        ("BNO085 quaternion", 100, 12),
        ("LSM6DSO32 accel + gyro", 104, 16),
        ("GPS fix", 1, 20),
    )
    free_flash_mb: float = 2.0           # Pico 2 has 4 MB; MicroPython + code take ~2 MB (estimate – check)
    full_rate_minutes_needed: float = 10.0  # launch → landing + recovery margin
    sht45_time_constant_s: float = 2.0


@dataclass
class Config:
    envelope: Envelope = field(default_factory=Envelope)
    components: list[Component] = field(default_factory=default_components)
    mass: MassLimits = field(default_factory=MassLimits)
    parachute: Parachute = field(default_factory=Parachute)
    air: Air = field(default_factory=Air)
    mission: Mission = field(default_factory=Mission)
    ground: list[Component] = field(default_factory=ground_components)
    launch: Launch = field(default_factory=Launch)
    optics: Optics = field(default_factory=Optics)
    radio: Radio = field(default_factory=Radio)
    cellular: Cellular = field(default_factory=Cellular)
    logging: Logging = field(default_factory=Logging)
