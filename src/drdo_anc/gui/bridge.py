import math
import time
import collections
import numpy as np
from PySide6.QtCore import QObject, Signal, Slot, Property, QTimer

from drdo_anc.gui.telemetry import AudioTelemetry
from drdo_anc.gui.waveform import WaveformProcessor

class GUIBridge(QObject):
    """
    Acts as the bridge between Python background threads and the QML frontend.
    """
    
    # Signals for QML to bind to
    telemetryUpdated = Signal()
    inputWaveformUpdated = Signal(list)
    outputWaveformUpdated = Signal(list)
    historyUpdated = Signal()
    
    def __init__(self, fps=60):
        super().__init__()
        self._fps = fps
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timeout)
        
        self._latest_telemetry = AudioTelemetry()
        
        self._waveform_processor = WaveformProcessor(target_points=500)
        self._latest_input_waveform = []
        self._latest_output_waveform = []
        
        # History buffers (last 100 frames)
        self._history_len = 100
        self._proc_time_hist = collections.deque([0.0]*self._history_len, maxlen=self._history_len)
        self._buffer_fill_hist = collections.deque([0.0]*self._history_len, maxlen=self._history_len)
        self._dropped_hist = collections.deque([0.0]*self._history_len, maxlen=self._history_len)
        self._rtf_hist = collections.deque([0.0]*self._history_len, maxlen=self._history_len)
        
        self._phase = 0.0
        
    def start_timer(self):
        interval = int(1000 / self._fps)
        self._timer.start(interval)
        
    def stop_timer(self):
        self._timer.stop()
        
    # --- Properties accessible from QML ---
    
    @Property(float, notify=telemetryUpdated)
    def inputLevelDb(self): return self._latest_telemetry.input_level_db
    
    @Property(float, notify=telemetryUpdated)
    def outputLevelDb(self): return self._latest_telemetry.output_level_db
    
    @Property(float, notify=telemetryUpdated)
    def inputPeakDb(self): return self._latest_telemetry.input_peak_db
    
    @Property(float, notify=telemetryUpdated)
    def outputPeakDb(self): return self._latest_telemetry.output_peak_db
    
    @Property(float, notify=telemetryUpdated)
    def processingTimeMs(self): return self._latest_telemetry.processing_time_ms
    
    @Property(float, notify=telemetryUpdated)
    def realtimeFactor(self): return self._latest_telemetry.realtime_factor
    
    @Property(float, notify=telemetryUpdated)
    def bufferFillPercent(self): return self._latest_telemetry.buffer_fill_percent
    
    @Property(int, notify=telemetryUpdated)
    def droppedFrames(self): return self._latest_telemetry.dropped_frames
    
    @Property(str, notify=telemetryUpdated)
    def modelName(self): return self._latest_telemetry.model_name
    
    @Property(int, notify=telemetryUpdated)
    def sampleRate(self): return self._latest_telemetry.sample_rate
    
    @Property(bool, notify=telemetryUpdated)
    def isLive(self): return self._latest_telemetry.is_live
    
    # History Properties
    @Property(list, notify=historyUpdated)
    def procTimeHistory(self): return list(self._proc_time_hist)
    
    @Property(list, notify=historyUpdated)
    def bufferFillHistory(self): return list(self._buffer_fill_hist)
    
    @Property(list, notify=historyUpdated)
    def droppedHistory(self): return list(self._dropped_hist)
    
    @Property(list, notify=historyUpdated)
    def rtfHistory(self): return list(self._rtf_hist)
    
    def update_telemetry(self, telemetry: AudioTelemetry):
        self._latest_telemetry = telemetry
        
    def update_waveforms(self, input_chunk: np.ndarray, output_chunk: np.ndarray):
        input_reduced, output_reduced = self._waveform_processor.process(input_chunk, output_chunk)
        self._latest_input_waveform = input_reduced.tolist()
        self._latest_output_waveform = output_reduced.tolist()

    def publish_data(self, input_chunk: np.ndarray, output_chunk: np.ndarray, proc_time_s: float, stats: dict = None):
        """Called by the background audio thread to push new data."""
        # Process waveforms
        input_reduced, output_reduced = self._waveform_processor.process(input_chunk, output_chunk)
        self._latest_input_waveform = input_reduced.tolist()
        self._latest_output_waveform = output_reduced.tolist()

        # Update telemetry object
        t = self._latest_telemetry
        t.is_live = True
        t.processing_time_ms = proc_time_s * 1000.0

        # Calculate input RMS and Peak
        if len(input_chunk) > 0:
            rms_in = float(np.sqrt(np.mean(input_chunk**2) + 1e-10))
            peak_in = float(np.max(np.abs(input_chunk)) + 1e-10)
            t.input_level_db = 20 * math.log10(rms_in)
            t.input_peak_db = 20 * math.log10(peak_in)

        # Calculate output RMS and Peak
        if len(output_chunk) > 0:
            rms_out = float(np.sqrt(np.mean(output_chunk**2) + 1e-10))
            peak_out = float(np.max(np.abs(output_chunk)) + 1e-10)
            t.output_level_db = 20 * math.log10(rms_out)
            t.output_peak_db = 20 * math.log10(peak_out)

        # Update stats
        if stats:
            t.dropped_frames = stats.get("input_overflows", 0) + stats.get("output_underflows", 0)
            
            # Simple buffer fill proxy based on chunk size processing
            chunk_duration = len(input_chunk) / max(1, t.sample_rate)
            t.realtime_factor = proc_time_s / chunk_duration if chunk_duration > 0 else 0.0

    @Slot()
    def _on_timeout(self):
        if not self._latest_telemetry.is_live:
            self._generate_fake_data()
            
        # Update history
        t = self._latest_telemetry
        self._proc_time_hist.append(t.processing_time_ms)
        self._buffer_fill_hist.append(t.buffer_fill_percent)
        self._dropped_hist.append(float(t.dropped_frames))
        self._rtf_hist.append(t.realtime_factor)
            
        self.telemetryUpdated.emit()
        self.historyUpdated.emit()
        self.inputWaveformUpdated.emit(self._latest_input_waveform)
        self.outputWaveformUpdated.emit(self._latest_output_waveform)
        
    def _generate_fake_data(self):
        self._phase += 0.15
        t = self._latest_telemetry
        t.is_live = True
        
        # Simulate speech envelope (bursts with pauses)
        envelope = max(0, math.sin(self._phase * 0.4) * math.sin(self._phase * 0.13))
        envelope = envelope ** 2  # Sharpen the bursts
        
        # Simulate Peak and RMS based on envelope
        base_vol = -50 + (envelope * 45)  # -50 to -5 dB
        t.input_level_db = base_vol
        t.input_peak_db = min(0, base_vol + 6 + np.random.uniform(0, 4))
        
        out_vol = base_vol - 2
        t.output_level_db = out_vol
        t.output_peak_db = min(0, out_vol + 4 + np.random.uniform(0, 3))
        
        # Stable telemetry numbers
        t.processing_time_ms = 4.1 + math.sin(self._phase * 0.5) * 0.3 + np.random.uniform(0, 0.1)
        t.realtime_factor = 0.45 + math.sin(self._phase * 0.3) * 0.02 + np.random.uniform(-0.01, 0.01)
        t.buffer_fill_percent = max(0, min(100, 15 + math.sin(self._phase * 1.5) * 4 + np.random.uniform(0, 2)))
        t.dropped_frames = 0 if np.random.random() > 0.02 else 1
        
        t.model_name = "DeepFilterNet3"
        t.sample_rate = 48000
        
        # Generate 500 samples
        x = np.linspace(0, 10 * np.pi, 500)
        # Clean speech: complex high-freq signal multiplied by envelope
        carrier = np.sin(x * 3.5) + 0.5 * np.sin(x * 7.2) + 0.25 * np.sin(x * 15.1)
        clean_speech = carrier * envelope * 0.8
        
        # Background noise (constant but varying slightly)
        noise_envelope = 0.15 + 0.05 * math.sin(self._phase * 0.1)
        noise = np.random.normal(0, noise_envelope, 500)
        
        noisy_speech = clean_speech + noise
        
        self._latest_input_waveform = noisy_speech.tolist()
        self._latest_output_waveform = clean_speech.tolist()
