import time
from dataclasses import dataclass

# Labels match the measurement, not a stronger claim.
PROCESSING_LATENCY_LABEL = "PROCESSING LATENCY"
PROCESSING_LATENCY_HINT = "Chunk process_stream time, not end-to-end delay."
PROCESSING_RTF_LABEL = "PROCESSING RTF"
PROCESSING_RTF_HINT = "Processing time ÷ chunk duration."
INPUT_OVERFLOWS_LABEL = "INPUT OVERFLOWS"
INPUT_OVERFLOWS_HINT_LIVE = "PortAudio input overflows for this live session."
INPUT_OVERFLOWS_HINT_UNAVAILABLE = "Not measured for recorded playback."
BUFFER_FILL_LABEL = "BUFFER FILL"
BUFFER_FILL_HINT = "Not measured on this path."
TELEMETRY_UNAVAILABLE = "—"
HOLD_LIVE = "Last live session"
HOLD_DEMO = "Last recorded playback"


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

    def __init__(self) -> None:
        self.timestamp = time.time()
        self.input_level_db = -60.0
        self.output_level_db = -60.0
        self.input_peak_db = -60.0
        self.output_peak_db = -60.0
        self.processing_time_ms = 0.0
        self.realtime_factor = 0.0
        self.buffer_fill_percent = 0.0
        self.dropped_frames = 0
        self.model_name = "Unknown"
        self.sample_rate = 48000
        self.is_live = False
