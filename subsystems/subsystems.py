import numpy as np
import random
from dataclass.config import SatelliteConfig, GroundStationConfig
from dataclass.sat_state import PowerState, ThermalState, CommsState
from dataclass.constants import PhysicalConstants

# ============================================================================
# SUBSYSTEM CLASSES
# ============================================================================
class PowerSubsystem:
    def __init__(self, sat_config: SatelliteConfig, constants: PhysicalConstants):
        self.sat_config = sat_config
        self.constants = constants
        self.state = PowerState(
            battery_charge=sat_config.battery_capacity * 0.8,
            solar_generation=0,
            power_consumption=sat_config.power_draw_baseline,
            battery_voltage=30.0,
            battery_temp=298.0
        )
    
    def update(self, in_eclipse: bool, dt_hours: float, consumption_w: float, temp_k: float) -> PowerState:
        if in_eclipse:
            generation = 0
        else:
            temp_eff = 1.0 - 0.004 * (temp_k - 298)
            generation = (self.constants.SOLAR_FLUX * self.sat_config.solar_panel_area * 
                         self.sat_config.solar_panel_efficiency * max(0.5, temp_eff))
        
        net_power = generation - consumption_w
        new_charge = self.state.battery_charge + net_power * dt_hours
        new_charge = max(0, min(self.sat_config.battery_capacity, new_charge))
        
        soc = new_charge / self.sat_config.battery_capacity
        voltage = 28.0 + 5.6 * (soc - 0.5)
        
        heat_gen = consumption_w * 0.05
        new_temp = temp_k + (heat_gen - 10) * dt_hours / 100
        new_temp = max(250, min(320, new_temp))
        
        self.state = PowerState(new_charge, generation, consumption_w, voltage, new_temp)
        return self.state

class ThermalSubsystem:
    def __init__(self, sat_config: SatelliteConfig, constants: PhysicalConstants):
        self.sat_config = sat_config
        self.constants = constants
        self.state = ThermalState(
            component_temps={'cpu': 298.0, 'battery': 298.0, 'radio': 298.0, 'solar_panel': 298.0},
            heat_generation=0,
            heat_dissipation=0
        )
    
    def update(self, power_consumption: float, in_eclipse: bool, dt: float) -> ThermalState:
        temps = self.state.component_temps.copy()
        
        heat_gen = power_consumption * 0.15
        if not in_eclipse:
            heat_gen += self.constants.SOLAR_FLUX * self.sat_config.absorptivity * self.sat_config.cross_section_area * 0.5
        
        avg_temp = np.mean(list(temps.values()))
        heat_dissipation = (self.sat_config.emissivity * self.constants.STEFAN_BOLTZMANN * 
                           self.sat_config.cross_section_area * (avg_temp**4 - self.constants.SPACE_TEMP**4))
        
        net_heat = heat_gen - heat_dissipation
        temp_change = net_heat * dt / self.sat_config.thermal_mass
        
        for component in temps:
            temps[component] += temp_change + random.uniform(-2, 2)
            temps[component] = max(200, min(350, temps[component]))
        
        self.state = ThermalState(temps, heat_gen, heat_dissipation)
        return self.state

class CommunicationSubsystem:
    def __init__(self, gs_config: GroundStationConfig, constants: PhysicalConstants):
        self.gs_config = gs_config
        self.constants = constants
        self.state = CommsState(False, 0.0, 0.0, 0.0, 0.0)
    
    def update(self, sat_pos: np.ndarray, sat_vel: np.ndarray, earth_radius: float) -> CommsState:
        gs_lat_rad = self.gs_config.latitude * np.pi / 180
        gs_lon_rad = self.gs_config.longitude * np.pi / 180
        gs_pos = earth_radius * np.array([
            np.cos(gs_lat_rad) * np.cos(gs_lon_rad),
            np.cos(gs_lat_rad) * np.sin(gs_lon_rad),
            np.sin(gs_lat_rad)
        ])
        
        range_vec = sat_pos - gs_pos
        range_km = np.linalg.norm(range_vec)
        
        local_vertical = gs_pos / earth_radius
        elevation_rad = np.pi/2 - np.arccos(np.dot(range_vec, local_vertical) / range_km)
        elevation_deg = elevation_rad * 180 / np.pi
        
        visible = elevation_deg >= self.gs_config.min_elevation and range_km <= self.gs_config.max_comm_range
        
        # Doppler shift
        range_unit = range_vec / range_km
        radial_velocity = np.dot(sat_vel, range_unit)
        doppler = -self.gs_config.frequency_hz * radial_velocity / self.constants.SPEED_OF_LIGHT
        
        signal_strength = max(0, 1.0 - range_km / self.gs_config.max_comm_range) if visible else 0.0
        
        self.state = CommsState(visible, signal_strength, range_km, doppler, elevation_deg)
        return self.state