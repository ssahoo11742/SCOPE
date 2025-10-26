import random
import hashlib
import os
from cryptography.hazmat.primitives.asymmetric import ed25519


class CommandSpoofer:
    """
    Handles generation and injection of spoofed commands with Ed25519 signatures
    and MD5 checksums for legacy compatibility.
    """

    def __init__(self, attack, base_commands, signer_private_key):
        # store reference to attack scenario
        self.attack = attack
        self.base_commands = base_commands

        # generate new Ed25519 keypair for every run
        self.signer_private_key = signer_private_key
        self.signer_public_key = self.signer_private_key.public_key()

        # default spoof config
        self.allowed_cmd_types = [
            'THRUST_X', 'THRUST_Y', 'THRUST_Z',
            'RW_TORQUE_X', 'RW_TORQUE_Y', 'RW_TORQUE_Z'
        ]

        # configurable spoof behavior
        self.mode = getattr(attack, 'spoof_mode', 'insert')
        self.compromised = getattr(attack, 'has_compromised_key', False)
        
        self.debug = getattr(attack, 'debug', False)

    # ------------------------------------------------------------
    def make_spoofed_cmd_dict(self, cmd_type: str, use_real_signer: bool = False) -> dict:
        """Generate a spoofed command dictionary with checksum + signature."""
        # Choose random value ranges similar to original logic
        if cmd_type.startswith("THRUST"):
            if random.random() < 0.7:
                val = random.uniform(-0.01, 0.01)
            else:
                val = random.uniform(-2000, 2000)
        elif cmd_type.startswith("RW_TORQUE"):
            val = random.uniform(-0.01, 0.01)
        else:
            val = random.uniform(-1, 1)

        cmd_body = f"{cmd_type}:{val:.6f}"
        md5_digest = hashlib.md5(cmd_body.encode()).hexdigest()[:6]
        cmd_with_md5 = f"{cmd_body}|{md5_digest}"

        # Sign using Ed25519 or create fake signature to simulate forgery
        if use_real_signer:
            sig = self.signer_private_key.sign(cmd_with_md5.encode()).hex()
        else:
            sig = os.urandom(16).hex()

        return {"command": cmd_with_md5, "auth": "ed25519", "signature": sig}

    # ------------------------------------------------------------
    def spoof(self, modified_commands: list) -> list:
        """Perform the spoofing attack on a given command list."""
        num_to_generate = int(len(self.base_commands) * self.attack.intensity)
        if self.attack.intensity > 0 and num_to_generate == 0:
            num_to_generate = 1

        if self.mode == 'insert':
            for _ in range(num_to_generate):
                spoof_type = random.choice(self.allowed_cmd_types)
                spoof_cmd = self.make_spoofed_cmd_dict(
                    spoof_type,
                    use_real_signer=self.compromised
                )
                insert_pos = random.randint(0, len(modified_commands))
                modified_commands.insert(insert_pos, spoof_cmd)

        elif self.mode == 'replace':
            replace_count = min(num_to_generate, len(modified_commands))
            replace_indices = random.sample(range(len(modified_commands)), k=replace_count)
            for idx in replace_indices:
                orig = modified_commands[idx]
                try:
                    orig_type = orig["command"].split(':', 1)[0]
                    if orig_type in self.allowed_cmd_types and random.random() < 0.8:
                        spoof_type = orig_type
                    else:
                        spoof_type = random.choice(self.allowed_cmd_types)
                except Exception:
                    spoof_type = random.choice(self.allowed_cmd_types)

                modified_commands[idx] = self.make_spoofed_cmd_dict(
                    spoof_type,
                    use_real_signer=self.compromised
                )
        else:
            # default append mode
            for _ in range(num_to_generate):
                spoof_type = random.choice(self.allowed_cmd_types)
                modified_commands.append(self.make_spoofed_cmd_dict(
                    spoof_type,
                    use_real_signer=self.compromised
                ))

        if self.debug:
            print("=== COMMAND SPOOFING DEBUG ===")
            print("Original:", self.base_commands)
            print("Modified:", modified_commands)
            print("=============================")

        return modified_commands

    # ------------------------------------------------------------

