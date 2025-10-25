
from dataclasses import dataclass
# ============================================================================
# PHYSICAL CONSTANTS
# ============================================================================
@dataclass
class PhysicalConstants:
    """Earth and space physical constants"""
    EARTH_RADIUS: float = 6371.0  # km
    EARTH_MU: float = 398600.4418  # km^3/s^2
    EARTH_J2: float = 1.08263e-3
    SOLAR_FLUX: float = 1361  # W/m^2
    STEFAN_BOLTZMANN: float = 5.67e-8  # W/m^2/K^4
    SPACE_TEMP: float = 3  # K
    SPEED_OF_LIGHT: float = 299792.458  # km/s
