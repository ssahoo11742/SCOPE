from dataclasses import dataclass, field
import numpy as np
from typing import Dict
# ============================================================================
# STATE CLASSES
# ============================================================================
@dataclass
class OrbitalState:
    position: np.ndarray  # [x, y, z] km ECI
    velocity: np.ndarray  # [vx, vy, vz] km/s

@dataclass
class AttitudeState:
    quaternion: np.ndarray  # [q0, q1, q2, q3]
    angular_velocity: np.ndarray  # [wx, wy, wz] rad/s
    reaction_wheel_momentum: np.ndarray  # [h1, h2, h3] N*m*s

@dataclass
class PowerState:
    battery_charge: float  # Wh
    solar_generation: float  # W
    power_consumption: float  # W
    battery_voltage: float  # V
    battery_temp: float  # K

@dataclass
class ThermalState:
    component_temps: Dict[str, float]  # K
    heat_generation: float  # W
    heat_dissipation: float  # W

@dataclass
class CommsState:
    link_active: bool
    signal_strength: float
    range_km: float
    doppler_shift_hz: float
    elevation_deg: float

@dataclass
class CCSDSPacket:
    """CCSDS Space Packet format"""
    version: int = 0
    packet_type: int = 0
    sec_hdr_flag: int = 1
    apid: int = 0
    sequence_flags: int = 3
    sequence_count: int = 0
    data_length: int = 0
    timestamp: float = 0.0
    data: dict = field(default_factory=dict)
    checksum: str = ""