"""Radio airtime / duty cycle and the flash logging budget."""

import math
from dataclasses import dataclass


def lora_airtime_s(payload_bytes: int, sf: int = 7, bw_hz: float = 125e3, cr: int = 1,
                   preamble: int = 8, explicit_header: bool = True, crc: bool = True) -> float:
    """Time on air of one LoRa packet (Semtech SX126x datasheet formula)."""
    t_sym = 2 ** sf / bw_hz
    de = 1 if t_sym > 0.016 else 0                     # low data rate optimisation
    ih = 0 if explicit_header else 1
    n = 8 + max(math.ceil((8 * payload_bytes - 4 * sf + 28 + 16 * crc - 20 * ih) / (4 * (sf - 2 * de))) * (cr + 4), 0)
    return (preamble + 4.25) * t_sym + n * t_sym


@dataclass
class LogBudget:
    bytes_per_s: float
    minutes_available: float
    per_stream: list            # (name, rate Hz, bytes/s)


def log_budget(logging_cfg) -> LogBudget:
    rows = [(name, rate, rate * size) for name, rate, size in logging_cfg.streams]
    total = sum(r[2] for r in rows)
    return LogBudget(total, logging_cfg.free_flash_mb * 1e6 / total / 60, rows)
