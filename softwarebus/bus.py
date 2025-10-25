from typing import Callable, Dict, List, Tuple
import hashlib
from dataclass.sat_state import CCSDSPacket
# ============================================================================
# SOFTWARE BUS
# ============================================================================
class SoftwareBus:
    """Simplified cFS Software Bus"""
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.message_queue: List[Tuple[str, CCSDSPacket]] = []
        self.packet_counter: int = 0
        
    def subscribe(self, topic: str, callback: Callable):
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append(callback)
    
    def publish(self, topic: str, packet: CCSDSPacket):
        self.message_queue.append((topic, packet))
        if topic in self.subscribers:
            for callback in self.subscribers[topic]:
                callback(packet)
    
    def create_packet(self, apid: int, pkt_type: int, data: dict, timestamp: float) -> CCSDSPacket:
        packet = CCSDSPacket(
            apid=apid,
            packet_type=pkt_type,
            sequence_count=self.packet_counter,
            timestamp=timestamp,
            data=data
        )
        self.packet_counter += 1
        data_str = f"{apid}{pkt_type}{timestamp}{str(data)}"
        packet.checksum = hashlib.md5(data_str.encode()).hexdigest()[:8]
        return packet