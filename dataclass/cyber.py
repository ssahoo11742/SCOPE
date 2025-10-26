from dataclasses import dataclass
from enum import Enum
# ============================================================================
# CYBER ATTACK
# ============================================================================
class CyberAttack(Enum):
    NONE = 0
    COMMAND_SPOOFING = 1
    TELEMETRY_FALSIFICATION = 2
    DENIAL_OF_SERVICE = 3
    BATTERY_DEPLETION = 4
    MALICIOUS_DETUMBLE = 5
    ORBIT_MANIPULATION = 6

@dataclass
class CyberScenario:
    attack_type: CyberAttack
    start_time: float
    duration: float
    intensity: float  # 0.0 to 1.0
    debug: bool
    spoof_mode: str
    has_compromised_key: bool = False