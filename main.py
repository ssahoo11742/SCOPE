import numpy as np
from dataclass.config import SimulationConfig, SatelliteConfig, GroundStationConfig, ControlConfig, DefenseSystemConfig
from dataclass.cyber import CyberAttack, CyberScenario
from simulator.sim import SatelliteSimulator

# ============================================================================
# MAIN EXECUTION
# ============================================================================
if __name__ == "__main__":
    # Configure simulation
    sim_config = SimulationConfig(
        time_steps=1000,
        dt=10,
        base_error_rate=0.2,  # Was 0.10 - now only 1% errors
        log_file="scope_full_telemetry.csv",
        enable_live_plot=False
    )
    
    sat_config = SatelliteConfig(
        mass=100,
        solar_panel_area=1.0,
        solar_panel_efficiency=0.20,
        battery_capacity=20000,
        power_draw_baseline=150,
        moment_of_inertia=np.array([10.0, 10.0, 15.0]),
        reaction_wheel_max_torque=0.1,
        reaction_wheel_max_momentum=10.0,
        drag_coefficient=2.2,
        cross_section_area=1.5,
        thermal_mass=500,
        emissivity=0.85,
        absorptivity=0.9
    )
    
    gs_config = GroundStationConfig(
        latitude=34.5,
        longitude=-106.5,
        min_elevation=10,
        max_comm_range=2500,
        frequency_hz=2.2e9
    )
    
    defense_config = DefenseSystemConfig(
        enable_key_auth=True
    )
    
    control_config = ControlConfig(
        orbit_gain=5e-8,        # Extremely gentle orbit control  
        attitude_gain_p=0.008,   # Very gentle pointing
        attitude_gain_d=0.015,   # Gentle damping
        thrust_noise_std=0.00005,
        torque_noise_std=0.0001
    )
    # Define cyber attack scenarios
    cyber_scenarios = [
        CyberScenario(CyberAttack.NONE, 0, 500, 0, debug=False, spoof_mode="insert"),
        CyberScenario(CyberAttack.COMMAND_SPOOFING, 5000, 3000, 0.7, debug=True, spoof_mode="insert", has_compromised_key=False),
        # CyberScenario(CyberAttack.DENIAL_OF_SERVICE, 1200, 200, 0.9),
        # CyberScenario(CyberAttack.BATTERY_DEPLETION, 1000, 400, 0.8),
    ]
    
    # Create and run simulator
    simulator = SatelliteSimulator(
        sim_config=sim_config,
        sat_config=sat_config,
        gs_config=gs_config,
        control_config=control_config,
        defense_config=defense_config,
        cyber_scenarios=cyber_scenarios,
        initial_altitude=1000
    )
    
    # Run simulation
    simulator.run()
    
    # Generate visualizations
    simulator.visualize()
    
    # Print summary
    simulator.print_summary()
