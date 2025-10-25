import numpy as np
from dataclass.config import ControlConfig, SatelliteConfig
from dataclass.sat_state import OrbitalState, AttitudeState

# ============================================================================
# CONTROLLER - PRISTINE PERFECT IMPLEMENTATION
# ============================================================================
class Controller:
    def __init__(self, control_config: ControlConfig, sat_config: SatelliteConfig):
        self.config = control_config
        self.sat_config = sat_config
    
    @staticmethod
    def quaternion_multiply(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
        """Quaternion multiplication (w, x, y, z format)"""
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2
        return np.array([
            w1*w2 - x1*x2 - y1*y2 - z1*z2,
            w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2,
            w1*z2 + x1*y2 - y1*x2 + z1*w2
        ])
    
    def compute_orbit_control(self, orbital_state: OrbitalState, target_altitude: float, 
                             earth_radius: float) -> np.ndarray:
        """Orbit control with dead-band"""
        r_mag = np.linalg.norm(orbital_state.position)
        current_altitude = r_mag - earth_radius
        altitude_error = target_altitude - current_altitude
        
        # Dead-band to prevent chattering
        if abs(altitude_error) < 5.0:
            return np.zeros(3)
        
        # Proportional control
        radial_direction = orbital_state.position / r_mag
        desired_thrust = radial_direction * altitude_error * self.config.orbit_gain
        
        thrust_noise = np.random.normal(0, self.config.thrust_noise_std, 3)
        return desired_thrust + thrust_noise
    
    def compute_attitude_control(self, attitude_state: AttitudeState) -> np.ndarray:
        """
        PRISTINE PERFECT: Bulletproof quaternion-based PD control
        Uses numerically stable error extraction with multiple fallbacks
        """
        
        # Target: identity quaternion (no rotation)
        q_target = np.array([1.0, 0.0, 0.0, 0.0])
        q_current = attitude_state.quaternion
        
        # CRITICAL: Normalize current quaternion to prevent accumulated errors
        q_norm = np.linalg.norm(q_current)
        if q_norm < 1e-10:
            # Degenerate quaternion - return zero torque
            return np.zeros(3)
        q_current = q_current / q_norm
        
        # Ensure shortest path: flip if w < 0
        if q_current[0] < 0:
            q_current = -q_current
        
        # Compute quaternion error: q_error = q_target ⊗ q_current*
        q_current_conj = np.array([q_current[0], -q_current[1], -q_current[2], -q_current[3]])
        q_error = self.quaternion_multiply(q_target, q_current_conj)
        
        # BULLETPROOF: Extract error angle with multiple safety checks
        # Method 1: Standard arccos (most accurate when valid)
        w_error = q_error[0]
        
        # Clamp to valid range for arccos [-1, 1]
        w_error_clamped = np.clip(w_error, -1.0, 1.0)
        
        # Check if clamping changed the value significantly
        if abs(w_error - w_error_clamped) > 1e-6:
            # Quaternion is corrupted, renormalize
            q_error_norm = np.linalg.norm(q_error)
            if q_error_norm > 1e-10:
                q_error = q_error / q_error_norm
                w_error_clamped = np.clip(q_error[0], -1.0, 1.0)
            else:
                # Completely degenerate - return zero torque
                return np.zeros(3)
        
        error_angle = 2.0 * np.arccos(w_error_clamped)
        
        # BULLETPROOF: Extract error axis with numerical stability
        vec_error = q_error[1:4]
        vec_error_mag = np.linalg.norm(vec_error)
        
        if vec_error_mag < 1e-10:
            # Near-zero rotation - no error
            error_vector = np.zeros(3)
        else:
            # Method: For small angles use 2*vec, for large use axis-angle
            if error_angle < 0.1:  # < 5.7 degrees
                # Small angle approximation: error ≈ 2 * vector part
                error_vector = 2.0 * vec_error
            else:
                # Full axis-angle extraction
                sin_half_angle = np.sin(error_angle / 2.0)
                
                if abs(sin_half_angle) < 1e-10:
                    # At 0° or 360° - no error
                    error_vector = np.zeros(3)
                else:
                    # Extract rotation axis
                    error_axis = vec_error / vec_error_mag
                    # Angle * axis gives error vector
                    error_vector = error_angle * error_axis
        
        # PRISTINE: Smooth gain scheduling (no discontinuities)
        error_deg = error_angle * 180.0 / np.pi
        
        # Hyperbolic tangent-based smooth gain reduction
        # At 0°: gain_scale = 1.0
        # At 30°: gain_scale ≈ 0.5
        # At 90°: gain_scale ≈ 0.2
        gain_scale = 0.2 + 0.8 / (1.0 + (error_deg / 30.0) ** 2)
        
        p_gain = self.config.attitude_gain_p * gain_scale
        d_gain = self.config.attitude_gain_d * gain_scale
        
        # PD control law
        torque_proportional = p_gain * error_vector
        torque_derivative = -d_gain * attitude_state.angular_velocity
        desired_torque = torque_proportional + torque_derivative
        
        # Add small Gaussian noise for realism
        torque_noise = np.random.normal(0, self.config.torque_noise_std, 3)
        final_torque = desired_torque + torque_noise
        
        # FINAL SAFETY CHECK: Verify output is valid
        if np.any(np.isnan(final_torque)) or np.any(np.isinf(final_torque)):
            print(f"ERROR: Invalid torque computed!")
            print(f"  q_current: {q_current}")
            print(f"  q_error: {q_error}")
            print(f"  error_angle: {error_angle}")
            print(f"  error_vector: {error_vector}")
            print(f"  desired_torque: {desired_torque}")
            return np.zeros(3)
        
        return final_torque