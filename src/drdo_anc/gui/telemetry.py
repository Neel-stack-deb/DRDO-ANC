import time
from dataclasses import dataclass

@dataclass
class AudioTelemetry:
    """Small scalar representation of audio state for GUI visualization."""
    timestamp: float = 0.0
    
    input_level_db: float = -60.0
    output_level_db: float = -60.0
    
    input_peak_db: float = -60.0
    output_peak_db: float = -60.0
    
    processing_time_ms: float = 0.0
    realtime_factor: float = 0.0
    
    buffer_fill_percent: float = 0.0
    dropped_frames: int = 0
    
    model_name: str = "Unknown"
    sample_rate: int = 48000
    is_live: bool = False
    
    def __init__(self):
        self.timestamp = time.time()
