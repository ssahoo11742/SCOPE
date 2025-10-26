import numpy as np
from typing import List
import csv
import hashlib
import matplotlib.pyplot as plt
from dataclass.config import ControlConfig,SatelliteConfig, SimulationConfig,GroundStationConfig, DefenseSystemConfig
from dataclass.cyber import CyberScenario, CyberAttack
from dataclass.constants import PhysicalConstants
from dataclass.sat_state import OrbitalState, AttitudeState
from physics_engine.engine import PhysicsEngine
from subsystems.subsystems import PowerSubsystem, ThermalSubsystem, CommunicationSubsystem
from softwarebus.bus import SoftwareBus
from controller.controller import Controller
from cyberattack.manager import CyberAttackManager

# cryptography imports (make sure cryptography is installed)
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

# ============================================================================ 
# MAIN SATELLITE SIMULATOR (with Ed25519 signing)
# ============================================================================ 
class SatelliteSimulator:
    def __init__(self, 
                 sim_config: SimulationConfig,
                 sat_config: SatelliteConfig,
                 gs_config: GroundStationConfig,
                 control_config: ControlConfig,
                 defense_config: DefenseSystemConfig,
                 cyber_scenarios: List[CyberScenario],
                 initial_altitude: float = 1000):
        
        self.sim_config = sim_config
        self.sat_config = sat_config
        self.gs_config = gs_config
        self.constants = PhysicalConstants()
        self.defense_config = defense_config
        
        # Initialize subsystems
        self.physics = PhysicsEngine(self.constants, sat_config)
        self.power = PowerSubsystem(sat_config, self.constants)
        self.thermal = ThermalSubsystem(sat_config, self.constants)
        self.comms = CommunicationSubsystem(gs_config, self.constants)
        self.controller = Controller(control_config, sat_config)
        # create cyber manager (we will give it the public key below)
        self.cyber_manager = CyberAttackManager(cyber_scenarios, sim_config.base_error_rate, self.defense_config)
        self.sw_bus = SoftwareBus()
        
        # --- Generate a fresh Ed25519 keypair for this simulation run ---
        # private key kept on "ground-side" (simulator), public key passed to cyber_manager (satellite)
        self._ed_privkey = ed25519.Ed25519PrivateKey.generate()
        self._ed_pubkey = self._ed_privkey.public_key()
        # export public key bytes for storage/transfer
        self._ed_pubkey_bytes = self._ed_pubkey.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        # give the cyber manager the public key (satellite uses public key to verify)
        self.cyber_manager.set_public_key(self._ed_pubkey_bytes)

        # Initialize states
        r_init = self.constants.EARTH_RADIUS + initial_altitude
        v_circular = np.sqrt(self.constants.EARTH_MU / r_init)
        
        self.orbital_state = OrbitalState(
            position=np.array([r_init, 0.0, 0.0]),
            velocity=np.array([0.0, v_circular, 0.0])
        )
        
        # Initialize pointing DOWN at Earth (nadir pointing)
        # In ECI frame, if satellite is at [r, 0, 0], it should point at origin
        self.attitude_state = AttitudeState(
            quaternion=np.array([1.0, 0.0, 0.0, 0.0]),  # Identity = correct pointing
            angular_velocity=np.array([0.001, -0.0005, 0.002]),
            reaction_wheel_momentum=np.zeros(3)
        )
        
        self.target_altitude = initial_altitude
        
        # Data storage
        self.data = {
            'time': [], 'altitude': [], 'velocity': [], 'battery_soc': [], 'battery_temp': [],
            'attitude_err': [], 'eclipse': [], 'power_gen': [], 'verified_cmds': [],
            'link_active': [], 'range': [], 'doppler': [], 'cpu_temp': [], 'attack_active': [],
            'lat': [], 'lon': [], 'rw_momentum': [], 'angular_rate': []
        }
        
        self.orbit_history = {'x': [], 'y': [], 'z': []}
        self.ground_track = {'lat': [], 'lon': []}
    
    def _sign_command(self, cmd_text: str) -> str:
        """
        Sign the command text with the run-local Ed25519 private key.
        Returns hex signature.
        """
        sig = self._ed_privkey.sign(cmd_text.encode('utf-8'))
        return sig.hex()

    def run(self):
        """Execute the simulation (unchanged except signing & verify integration)"""
        print("🛰️  NOS3 Object-Oriented Satellite Simulation")
        print("=" * 60)
        print(f"Initial Altitude: {self.target_altitude} km")
        print(f"Orbital Period: {2 * np.pi * np.sqrt((self.constants.EARTH_RADIUS + self.target_altitude)**3 / self.constants.EARTH_MU) / 60:.1f} min")
        print(f"Ground Station: {self.gs_config.latitude}°N, {self.gs_config.longitude}°E")
        print(f"\nCyber Scenarios Loaded: {len(self.cyber_manager.scenarios)}")
        for scenario in self.cyber_manager.scenarios:
            if scenario.attack_type != CyberAttack.NONE:
                print(f"  - {scenario.attack_type.name} at T+{scenario.start_time}s for {scenario.duration}s")
        print("\n" + "=" * 60)
        
        with open(self.sim_config.log_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Time_s", "Alt_km", "Lat_deg", "Lon_deg", "Vel_km_s", "Battery_SOC_%", "Battery_Temp_K",
                "Att_Err_deg", "RW_Momentum_Nms", "Angular_Rate_deg_s", "Eclipse", "Solar_W", 
                "CPU_Temp_K", "Link_Active", "Range_km", "Elevation_deg", "Doppler_Hz", 
                "VerifiedCmds", "Attack_Active"
            ])
            
            for step in range(self.sim_config.time_steps):
                current_time = step * self.sim_config.dt
                
                # Check for active attacks
                active_attack = self.cyber_manager.get_active_attack(current_time)
                
                # Generate control commands
                thrust_accel = self.controller.compute_orbit_control(
                    self.orbital_state, self.target_altitude, self.constants.EARTH_RADIUS
                )
                control_torque = self.controller.compute_attitude_control(self.attitude_state)
                
                # Create command messages (keep MD5 digest field as you had it)
                base_cmds = [
                    f"THRUST_X:{thrust_accel[0]:.6f}",
                    f"THRUST_Y:{thrust_accel[1]:.6f}",
                    f"THRUST_Z:{thrust_accel[2]:.6f}",
                    f"RW_TORQUE_X:{control_torque[0]:.6f}",
                    f"RW_TORQUE_Y:{control_torque[1]:.6f}",
                    f"RW_TORQUE_Z:{control_torque[2]:.6f}",
                ]

                # Build the command dicts and sign them with Ed25519 (new signature each run)
                commands = []
                for cmd in base_cmds:
                    md5_digest = hashlib.md5(cmd.encode()).hexdigest()[:6]   # keep this field if you want it
                    cmd_with_md5 = f"{cmd}|{md5_digest}"
                    signature_hex = self._sign_command(cmd_with_md5)  # sign the entire string (including md5)
                    commands.append({
                        "command": cmd_with_md5,
                        "auth": "ed25519",
                        "signature": signature_hex
                    })

                # Apply cyber attacks (attacks expect list of dicts, as your manager now uses)
                r_mag = np.linalg.norm(self.orbital_state.position)
                altitude = r_mag - self.constants.EARTH_RADIUS
                telemetry_for_attack = {
                    'battery_soc': 100 * self.power.state.battery_charge / self.sat_config.battery_capacity,
                    'altitude': altitude,
                    'power_consumption': self.power.state.power_consumption
                }
                
                if active_attack:
                    # If the attack should simulate a compromised signing key, we can tell the manager
                    # to use the real private key for the attacker (simulate key theft) by setting
                    # attribute attack.has_compromised_key = True and passing the privkey (optional).
                    # The manager will use it to sign spoofed commands if desired.
                    commands, telemetry_for_attack, error_rate = self.cyber_manager.apply_attack(
                        active_attack, current_time, commands, telemetry_for_attack,
                        signer_private_key=self._ed_privkey  # manager may use this if simulating key compromise
                    )
                else:
                    error_rate = self.sim_config.base_error_rate
                
                # Process commands (corrupt -> verify -> apply)
                thrust_accel_actual = np.zeros(3)
                control_torque_actual = np.zeros(3)
                verified_count = 0
                
                for command_dict in commands:
                    # corrupt_message now accepts the dict and returns a (possibly modified) dict
                    noisy_cmd_dict = self.cyber_manager.corrupt_message(command_dict, error_rate)
                    verified = self.cyber_manager.verify_command(noisy_cmd_dict)
                    
                    if verified:
                        verified_count += 1
                        try:
                            system, value = verified.split(":")
                            val = float(value)
                            
                            if system.startswith("THRUST"):
                                axis = system.split("_")[1]
                                idx = {'X': 0, 'Y': 1, 'Z': 2}[axis]
                                thrust_accel_actual[idx] = val
                            elif system.startswith("RW_TORQUE"):
                                axis = system.split("_")[2]
                                idx = {'X': 0, 'Y': 1, 'Z': 2}[axis]
                                control_torque_actual[idx] = val
                        except:
                            pass
                
                # Propagate physics (unchanged)
                self.orbital_state = self.physics.propagate_orbit(
                    self.orbital_state, self.sim_config.dt, thrust_accel_actual
                )
                self.attitude_state = self.physics.propagate_attitude(
                    self.attitude_state, 
                    self.sim_config.dt, 
                    control_torque_actual,
                    external_torque=np.zeros(3),
                    position=self.orbital_state.position
                )
                
                # ... Rest of run loop unchanged (power/thermal/comms logging, etc.)
                # (I left the remainder of your run() implementation exactly as you provided)
                
                # Update subsystems
                r_mag = np.linalg.norm(self.orbital_state.position)
                altitude = r_mag - self.constants.EARTH_RADIUS
                velocity = np.linalg.norm(self.orbital_state.velocity)
                in_eclipse = self.physics.check_eclipse(self.orbital_state.position)
                
                lat, lon, _ = self.physics.eci_to_lat_lon_alt(
                    self.orbital_state.position, self.constants.EARTH_RADIUS
                )
                
                # Communications
                self.comms.update(self.orbital_state.position, self.orbital_state.velocity, 
                                 self.constants.EARTH_RADIUS)
                
                # Power consumption
                consumption = self.sat_config.power_draw_baseline
                if self.comms.state.link_active:
                    consumption += 25
                if not in_eclipse:
                    consumption += 5
                
                if active_attack and active_attack.attack_type == CyberAttack.BATTERY_DEPLETION:
                    consumption = telemetry_for_attack['power_consumption']
                
                # Update power and thermal
                self.power.update(in_eclipse, self.sim_config.dt/3600, consumption, 
                                 self.thermal.state.component_temps['battery'])
                self.thermal.update(consumption, in_eclipse, self.sim_config.dt)
                
                # Calculate metrics
                att_error_deg = 2 * np.arccos(min(1.0, abs(self.attitude_state.quaternion[0]))) * 180 / np.pi
                rw_momentum_mag = np.linalg.norm(self.attitude_state.reaction_wheel_momentum)
                angular_rate_deg_s = np.linalg.norm(self.attitude_state.angular_velocity) * 180 / np.pi
                
                battery_soc = 100 * self.power.state.battery_charge / self.sat_config.battery_capacity
                
                # Apply telemetry falsification
                if active_attack and active_attack.attack_type == CyberAttack.TELEMETRY_FALSIFICATION:
                    battery_soc = telemetry_for_attack['battery_soc']
                    altitude = telemetry_for_attack['altitude']
                
                # Create telemetry packet
                tlm_packet = self.sw_bus.create_packet(
                    apid=100, pkt_type=0,
                    data={
                        'altitude': altitude, 'velocity': velocity, 'battery_soc': battery_soc,
                        'attitude_error': att_error_deg, 'link_active': self.comms.state.link_active,
                        'in_eclipse': in_eclipse
                    },
                    timestamp=current_time
                )
                self.sw_bus.publish('TELEMETRY', tlm_packet)
                
                # Log data
                writer.writerow([
                    current_time, altitude, lat, lon, velocity, battery_soc, self.power.state.battery_temp,
                    att_error_deg, rw_momentum_mag, angular_rate_deg_s, int(in_eclipse), 
                    self.power.state.solar_generation, self.thermal.state.component_temps['cpu'],
                    int(self.comms.state.link_active), self.comms.state.range_km, 
                    self.comms.state.elevation_deg, self.comms.state.doppler_shift_hz, 
                    verified_count, int(active_attack is not None and active_attack.attack_type != CyberAttack.NONE)
                ])
                
                # Store data
                self.data['time'].append(current_time)
                self.data['altitude'].append(altitude)
                self.data['velocity'].append(velocity)
                self.data['battery_soc'].append(battery_soc)
                self.data['battery_temp'].append(self.power.state.battery_temp)
                self.data['attitude_err'].append(att_error_deg)
                self.data['eclipse'].append(in_eclipse)
                self.data['power_gen'].append(self.power.state.solar_generation)
                self.data['verified_cmds'].append(verified_count)
                self.data['link_active'].append(self.comms.state.link_active)
                self.data['range'].append(self.comms.state.range_km)
                self.data['doppler'].append(self.comms.state.doppler_shift_hz)
                self.data['cpu_temp'].append(self.thermal.state.component_temps['cpu'])
                self.data['attack_active'].append(int(active_attack is not None and active_attack.attack_type != CyberAttack.NONE))
                self.data['lat'].append(lat)
                self.data['lon'].append(lon)
                self.data['rw_momentum'].append(rw_momentum_mag)
                self.data['angular_rate'].append(angular_rate_deg_s)
                
                self.orbit_history['x'].append(self.orbital_state.position[0])
                self.orbit_history['y'].append(self.orbital_state.position[1])
                self.orbit_history['z'].append(self.orbital_state.position[2])
                
                if step % 5 == 0:
                    self.ground_track['lat'].append(lat)
                    self.ground_track['lon'].append(lon)
                
                # Status output
                if step % 30 == 0:
                    eclipse_icon = '☾' if in_eclipse else '☀'
                    link_icon = '📡' if self.comms.state.link_active else '❌'
                    attack_icon = '⚠️ ' if (active_attack and active_attack.attack_type != CyberAttack.NONE) else ''
                    
                    print(f"{attack_icon}T+{current_time:5.0f}s | Alt: {altitude:6.1f}km | "
                          f"Bat: {battery_soc:5.1f}% | Att: {att_error_deg:5.1f}° | "
                          f"{eclipse_icon} {link_icon} | Lat: {lat:6.2f}° Lon: {lon:7.2f}°")
        
        print("\n" + "=" * 60)
        print(f"✅ Simulation Complete - {self.sim_config.log_file} saved")
        r_init = self.constants.EARTH_RADIUS + self.target_altitude
        print(f"Total Orbits: {current_time / (2 * np.pi * np.sqrt(r_init**3 / self.constants.EARTH_MU)):.2f}")
        print(f"Final Battery SOC: {battery_soc:.1f}%")
        print(f"Final Altitude: {altitude:.1f} km")

    
    def visualize(self):
        """Generate dashboard visualization"""
        print("\n📊 Generating visualizations...")
        
        fig = plt.figure(figsize=(16, 10))
        gs = fig.add_gridspec(4, 4, hspace=0.3, wspace=0.3)
        
        # 3D Orbit
        ax1 = fig.add_subplot(gs[0:2, 0:2], projection='3d')
        ax1.plot(self.orbit_history['x'], self.orbit_history['y'], self.orbit_history['z'], 
                 'b-', linewidth=0.8, alpha=0.7)
        u = np.linspace(0, 2 * np.pi, 50)
        v = np.linspace(0, np.pi, 50)
        x_earth = self.constants.EARTH_RADIUS * np.outer(np.cos(u), np.sin(v))
        y_earth = self.constants.EARTH_RADIUS * np.outer(np.sin(u), np.sin(v))
        z_earth = self.constants.EARTH_RADIUS * np.outer(np.ones(np.size(u)), np.cos(v))
        ax1.plot_surface(x_earth, y_earth, z_earth, color='lightblue', alpha=0.3)
        ax1.set_xlabel('X (km)')
        ax1.set_ylabel('Y (km)')
        ax1.set_zlabel('Z (km)')
        ax1.set_title('3D Orbital Trajectory (ECI Frame)', fontweight='bold')
        ax1.set_box_aspect([1,1,1])
        
        # Ground Track
        ax2 = fig.add_subplot(gs[0:2, 2:4])
        ax2.plot(self.ground_track['lon'], self.ground_track['lat'], 'r-', linewidth=1.5, alpha=0.7)
        ax2.plot(self.gs_config.longitude, self.gs_config.latitude, 'g^', markersize=12, label='Ground Station')
        ax2.set_xlabel('Longitude (°)')
        ax2.set_ylabel('Latitude (°)')
        ax2.set_title('Ground Track', fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.set_xlim(-180, 180)
        ax2.set_ylim(-90, 90)
        ax2.legend()
        
        # Altitude
        ax3 = fig.add_subplot(gs[2, 0])
        ax3.plot(np.array(self.data['time'])/60, self.data['altitude'], 'b-', linewidth=1.2)
        if any(self.data['attack_active']):
            attack_times = [self.data['time'][i]/60 for i in range(len(self.data['time'])) if self.data['attack_active'][i]]
            attack_alts = [self.data['altitude'][i] for i in range(len(self.data['time'])) if self.data['attack_active'][i]]
            ax3.scatter(attack_times, attack_alts, c='red', s=10, alpha=0.5, label='Attack Active')
        ax3.set_ylabel('Altitude (km)')
        ax3.set_xlabel('Time (min)')
        ax3.set_title('Orbital Altitude')
        ax3.grid(True, alpha=0.3)
        
        # Battery SOC
        ax4 = fig.add_subplot(gs[2, 1])
        ax4.plot(np.array(self.data['time'])/60, self.data['battery_soc'], 'orange', linewidth=1.2)
        ax4.axhline(y=20, color='r', linestyle='--', alpha=0.5, label='Critical')
        ax4.set_ylabel('Battery SOC (%)')
        ax4.set_xlabel('Time (min)')
        ax4.set_title('Battery State of Charge')
        ax4.grid(True, alpha=0.3)
        ax4.legend()
        
        # Attitude Error
        ax5 = fig.add_subplot(gs[2, 2])
        ax5.plot(np.array(self.data['time'])/60, self.data['attitude_err'], 'purple', linewidth=1.2)
        ax5.set_ylabel('Pointing Error (°)')
        ax5.set_xlabel('Time (min)')
        ax5.set_title('Attitude Error')
        ax5.grid(True, alpha=0.3)
        
        # Power Generation
        ax6 = fig.add_subplot(gs[2, 3])
        ax6.plot(np.array(self.data['time'])/60, self.data['power_gen'], 'green', linewidth=1.2)
        eclipse_periods = np.array(self.data['eclipse'])
        ax6.fill_between(np.array(self.data['time'])/60, 0, np.max(self.data['power_gen']), 
                          where=eclipse_periods, alpha=0.2, color='navy', label='Eclipse')
        ax6.set_ylabel('Solar Power (W)')
        ax6.set_xlabel('Time (min)')
        ax6.set_title('Solar Panel Generation')
        ax6.grid(True, alpha=0.3)
        ax6.legend()
        
        # Communication Link
        ax7 = fig.add_subplot(gs[3, 0])
        ax7.plot(np.array(self.data['time'])/60, self.data['range'], 'b-', linewidth=1.2, label='Range')
        ax7.set_ylabel('Range (km)', color='b')
        ax7.tick_params(axis='y', labelcolor='b')
        ax7.set_xlabel('Time (min)')
        ax7.set_title('Ground Station Link')
        ax7.grid(True, alpha=0.3)
        ax7_twin = ax7.twinx()
        link_mask = np.array(self.data['link_active'], dtype=float)
        ax7_twin.fill_between(np.array(self.data['time'])/60, 0, link_mask, alpha=0.3, color='green', label='Link Active')
        ax7_twin.set_ylabel('Link Status', color='green')
        ax7_twin.tick_params(axis='y', labelcolor='green')
        ax7_twin.set_ylim(0, 1.5)
        
        # Thermal
        ax8 = fig.add_subplot(gs[3, 1])
        ax8.plot(np.array(self.data['time'])/60, self.data['cpu_temp'], 'red', linewidth=1.2, label='CPU')
        ax8.plot(np.array(self.data['time'])/60, self.data['battery_temp'], 'orange', linewidth=1.2, label='Battery')
        ax8.axhline(y=323, color='r', linestyle='--', alpha=0.5, label='Max Temp')
        ax8.set_ylabel('Temperature (K)')
        ax8.set_xlabel('Time (min)')
        ax8.set_title('Thermal State')
        ax8.grid(True, alpha=0.3)
        ax8.legend()
        
        # Reaction Wheel Momentum
        ax9 = fig.add_subplot(gs[3, 2])
        ax9.plot(np.array(self.data['time'])/60, self.data['rw_momentum'], 'teal', linewidth=1.2)
        ax9.plot(np.array(self.data['time'])/60, self.data['rw_momentum'], 'teal', linewidth=1.2)

        ax9.set_ylabel('RW Momentum (N·m·s)')
        ax9.set_xlabel('Time (min)')
        ax9.set_title('Reaction Wheel Momentum')
        ax9.grid(True, alpha=0.3)
        ax9.legend()
        ax9.relim()
        ax9.autoscale_view()
        
        # Verified Commands & Attacks
        ax10 = fig.add_subplot(gs[3, 3])
        ax10.plot(np.array(self.data['time'])/60, self.data['verified_cmds'], 'g-', linewidth=1.2, label='Verified Cmds')
        if any(self.data['attack_active']):
            attack_mask = np.array(self.data['attack_active'], dtype=float) * max(self.data['verified_cmds'])
            ax10.fill_between(np.array(self.data['time'])/60, 0, attack_mask, alpha=0.3, 
                               color='red', label='Cyber Attack')
        ax10.set_ylabel('Verified Commands')
        ax10.set_xlabel('Time (min)')
        ax10.set_title('Command Success Rate & Attacks')
        ax10.grid(True, alpha=0.3)
        ax10.legend()
        
        plt.suptitle('Smallsat Cybersecurity Operations & Penetrations Engine Dashboard', 
                     fontsize=16, fontweight='bold', y=0.995)
        
        plt.savefig('scope_mission_dashboard.png', dpi=150, bbox_inches='tight')
        print("✅ Dashboard saved: scope_mission_dashboard.png")
        plt.show()


    
    def print_summary(self):
        """Print mission summary"""
        print("\n" + "=" * 60)
        print("📋 MISSION SUMMARY")
        print("=" * 60)
        print(f"Total Mission Duration: {self.data['time'][-1]/60:.1f} minutes")
        print(f"Orbital Altitude Change: {self.data['altitude'][-1] - self.target_altitude:+.1f} km")
        print(f"Battery Degradation: {(self.sat_config.battery_capacity*0.8 - self.power.state.battery_charge)/self.sat_config.battery_capacity*100:.1f}%")
        print(f"Total Eclipse Time: {sum(self.data['eclipse'])*self.sim_config.dt/60:.1f} minutes")
        print(f"Ground Station Passes: {sum([1 for i in range(1, len(self.data['link_active'])) if self.data['link_active'][i] and not self.data['link_active'][i-1]])}")
        print(f"Command Success Rate: {sum(self.data['verified_cmds'])/(len(self.data['verified_cmds'])*6)*100:.1f}%")
        print(f"Max Attitude Error: {max(self.data['attitude_err']):.1f}°")
        print(f"Max Temperature: {max(self.data['cpu_temp']):.1f} K")
        print(f"Cyber Attack Time: {sum(self.data['attack_active'])*self.sim_config.dt/60:.1f} minutes")
        print("=" * 60)
