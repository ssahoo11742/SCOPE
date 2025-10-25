from typing import Optional, List, Tuple
import random
import hashlib
from dataclass.cyber import CyberAttack, CyberScenario

# ============================================================================ 
# CYBER ATTACK MANAGER (updated)
# ============================================================================ 
class CyberAttackManager:
    def __init__(self, scenarios: List[CyberScenario], base_error_rate: float):
        self.scenarios = scenarios
        self.base_error_rate = base_error_rate

    def get_active_attack(self, current_time: float) -> Optional[CyberScenario]:
        for scenario in self.scenarios:
            if scenario.start_time <= current_time < scenario.start_time + scenario.duration:
                return scenario
        return None

    def apply_attack(self, attack: CyberScenario, current_time: float, commands: List[str],
                    telemetry_data: dict) -> Tuple[List[str], dict, float]:
        if current_time < attack.start_time or current_time > attack.start_time + attack.duration:
            return commands, telemetry_data, self.base_error_rate

        modified_commands = list(commands)  # copy
        modified_telemetry = telemetry_data.copy()
        error_rate = self.base_error_rate

        # --- COMMAND SPOOFING (enhanced) ---
        if attack.attack_type == CyberAttack.COMMAND_SPOOFING:
            # helper to create a spoofed command matching your format
            def make_spoofed_cmd(cmd_type: str) -> str:
                if cmd_type.startswith("THRUST"):
                    # 70% subtle, 30% large bogus (matches examples you posted)
                    if random.random() < 0.7:
                        val = random.uniform(-0.01, 0.01)
                    else:
                        val = random.uniform(-2000, 2000)
                elif cmd_type.startswith("RW_TORQUE"):
                    val = random.uniform(-0.01, 0.01)
                else:
                    val = random.uniform(-1, 1)
                cmd_body = f"{cmd_type}:{val:.6f}"
                checksum = hashlib.md5(cmd_body.encode()).hexdigest()[:6]
                return f"{cmd_body}|{checksum}"

            # how many spoofed commands to produce
            num_to_generate = int(len(commands) * attack.intensity)
            if attack.intensity > 0 and num_to_generate == 0:
                num_to_generate = 1  # at least 1 when intensity > 0

            # allowed types to spoof
            allowed_cmd_types = ['THRUST_X', 'THRUST_Y', 'THRUST_Z',
                                 'RW_TORQUE_X', 'RW_TORQUE_Y', 'RW_TORQUE_Z']

            # choose mode: insert (default) or replace (set attack.spoof_mode = 'replace')
            mode = getattr(attack, 'spoof_mode', 'insert')

            if mode == 'insert':
                for _ in range(num_to_generate):
                    spoof_type = random.choice(allowed_cmd_types)
                    spoof_cmd = make_spoofed_cmd(spoof_type)
                    insert_pos = random.randint(0, len(modified_commands))
                    modified_commands.insert(insert_pos, spoof_cmd)

            elif mode == 'replace':
                # replace randomly chosen commands with spoofed ones
                replace_count = min(num_to_generate, len(modified_commands))
                replace_indices = random.sample(range(len(modified_commands)), k=replace_count)
                for idx in replace_indices:
                    orig = modified_commands[idx]
                    # try to parse original type (e.g., "THRUST_X:...")
                    try:
                        orig_type = orig.split(':', 1)[0]
                        # 80% keep same type when replacing, otherwise random
                        if orig_type in allowed_cmd_types and random.random() < 0.8:
                            spoof_type = orig_type
                        else:
                            spoof_type = random.choice(allowed_cmd_types)
                    except:
                        spoof_type = random.choice(allowed_cmd_types)
                    modified_commands[idx] = make_spoofed_cmd(spoof_type)

            else:
                # fallback: append
                for _ in range(num_to_generate):
                    spoof_type = random.choice(allowed_cmd_types)
                    modified_commands.append(make_spoofed_cmd(spoof_type))

            # optional debug prints
            if getattr(attack, 'debug', False):
                print("=== COMMAND SPOOFING DEBUG ===")
                print("Original:", commands)
                print("Modified:", modified_commands)
                print("=============================")

        # --- TELEMETRY FALSIFICATION ---
        elif attack.attack_type == CyberAttack.TELEMETRY_FALSIFICATION:
            if 'battery_soc' in modified_telemetry:
                modified_telemetry['battery_soc'] *= (1 + attack.intensity * 0.5)
            if 'altitude' in modified_telemetry:
                modified_telemetry['altitude'] *= (1 + attack.intensity * 0.1)

        # --- DENIAL OF SERVICE (drops / increases error) ---
        elif attack.attack_type == CyberAttack.DENIAL_OF_SERVICE:
            error_rate = self.base_error_rate + attack.intensity * 0.7
            num_to_drop = int(len(modified_commands) * attack.intensity)
            modified_commands = modified_commands[num_to_drop:]

        # --- BATTERY DEPLETION ---
        elif attack.attack_type == CyberAttack.BATTERY_DEPLETION:
            modified_telemetry['power_consumption'] = modified_telemetry.get('power_consumption', 50) * (
                        1 + attack.intensity * 2)

        # --- MALICIOUS DETUMBLE (modify RW_TORQUE commands) ---
        elif attack.attack_type == CyberAttack.MALICIOUS_DETUMBLE:
            for i, cmd in enumerate(modified_commands):
                if 'RW_TORQUE' in cmd:
                    parts = cmd.split(':')
                    if len(parts) >= 2:
                        try:
                            value = float(parts[1].split('|')[0])
                            modified_commands[i] = cmd.replace(str(value), str(-value * 1.5))
                        except:
                            pass

        # --- ORBIT MANIPULATION (example) ---
        elif attack.attack_type == CyberAttack.ORBIT_MANIPULATION:
            for i in range(int(attack.intensity * 3)):
                malicious_cmd = f"THRUST_Z:{-0.005:.6f}"
                checksum = hashlib.md5(malicious_cmd.encode()).hexdigest()[:6]
                modified_commands.append(f"{malicious_cmd}|{checksum}")

        return modified_commands, modified_telemetry, error_rate

    @staticmethod
    def corrupt_message(msg: str, error_rate: float, flips: int = 2) -> str:
        """
        Flip `flips` distinct random bits in the UTF-8 byte representation of msg
        with probability `error_rate`. If the flips don't change the visible string,
        perform a single-character fallback corruption to guarantee a visible change.
        """
        if random.random() < error_rate and len(msg) > 0:
            byte_array = bytearray(msg.encode('utf-8'))
            total_bits = len(byte_array) * 8
            flips = min(flips, total_bits)

            # choose unique bit indices
            bit_indices = random.sample(range(total_bits), k=flips)
            for bit_index in bit_indices:
                byte_index = bit_index // 8
                bit_in_byte = bit_index % 8
                byte_array[byte_index] ^= (1 << bit_in_byte)

            corrupted_msg = byte_array.decode('utf-8', errors='replace')

            # fallback: guarantee visible corruption if nothing changed
            if corrupted_msg == msg:
                pos = random.randint(0, len(msg) - 1)
                corrupted_msg = msg[:pos] + random.choice("XYZ123!@#") + msg[pos + 1:]

            return corrupted_msg

        return msg

    @staticmethod
    def verify_command(msg: str) -> Optional[str]:
        try:
            cmd, checksum = msg.split("|")
            valid = hashlib.md5(cmd.encode()).hexdigest()[:6]
            return cmd if valid == checksum else None
        except:
            return None
