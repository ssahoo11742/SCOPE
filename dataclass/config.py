
from dataclasses import dataclass, field
import numpy as np
# ============================================================================
# CONFIGURATION CLASSES
# ============================================================================
@dataclass
class SimulationConfig:
    """Main simulation configuration"""
    time_steps: int = 20000
    dt: float = 10  # seconds
    base_error_rate: float = 0.90
    log_file: str = "nos3_full_telemetry.csv"
    enable_live_plot: bool = False

@dataclass
class SatelliteConfig:
    """Satellite physical properties"""
    mass: float = 100  # kg
    solar_panel_area: float = 2.0  # m^2
    solar_panel_efficiency: float = 0.28
    battery_capacity: float = 20000  # Wh
    power_draw_baseline: float = 50  # W
    moment_of_inertia: np.ndarray = field(default_factory=lambda: np.array([10.0, 10.0, 15.0]))
    reaction_wheel_max_torque: float = 0.1  # N*m
    reaction_wheel_max_momentum: float = 10.0  # N*m*s
    drag_coefficient: float = 2.2
    cross_section_area: float = 1.5  # m^2
    thermal_mass: float = 500  # J/K
    emissivity: float = 0.85
    absorptivity: float = 0.9

@dataclass
class GroundStationConfig:
    """Ground station properties"""
    latitude: float = 34.5  # degrees (Kirtland AFB)
    longitude: float = -106.5  # degrees
    min_elevation: float = 10  # degrees
    max_comm_range: float = 2500  # km
    frequency_hz: float = 2.2e9  # S-band

@dataclass
class ControlConfig:
    """Control law gains"""
    orbit_gain: float = 0.00001
    attitude_gain_p: float = 0.02
    attitude_gain_d: float = 0.05
    thrust_noise_std: float = 0.0001
    torque_noise_std: float = 0.001