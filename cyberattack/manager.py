from typing import Optional, List, Tuple
import random
import hashlib
from dataclass.cyber import CyberAttack, CyberScenario
import os
# cryptography imports
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature
from dataclass.config import DefenseSystemConfig
from .spoof import CommandSpoofer
# ============================================================================ 
# CYBER ATTACK MANAGER (Ed25519-aware)
# ============================================================================ 
class CyberAttackManager:
    def __init__(self, scenarios: List[CyberScenario], base_error_rate: float, defense_config:DefenseSystemConfig ):
        self.scenarios = scenarios
        self.defense_config = defense_config
        self.base_error_rate = base_error_rate
        # public key will be set by simulator (satellite verifies with this)
        self.public_key = None

    def set_public_key(self, public_key_bytes: bytes):
        """
        Supply the Ed25519 public key bytes (Raw) so verify_command can verify signatures.
        Call from simulator after generating the fresh keypair each run.
        """
        try:
            self.public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
        except Exception:
            self.public_key = None

    def get_active_attack(self, current_time: float) -> Optional[CyberScenario]:
        for scenario in self.scenarios:
            if scenario.start_time <= current_time < scenario.start_time + scenario.duration:
                return scenario
        return None

    def apply_attack(self, attack: CyberScenario, current_time: float, commands: List[dict],
                    telemetry_data: dict, signer_private_key: Optional[ed25519.Ed25519PrivateKey] = None
                    ) -> Tuple[List[dict], dict, float]:
        """
        commands: List of dicts like {"command": "...|md5", "auth": "ed25519", "signature": "<hex>"}
        If signer_private_key is provided and attack simulates key compromise (attack.has_compromised_key),
        the manager can use the real private key to sign spoofed commands.
        """
        if current_time < attack.start_time or current_time > attack.start_time + attack.duration:
            return commands, telemetry_data, self.base_error_rate

        modified_commands = list(commands)  # copy of dicts
        modified_telemetry = telemetry_data.copy()
        error_rate = self.base_error_rate

        # --- COMMAND SPOOFING (enhanced, produces dicts) ---
        if attack.attack_type == CyberAttack.COMMAND_SPOOFING:
            spoofer = CommandSpoofer(attack, commands, signer_private_key)
            modified_commands = spoofer.spoof(commands.copy())

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
                try:
                    if 'RW_TORQUE' in cmd.get("command", ""):
                        parts = cmd["command"].split(':')
                        if len(parts) >= 2:
                            value = float(parts[1].split('|')[0])
                            new_val = str(-value * 1.5)
                            modified_commands[i]["command"] = cmd["command"].replace(str(value), new_val)
                            # signature invalid now; if simulating key compromise you might re-sign here
                except Exception:
                    pass

        # --- ORBIT MANIPULATION (example) ---
        elif attack.attack_type == CyberAttack.ORBIT_MANIPULATION:
            for i in range(int(attack.intensity * 3)):
                malicious_cmd = f"THRUST_Z:{-0.005:.6f}"
                checksum = hashlib.md5(malicious_cmd.encode()).hexdigest()[:6]
                cmd_with_md5 = f"{malicious_cmd}|{checksum}"
                # signed as fake (no real signer) — will fail verify unless compromised
                sig = os.urandom(16).hex()
                modified_commands.append({"command": cmd_with_md5, "auth": "ed25519", "signature": sig})

        return modified_commands, modified_telemetry, error_rate

    def corrupt_message(self, cmd_dict: dict, error_rate: float, flips: int = 2) -> dict:
        """
        Operates on command dicts. Flips bits in the 'command' string field.
        Returns a new dict (copy) with possibly corrupted 'command' bytes.
        Signature field will be left as-is (so verification will fail if we change the command).
        """
        if not isinstance(cmd_dict, dict):
            return cmd_dict

        out = cmd_dict.copy()
        if random.random() < error_rate and len(out.get("command", "")) > 0:
            msg = out["command"]
            byte_array = bytearray(msg.encode('utf-8'))
            total_bits = len(byte_array) * 8
            flips = min(flips, total_bits)
            bit_indices = random.sample(range(total_bits), k=flips)
            for bit_index in bit_indices:
                byte_index = bit_index // 8
                bit_in_byte = bit_index % 8
                byte_array[byte_index] ^= (1 << bit_in_byte)
            corrupted_msg = byte_array.decode('utf-8', errors='replace')
            # put corrupted command into dict; signature remains the original => verify should fail
            out["command"] = corrupted_msg

            # fallback guarantee
            if out["command"] == cmd_dict.get("command"):
                pos = random.randint(0, len(msg) - 1)
                corrupted_msg = msg[:pos] + random.choice("XYZ123!@#") + msg[pos + 1:]
                out["command"] = corrupted_msg

        return out

    def verify_command(self, msg: dict) -> Optional[str]:
        """
        Verify Ed25519 signature on the given command dict.
        If valid, returns the command body (text before any '|').
        If invalid, returns None.

        If defense_config.has_enabled_auth is False, signature verification is skipped
        and the command body is returned (i.e. auth not enforced).
        """
        try:
            if not isinstance(msg, dict):
                return None

            cmd_text = msg.get("command", "")
            signature_hex = msg.get("signature", "")
            auth = msg.get("auth", "")

            # If defense system explicitly disables auth, accept commands without verification
            if self.defense_config is not None and not getattr(self.defense_config, "enable_key_auth", True):
                if '|' in cmd_text:
                    return cmd_text.split('|', 1)[0]
                return cmd_text

            # Normal behavior: require ed25519 + public key and verify signature
            if auth != "ed25519" or not self.public_key:
                return None
            signature_bytes = bytes.fromhex(signature_hex)
            # verify signature against the exact command string the signer signed
            self.public_key.verify(signature_bytes, cmd_text.encode('utf-8'))
            # signature valid -> return the command body (before '|') to maintain previous behavior
            if '|' in cmd_text:
                return cmd_text.split('|', 1)[0]
            return cmd_text
        except (InvalidSignature, ValueError, KeyError):
            return None
        except Exception:
            return None

