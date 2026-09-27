import collections
import math
import threading
from dataclasses import dataclass, field

import numpy as np
from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from drdo_anc.gui.mode_presentation import (
    activity_caption,
    audio_selectors_enabled,
    mode_banner,
    mode_description,
    stop_live_enabled,
    visible_controls,
)
from drdo_anc.gui.telemetry import (
  BUFFER_FILL_HINT,
  BUFFER_FILL_LABEL,
  INPUT_OVERFLOWS_HINT_LIVE,
  INPUT_OVERFLOWS_HINT_UNAVAILABLE,
  INPUT_OVERFLOWS_LABEL,
  PROCESSING_LATENCY_HINT,
  PROCESSING_LATENCY_LABEL,
  PROCESSING_RTF_HINT,
  PROCESSING_RTF_LABEL,
  TELEMETRY_UNAVAILABLE,
  AudioTelemetry,
)
from drdo_anc.gui.waveform import WaveformProcessor


@dataclass
class _TelemetrySnapshot:
  """Latest-value handoff from the audio thread to the GUI timer."""

  input_chunk: np.ndarray | None = None
  output_chunk: np.ndarray | None = None
  processing_time_s: float = 0.0
  stats: dict[str, float | int] = field(default_factory=dict)
  has_update: bool = False
  source_mode: str = ""
  session_token: int = -1


class GUIBridge(QObject):
  """
  Bridge between background audio threads and the QML frontend.

  The audio thread only stores a small snapshot. Waveform reduction and
  level calculations run on the GUI timer thread.
  """

  telemetryUpdated = Signal()
  inputWaveformUpdated = Signal(list)
  outputWaveformUpdated = Signal(list)
  historyUpdated = Signal()
  errorChanged = Signal()
  demoStateChanged = Signal()
  liveStateChanged = Signal()
  benchmarkStateChanged = Signal()
  devicesChanged = Signal()
  preflightStateChanged = Signal()
  modePresentationChanged = Signal()

  def __init__(self, fps: int = 30) -> None:
    super().__init__()
    self._fps = fps
    self._timer = QTimer(self)
    self._timer.timeout.connect(self._on_timeout)

    self._latest_telemetry = AudioTelemetry()
    self._error_message = ""

    self._waveform_processor = WaveformProcessor(target_points=500)
    self._latest_input_waveform: list[float] = []
    self._latest_output_waveform: list[float] = []

    self._history_len = 100
    self._proc_time_hist: collections.deque[float] = collections.deque(
      maxlen=self._history_len,
    )
    self._buffer_fill_hist: collections.deque[float] = collections.deque(
      maxlen=self._history_len,
    )
    self._dropped_hist: collections.deque[float] = collections.deque(
      maxlen=self._history_len,
    )
    self._rtf_hist: collections.deque[float] = collections.deque(
      maxlen=self._history_len,
    )
    self._telemetry_token = 0
    self._telemetry_session_open = False
    self._telemetry_hold_note = ""
    self._telemetry_note = ""
    self._processing_measured = False
    self._rtf_measured = False
    self._overflow_measured = False
    self._overflow_count = 0

    self._phase = 0.0
    self._telemetry_lock = threading.Lock()
    self._pending_snapshot = _TelemetrySnapshot()
    self._session = None
    self._use_fake_visuals = False

    self._operation_mode = "demo"
    self._playback_state = "stopped"
    self._demo_scenario = "Speech Only"
    self._selected_scenario_index = 0
    self._scenario_labels: list[str] = []
    self._ab_mode = "raw"
    self._pipeline_stage = "input"
    self._audio_status = "Ready"
    self._development_cases = -1
    self._evaluations = -1
    self._demo_clean_file = ""
    self._demo_noisy_file = ""
    self._demo_enhanced_ref_file = ""
    self._demo_enhanced_playback = "Live DF3"
    self._demo_input_label = "NOISY INPUT"
    self._demo_output_label = "LIVE DF3 ENHANCED"
    self._demo_metrics_available = False
    self._demo_noisy_snr = 0.0
    self._demo_enhanced_ref_snr = 0.0
    self._demo_noisy_si_sdr = 0.0
    self._demo_enhanced_ref_si_sdr = 0.0
    self._demo_noisy_stoi = 0.0
    self._demo_enhanced_ref_stoi = 0.0
    self._demo_noisy_pesq = 0.0
    self._demo_enhanced_ref_pesq = 0.0
    self._demo_status = "IDLE"
    self._demo_source_file = ""
    self._demo_duration_s = 0.0
    self._demo_model_name = ""
    self._missing_demo_categories: list[str] = []
    self._input_device_labels: list[str] = []
    self._output_device_labels: list[str] = []
    self._model_labels: list[str] = []
    self._selected_input_device_index = -1
    self._selected_output_device_index = -1
    self._selected_model_index = 0
    self._live_can_start = False
    self._live_block_reason = ""
    self._devices_locked = False
    self._show_all_devices = False
    self._live_status = "IDLE"
    self._live_input_summary = ""
    self._live_output_summary = ""
    self._live_input_overflows = 0
    self._benchmark_loaded = False
    self._benchmark_unavailable_message = ""
    self._benchmark_partial_warning = ""
    self._benchmark_pretrained_model = "DeepFilterNet3"
    self._benchmark_finetuned_model = "DeepFilterNet3-Finetuned"
    self._dev_benchmark: dict = {"available": False}
    self._rd_benchmark: dict = {"available": False}
    self._preflight_status = "NOT_CHECKED"
    self._preflight_summary = ""
    self._preflight_check_lines: list[str] = []
    self._live_fallback_offered = False
    self._live_fallback_message = ""
    self._live_fallback_kind = ""

  def start_timer(self) -> None:
    interval = int(1000 / self._fps)
    self._timer.start(interval)

  def stop_timer(self) -> None:
    self._timer.stop()

  @Property(float, notify=telemetryUpdated)
  def inputLevelDb(self) -> float:
    return self._latest_telemetry.input_level_db

  @Property(float, notify=telemetryUpdated)
  def outputLevelDb(self) -> float:
    return self._latest_telemetry.output_level_db

  @Property(float, notify=telemetryUpdated)
  def inputPeakDb(self) -> float:
    return self._latest_telemetry.input_peak_db

  @Property(float, notify=telemetryUpdated)
  def outputPeakDb(self) -> float:
    return self._latest_telemetry.output_peak_db

  @Property(float, notify=telemetryUpdated)
  def processingTimeMs(self) -> float:
    return self._latest_telemetry.processing_time_ms

  @Property(float, notify=telemetryUpdated)
  def realtimeFactor(self) -> float:
    return self._latest_telemetry.realtime_factor

  @Property(float, notify=telemetryUpdated)
  def bufferFillPercent(self) -> float:
    return self._latest_telemetry.buffer_fill_percent

  @Property(int, notify=telemetryUpdated)
  def droppedFrames(self) -> int:
    return self._overflow_count if self._overflow_measured else 0

  @Property(int, constant=True)
  def guiFps(self) -> int:
    return self._fps

  @Property(bool, notify=telemetryUpdated)
  def processingMeasured(self) -> bool:
    return self._processing_measured

  @Property(bool, notify=telemetryUpdated)
  def rtfMeasured(self) -> bool:
    return self._rtf_measured

  @Property(bool, notify=telemetryUpdated)
  def overflowMeasured(self) -> bool:
    return self._overflow_measured

  @Property(bool, notify=telemetryUpdated)
  def bufferMeasured(self) -> bool:
    return False

  @Property(str, notify=telemetryUpdated)
  def processingValueText(self) -> str:
    if not self._processing_measured:
      return TELEMETRY_UNAVAILABLE
    return f"{self._latest_telemetry.processing_time_ms:.2f}"

  @Property(str, notify=telemetryUpdated)
  def rtfValueText(self) -> str:
    if not self._rtf_measured:
      return TELEMETRY_UNAVAILABLE
    return f"{self._latest_telemetry.realtime_factor:.2f}"

  @Property(str, notify=telemetryUpdated)
  def overflowValueText(self) -> str:
    if not self._overflow_measured:
      return TELEMETRY_UNAVAILABLE
    return str(self._overflow_count)

  @Property(str, notify=telemetryUpdated)
  def bufferValueText(self) -> str:
    return TELEMETRY_UNAVAILABLE

  @Property(str, constant=True)
  def processingLatencyLabel(self) -> str:
    return PROCESSING_LATENCY_LABEL

  @Property(str, constant=True)
  def processingLatencyHint(self) -> str:
    return PROCESSING_LATENCY_HINT

  @Property(str, constant=True)
  def rtfLabel(self) -> str:
    return PROCESSING_RTF_LABEL

  @Property(str, constant=True)
  def rtfHint(self) -> str:
    return PROCESSING_RTF_HINT

  @Property(str, constant=True)
  def overflowLabel(self) -> str:
    return INPUT_OVERFLOWS_LABEL

  @Property(str, notify=telemetryUpdated)
  def overflowHint(self) -> str:
    if self._operation_mode == "live":
      return INPUT_OVERFLOWS_HINT_LIVE
    return INPUT_OVERFLOWS_HINT_UNAVAILABLE

  @Property(str, constant=True)
  def bufferFillLabel(self) -> str:
    return BUFFER_FILL_LABEL

  @Property(str, constant=True)
  def bufferFillHint(self) -> str:
    return BUFFER_FILL_HINT

  @Property(str, notify=telemetryUpdated)
  def telemetryNote(self) -> str:
    return self._telemetry_note

  @Property(str, notify=telemetryUpdated)
  def modelName(self) -> str:
    return self._latest_telemetry.model_name

  @Property(int, notify=telemetryUpdated)
  def sampleRate(self) -> int:
    return self._latest_telemetry.sample_rate

  @Property(bool, notify=liveStateChanged)
  def isLive(self) -> bool:
    return self._live_status == "LIVE"

  @Property(str, notify=liveStateChanged)
  def liveStatus(self) -> str:
    return self._live_status

  @Property(str, notify=liveStateChanged)
  def liveInputSummary(self) -> str:
    return self._live_input_summary

  @Property(str, notify=liveStateChanged)
  def liveOutputSummary(self) -> str:
    return self._live_output_summary

  @Property(int, notify=liveStateChanged)
  def liveInputOverflows(self) -> int:
    return self._live_input_overflows

  @Property(str, notify=errorChanged)
  def errorMessage(self) -> str:
    return self._error_message

  @Property(str, notify=demoStateChanged)
  def operationMode(self) -> str:
    return self._operation_mode

  @Property(str, notify=demoStateChanged)
  def playbackState(self) -> str:
    return self._playback_state

  @Property(str, notify=demoStateChanged)
  def demoScenario(self) -> str:
    return self._demo_scenario

  @Property(int, notify=demoStateChanged)
  def selectedScenarioIndex(self) -> int:
    return self._selected_scenario_index

  @Property(list, notify=demoStateChanged)
  def scenarioLabels(self) -> list[str]:
    return list(self._scenario_labels)

  @Property(str, notify=demoStateChanged)
  def abMode(self) -> str:
    return self._ab_mode

  @Property(str, notify=demoStateChanged)
  def pipelineStage(self) -> str:
    return self._pipeline_stage

  @Property(str, notify=demoStateChanged)
  def audioStatus(self) -> str:
    return self._audio_status

  @Property(int, notify=demoStateChanged)
  def developmentCases(self) -> int:
    return self._development_cases

  @Property(int, notify=demoStateChanged)
  def evaluations(self) -> int:
    return self._evaluations

  @Property(bool, notify=demoStateChanged)
  def showBenchmarkSummary(self) -> bool:
    return self._development_cases > 0 and self._evaluations > 0

  @Property(str, notify=demoStateChanged)
  def demoCleanFile(self) -> str:
    return self._demo_clean_file

  @Property(str, notify=demoStateChanged)
  def demoNoisyFile(self) -> str:
    return self._demo_noisy_file

  @Property(str, notify=demoStateChanged)
  def demoEnhancedRefFile(self) -> str:
    return self._demo_enhanced_ref_file

  @Property(str, notify=demoStateChanged)
  def demoEnhancedPlayback(self) -> str:
    return self._demo_enhanced_playback

  @Property(str, notify=demoStateChanged)
  def demoInputLabel(self) -> str:
    return self._demo_input_label

  @Property(str, notify=demoStateChanged)
  def demoOutputLabel(self) -> str:
    return self._demo_output_label

  @Property(bool, notify=demoStateChanged)
  def showDemoMetrics(self) -> bool:
    return self._demo_metrics_available

  @Property(float, notify=demoStateChanged)
  def demoNoisySnr(self) -> float:
    return self._demo_noisy_snr

  @Property(float, notify=demoStateChanged)
  def demoEnhancedRefSnr(self) -> float:
    return self._demo_enhanced_ref_snr

  @Property(float, notify=demoStateChanged)
  def demoNoisySiSdr(self) -> float:
    return self._demo_noisy_si_sdr

  @Property(float, notify=demoStateChanged)
  def demoEnhancedRefSiSdr(self) -> float:
    return self._demo_enhanced_ref_si_sdr

  @Property(float, notify=demoStateChanged)
  def demoNoisyStoi(self) -> float:
    return self._demo_noisy_stoi

  @Property(float, notify=demoStateChanged)
  def demoEnhancedRefStoi(self) -> float:
    return self._demo_enhanced_ref_stoi

  @Property(float, notify=demoStateChanged)
  def demoNoisyPesq(self) -> float:
    return self._demo_noisy_pesq

  @Property(float, notify=demoStateChanged)
  def demoEnhancedRefPesq(self) -> float:
    return self._demo_enhanced_ref_pesq

  @Property(str, notify=demoStateChanged)
  def demoStatus(self) -> str:
    return self._demo_status

  @Property(str, notify=demoStateChanged)
  def demoSourceFile(self) -> str:
    return self._demo_source_file

  @Property(float, notify=demoStateChanged)
  def demoDurationSeconds(self) -> float:
    return self._demo_duration_s

  @Property(str, notify=demoStateChanged)
  def demoModelName(self) -> str:
    return self._demo_model_name

  @Property(list, notify=demoStateChanged)
  def missingDemoCategories(self) -> list[str]:
    return list(self._missing_demo_categories)

  @Property(bool, notify=demoStateChanged)
  def isDemoMode(self) -> bool:
    return self._operation_mode == "demo"

  @Property(str, notify=demoStateChanged)
  def demoSourceLabel(self) -> str:
    if self._operation_mode == "benchmark":
      return "BENCHMARK"
    if self._operation_mode == "live":
      return "LIVE MICROPHONE"
    return "RECORDED DEMO"

  @Property(str, notify=modePresentationChanged)
  def modeBanner(self) -> str:
    return mode_banner(self._operation_mode, self._live_status)

  @Property(str, notify=modePresentationChanged)
  def modeDescription(self) -> str:
    return mode_description(self._operation_mode)

  @Property(str, notify=modePresentationChanged)
  def activityCaption(self) -> str:
    return activity_caption(
      self._operation_mode,
      demo_status=self._demo_status,
      demo_scenario=self._demo_scenario,
      ab_mode=self._ab_mode,
      duration_s=self._demo_duration_s,
      live_status=self._live_status,
      overflows=self._live_input_overflows,
      overflows_measured=self._overflow_measured,
    )

  @Property(bool, notify=modePresentationChanged)
  def showAudioSelectors(self) -> bool:
    return "model" in self._visible_controls()

  @Property(bool, notify=modePresentationChanged)
  def audioSelectorsEnabled(self) -> bool:
    return audio_selectors_enabled(
      self._operation_mode,
      self._live_status,
      devices_locked=self._devices_locked,
    )

  @Property(bool, notify=modePresentationChanged)
  def showDemoScenario(self) -> bool:
    return "scenario" in self._visible_controls()

  @Property(bool, notify=modePresentationChanged)
  def showDemoSafety(self) -> bool:
    return "demo_preflight" in self._visible_controls()

  @Property(bool, notify=modePresentationChanged)
  def showDemoTransport(self) -> bool:
    return "play" in self._visible_controls()

  @Property(bool, notify=modePresentationChanged)
  def showDemoAb(self) -> bool:
    return "ab_raw" in self._visible_controls()

  @Property(bool, notify=modePresentationChanged)
  def showLiveAb(self) -> bool:
    return False

  @Property(bool, notify=modePresentationChanged)
  def showLiveTransport(self) -> bool:
    return self._operation_mode == "live"

  @Property(bool, notify=modePresentationChanged)
  def showStartLive(self) -> bool:
    return "start_live" in self._visible_controls()

  @Property(bool, notify=modePresentationChanged)
  def showStopLive(self) -> bool:
    return "stop_live" in self._visible_controls()

  @Property(bool, notify=modePresentationChanged)
  def showLiveStarting(self) -> bool:
    return "live_starting" in self._visible_controls()

  @Property(bool, notify=modePresentationChanged)
  def showRecoverLive(self) -> bool:
    return "recover_live" in self._visible_controls()

  @Property(bool, notify=modePresentationChanged)
  def showLiveFallback(self) -> bool:
    return "live_fallback" in self._visible_controls()

  @Property(bool, notify=modePresentationChanged)
  def startLiveEnabled(self) -> bool:
    return "start_live" in self._visible_controls()

  @Property(bool, notify=modePresentationChanged)
  def stopLiveEnabled(self) -> bool:
    return stop_live_enabled(self._operation_mode, self._live_status)

  def _visible_controls(self) -> frozenset[str]:
    return visible_controls(
      self._operation_mode,
      self._live_status,
      live_fallback_offered=self._live_fallback_offered,
    )

  def _emit_mode_presentation(self) -> None:
    self.modePresentationChanged.emit()

  @Property(str, notify=preflightStateChanged)
  def preflightStatus(self) -> str:
    return self._preflight_status

  @Property(str, notify=preflightStateChanged)
  def preflightSummary(self) -> str:
    return self._preflight_summary

  @Property(list, notify=preflightStateChanged)
  def preflightCheckLines(self) -> list[str]:
    return list(self._preflight_check_lines)

  @Property(bool, notify=preflightStateChanged)
  def preflightHasRun(self) -> bool:
    return self._preflight_status != "NOT_CHECKED"

  @Property(bool, notify=liveStateChanged)
  def liveFallbackOffered(self) -> bool:
    return self._live_fallback_offered

  @Property(str, notify=liveStateChanged)
  def liveFallbackMessage(self) -> str:
    return self._live_fallback_message

  @Property(bool, notify=benchmarkStateChanged)
  def isBenchmarkMode(self) -> bool:
    return self._operation_mode == "benchmark"

  @Property(bool, notify=benchmarkStateChanged)
  def benchmarkLoaded(self) -> bool:
    return self._benchmark_loaded

  @Property(str, notify=benchmarkStateChanged)
  def benchmarkUnavailableMessage(self) -> str:
    return self._benchmark_unavailable_message

  @Property(str, notify=benchmarkStateChanged)
  def benchmarkPartialWarning(self) -> str:
    return self._benchmark_partial_warning

  @Property(str, notify=benchmarkStateChanged)
  def benchmarkPretrainedModel(self) -> str:
    return self._benchmark_pretrained_model

  @Property(str, notify=benchmarkStateChanged)
  def benchmarkFinetunedModel(self) -> str:
    return self._benchmark_finetuned_model

  @Property(bool, notify=benchmarkStateChanged)
  def devBenchmarkAvailable(self) -> bool:
    return bool(self._dev_benchmark.get("available"))

  @Property(str, notify=benchmarkStateChanged)
  def devBenchmarkTitle(self) -> str:
    return str(self._dev_benchmark.get("title", ""))

  @Property(str, notify=benchmarkStateChanged)
  def devBenchmarkContext(self) -> str:
    return str(self._dev_benchmark.get("context", ""))

  @Property(str, notify=benchmarkStateChanged)
  def devRulesVersion(self) -> str:
    return str(self._dev_benchmark.get("rules_version", ""))

  @Property(str, notify=benchmarkStateChanged)
  def devEvaluationModes(self) -> str:
    return str(self._dev_benchmark.get("evaluation_modes", ""))

  @Property(int, notify=benchmarkStateChanged)
  def devPairedEvaluations(self) -> int:
    return int(self._dev_benchmark.get("paired_evaluations", 0))

  @Property(float, notify=benchmarkStateChanged)
  def devPretrainedSiSdr(self) -> float:
    return float(self._dev_benchmark.get("pretrained_si_sdr", 0.0))

  @Property(float, notify=benchmarkStateChanged)
  def devFinetunedSiSdr(self) -> float:
    return float(self._dev_benchmark.get("finetuned_si_sdr", 0.0))

  @Property(float, notify=benchmarkStateChanged)
  def devPretrainedStoi(self) -> float:
    return float(self._dev_benchmark.get("pretrained_stoi", 0.0))

  @Property(float, notify=benchmarkStateChanged)
  def devFinetunedStoi(self) -> float:
    return float(self._dev_benchmark.get("finetuned_stoi", 0.0))

  @Property(float, notify=benchmarkStateChanged)
  def devPretrainedPesq(self) -> float:
    return float(self._dev_benchmark.get("pretrained_pesq", 0.0))

  @Property(float, notify=benchmarkStateChanged)
  def devFinetunedPesq(self) -> float:
    return float(self._dev_benchmark.get("finetuned_pesq", 0.0))

  @Property(float, notify=benchmarkStateChanged)
  def devPretrainedSnr(self) -> float:
    return float(self._dev_benchmark.get("pretrained_snr", 0.0))

  @Property(float, notify=benchmarkStateChanged)
  def devFinetunedSnr(self) -> float:
    return float(self._dev_benchmark.get("finetuned_snr", 0.0))

  @Property(float, notify=benchmarkStateChanged)
  def devSiSdrImprovement(self) -> float:
    return float(self._dev_benchmark.get("si_sdr_improvement", 0.0))

  @Property(int, notify=benchmarkStateChanged)
  def devSiSdrImproved(self) -> int:
    return int(self._dev_benchmark.get("si_sdr_improved", 0))

  @Property(int, notify=benchmarkStateChanged)
  def devSiSdrDegraded(self) -> int:
    return int(self._dev_benchmark.get("si_sdr_degraded", 0))

  @Property(str, notify=benchmarkStateChanged)
  def devPretrainedSource(self) -> str:
    return str(self._dev_benchmark.get("pretrained_source", ""))

  @Property(str, notify=benchmarkStateChanged)
  def devFinetunedSource(self) -> str:
    return str(self._dev_benchmark.get("finetuned_source", ""))

  @Property(bool, notify=benchmarkStateChanged)
  def rdBenchmarkAvailable(self) -> bool:
    return bool(self._rd_benchmark.get("available"))

  @Property(str, notify=benchmarkStateChanged)
  def rdBenchmarkTitle(self) -> str:
    return str(self._rd_benchmark.get("title", ""))

  @Property(str, notify=benchmarkStateChanged)
  def rdHoldoutNote(self) -> str:
    return str(self._rd_benchmark.get("holdout_note", ""))

  @Property(str, notify=benchmarkStateChanged)
  def rdRulesVersion(self) -> str:
    return str(self._rd_benchmark.get("rules_version", ""))

  @Property(int, notify=benchmarkStateChanged)
  def rdPairedEvaluations(self) -> int:
    return int(self._rd_benchmark.get("paired_evaluations", 0))

  @Property(int, notify=benchmarkStateChanged)
  def rdSuccessfulEvaluations(self) -> int:
    return int(self._rd_benchmark.get("successful_evaluations", 0))

  @Property(float, notify=benchmarkStateChanged)
  def rdPretrainedSiSdr(self) -> float:
    return float(self._rd_benchmark.get("pretrained_si_sdr", 0.0))

  @Property(float, notify=benchmarkStateChanged)
  def rdFinetunedSiSdr(self) -> float:
    return float(self._rd_benchmark.get("finetuned_si_sdr", 0.0))

  @Property(float, notify=benchmarkStateChanged)
  def rdPretrainedStoi(self) -> float:
    return float(self._rd_benchmark.get("pretrained_stoi", 0.0))

  @Property(float, notify=benchmarkStateChanged)
  def rdFinetunedStoi(self) -> float:
    return float(self._rd_benchmark.get("finetuned_stoi", 0.0))

  @Property(float, notify=benchmarkStateChanged)
  def rdPretrainedPesq(self) -> float:
    return float(self._rd_benchmark.get("pretrained_pesq", 0.0))

  @Property(float, notify=benchmarkStateChanged)
  def rdFinetunedPesq(self) -> float:
    return float(self._rd_benchmark.get("finetuned_pesq", 0.0))

  @Property(float, notify=benchmarkStateChanged)
  def rdPretrainedSnr(self) -> float:
    return float(self._rd_benchmark.get("pretrained_snr", 0.0))

  @Property(float, notify=benchmarkStateChanged)
  def rdFinetunedSnr(self) -> float:
    return float(self._rd_benchmark.get("finetuned_snr", 0.0))

  @Property(float, notify=benchmarkStateChanged)
  def rdSiSdrImprovement(self) -> float:
    return float(self._rd_benchmark.get("si_sdr_improvement", 0.0))

  @Property(int, notify=benchmarkStateChanged)
  def rdSiSdrImproved(self) -> int:
    return int(self._rd_benchmark.get("si_sdr_improved", 0))

  @Property(int, notify=benchmarkStateChanged)
  def rdSiSdrDegraded(self) -> int:
    return int(self._rd_benchmark.get("si_sdr_degraded", 0))

  @Property(list, notify=devicesChanged)
  def inputDeviceLabels(self) -> list[str]:
    return list(self._input_device_labels)

  @Property(list, notify=devicesChanged)
  def outputDeviceLabels(self) -> list[str]:
    return list(self._output_device_labels)

  @Property(list, notify=devicesChanged)
  def modelLabels(self) -> list[str]:
    return list(self._model_labels)

  @Property(int, notify=devicesChanged)
  def selectedInputDeviceIndex(self) -> int:
    return self._selected_input_device_index

  @Property(int, notify=devicesChanged)
  def selectedOutputDeviceIndex(self) -> int:
    return self._selected_output_device_index

  @Property(int, notify=devicesChanged)
  def selectedModelIndex(self) -> int:
    return self._selected_model_index

  @Property(bool, notify=devicesChanged)
  def liveCanStart(self) -> bool:
    return self._live_can_start

  @Property(str, notify=devicesChanged)
  def liveBlockReason(self) -> str:
    return self._live_block_reason

  @Property(bool, notify=devicesChanged)
  def devicesLocked(self) -> bool:
    return self._devices_locked

  @Property(bool, notify=devicesChanged)
  def showAllDevices(self) -> bool:
    return self._show_all_devices

  def set_device_choices(
    self,
    *,
    input_labels: list[str],
    output_labels: list[str],
    model_labels: list[str],
    selected_input_index: int,
    selected_output_index: int,
    selected_model_index: int,
    live_can_start: bool,
    live_block_reason: str,
    show_all_devices: bool = False,
  ) -> None:
    self._input_device_labels = list(input_labels)
    self._output_device_labels = list(output_labels)
    self._model_labels = list(model_labels)
    self._selected_input_device_index = selected_input_index
    self._selected_output_device_index = selected_output_index
    self._selected_model_index = selected_model_index
    self._live_can_start = live_can_start
    self._live_block_reason = live_block_reason
    self._show_all_devices = show_all_devices
    self.devicesChanged.emit()
    self._emit_mode_presentation()

  def set_devices_locked(self, locked: bool) -> None:
    if self._devices_locked == locked:
      return
    self._devices_locked = locked
    self.devicesChanged.emit()
    self._emit_mode_presentation()

  def set_demo_assets(
    self,
    *,
    clean_file: str,
    noisy_file: str,
    enhanced_ref_file: str,
    enhanced_playback: str,
  ) -> None:
    self._demo_clean_file = clean_file
    self._demo_noisy_file = noisy_file
    self._demo_enhanced_ref_file = enhanced_ref_file
    self._demo_enhanced_playback = enhanced_playback
    self._demo_input_label = "NOISY INPUT"
    self._demo_output_label = "ENHANCED OUTPUT"
    self.demoStateChanged.emit()

  def set_demo_status(self, status: str) -> None:
    if self._demo_status == status:
      return
    self._demo_status = status
    self.demoStateChanged.emit()
    self._emit_mode_presentation()

  def set_demo_scenario_details(
    self,
    *,
    label: str,
    source_file: str,
    sample_rate: int,
    model_name: str,
    duration_s: float,
  ) -> None:
    self._demo_scenario = label
    self._demo_source_file = source_file
    self._demo_duration_s = float(duration_s)
    self._demo_model_name = model_name
    self._latest_telemetry.sample_rate = int(sample_rate)
    self.demoStateChanged.emit()
    self.telemetryUpdated.emit()
    self._emit_mode_presentation()

  def set_missing_demo_categories(self, messages: list[str]) -> None:
    self._missing_demo_categories = list(messages)
    self.demoStateChanged.emit()

  def set_live_status(self, status: str) -> None:
    if self._live_status == status:
      return
    self._live_status = status
    self.liveStateChanged.emit()
    self.telemetryUpdated.emit()
    self._emit_mode_presentation()

  def set_live_device_summaries(
    self,
    *,
    input_summary: str,
    output_summary: str,
  ) -> None:
    self._live_input_summary = input_summary
    self._live_output_summary = output_summary
    self.liveStateChanged.emit()

  def set_live_input_overflows(self, count: int) -> None:
    if self._live_input_overflows == count:
      return
    self._live_input_overflows = int(count)
    self.liveStateChanged.emit()
    self._emit_mode_presentation()

  def set_preflight_report(
    self,
    *,
    status: str,
    summary: str,
    check_lines: list[str],
  ) -> None:
    self._preflight_status = status
    self._preflight_summary = summary
    self._preflight_check_lines = list(check_lines)
    self.preflightStateChanged.emit()

  def set_preflight_checking(self) -> None:
    self._preflight_status = "CHECKING"
    self._preflight_summary = ""
    self._preflight_check_lines = []
    self.preflightStateChanged.emit()

  def offer_live_fallback(self, message: str, *, kind: str = "live") -> None:
    self._live_fallback_offered = True
    self._live_fallback_message = message
    self._live_fallback_kind = kind
    self.set_error(message)
    self.liveStateChanged.emit()
    self._emit_mode_presentation()

  def clear_live_fallback(self) -> None:
    if not self._live_fallback_offered and not self._live_fallback_message:
      return
    self._live_fallback_offered = False
    self._live_fallback_message = ""
    self._live_fallback_kind = ""
    self.liveStateChanged.emit()
    self._emit_mode_presentation()

  def clear_demo_reference_metrics(self) -> None:
    self._demo_metrics_available = False
    self.demoStateChanged.emit()

  def set_demo_reference_metrics(self, metrics: dict[str, float]) -> None:
    self._demo_metrics_available = True
    self._demo_noisy_snr = float(metrics.get("noisy_snr", 0.0))
    self._demo_enhanced_ref_snr = float(metrics.get("enhanced_snr", 0.0))
    self._demo_noisy_si_sdr = float(metrics.get("noisy_si_sdr", 0.0))
    self._demo_enhanced_ref_si_sdr = float(metrics.get("enhanced_si_sdr", 0.0))
    self._demo_noisy_stoi = float(metrics.get("noisy_stoi", 0.0))
    self._demo_enhanced_ref_stoi = float(metrics.get("enhanced_stoi", 0.0))
    self._demo_noisy_pesq = float(metrics.get("noisy_pesq", 0.0))
    self._demo_enhanced_ref_pesq = float(metrics.get("enhanced_pesq", 0.0))
    self.demoStateChanged.emit()

  def set_session(self, session) -> None:
    self._session = session

  def enable_fake_visuals(self, enabled: bool = True) -> None:
    self._use_fake_visuals = enabled

  def set_operation_mode(self, mode: str) -> None:
    self._operation_mode = mode
    self.demoStateChanged.emit()
    self.benchmarkStateChanged.emit()
    self._emit_mode_presentation()
    self.clear_mode_telemetry()

  def set_benchmark_presentation(
    self,
    *,
    loaded: bool,
    unavailable_message: str,
    pretrained_model: str,
    finetuned_model: str,
    development: dict,
    recording_disjoint: dict,
  ) -> None:
    self._benchmark_loaded = bool(loaded)
    self._benchmark_unavailable_message = unavailable_message
    self._benchmark_pretrained_model = pretrained_model
    self._benchmark_finetuned_model = finetuned_model
    self._dev_benchmark = dict(development)
    self._rd_benchmark = dict(recording_disjoint)
    dev_ok = bool(development.get("available"))
    rd_ok = bool(recording_disjoint.get("available"))
    if loaded and unavailable_message and (dev_ok or rd_ok):
      self._benchmark_partial_warning = unavailable_message
    else:
      self._benchmark_partial_warning = ""
    self.benchmarkStateChanged.emit()

  def set_playback_state(self, state: str) -> None:
    self._playback_state = state
    self.demoStateChanged.emit()

  def set_demo_scenario(self, label: str) -> None:
    self._demo_scenario = label
    self.demoStateChanged.emit()
    self._emit_mode_presentation()

  def set_selected_scenario_index(self, index: int) -> None:
    self._selected_scenario_index = index
    self.demoStateChanged.emit()

  def set_scenario_labels(self, labels: list[str]) -> None:
    self._scenario_labels = list(labels)
    self.demoStateChanged.emit()

  def set_ab_mode(self, mode: str) -> None:
    self._ab_mode = mode
    self.demoStateChanged.emit()
    self._emit_mode_presentation()

  def set_pipeline_stage(self, stage: str) -> None:
    self._pipeline_stage = stage
    self.demoStateChanged.emit()

  def set_audio_status(self, status: str) -> None:
    self._audio_status = status
    self.demoStateChanged.emit()

  def set_benchmark_summary(
    self,
    development_cases: int | None,
    evaluations: int | None,
  ) -> None:
    self._development_cases = development_cases if development_cases else -1
    self._evaluations = evaluations if evaluations else -1
    self.demoStateChanged.emit()

  @Slot()
  def setDemoMode(self) -> None:
    if self._session is not None:
      self._session.set_demo_mode()

  @Slot()
  def setLiveMode(self) -> None:
    if self._session is not None:
      self._session.select_live_mode()

  @Slot()
  def setBenchmarkMode(self) -> None:
    if self._session is not None:
      self._session.set_benchmark_mode()

  @Slot()
  def play(self) -> None:
    if self._session is not None:
      self._session.play()

  @Slot()
  def startLive(self) -> None:
    if self._session is not None and self._operation_mode == "live":
      self._session.set_live_mode()

  @Slot()
  def pause(self) -> None:
    if self._session is not None:
      self._session.pause()

  @Slot()
  def stop(self) -> None:
    if self._session is not None:
      self._session.stop()

  @Slot()
  def resetDemo(self) -> None:
    if self._session is not None:
      self._session.reset_demo()

  @Slot()
  def recoverLive(self) -> None:
    if self._session is not None:
      self._session.recover_live()

  @Slot()
  def runDemoPreflight(self) -> None:
    if self._session is not None:
      self._session.run_demo_preflight()

  @Slot()
  def emergencyResetDemo(self) -> None:
    if self._session is not None:
      self._session.emergency_reset_demo()

  @Slot()
  def tryLiveAgain(self) -> None:
    if self._session is not None:
      self._session.try_live_again()

  @Slot()
  def useRecordedDemo(self) -> None:
    if self._session is not None:
      self._session.use_recorded_demo()

  @Slot()
  def stopLive(self) -> None:
    if self._session is not None:
      self._session.stop_live()

  @Slot(int)
  def selectScenario(self, index: int) -> None:
    if self._session is not None:
      self._session.set_scenario(index)

  @Slot()
  def selectAbRaw(self) -> None:
    if self._session is not None:
      self._session.set_ab_raw()

  @Slot()
  def selectAbEnhanced(self) -> None:
    if self._session is not None:
      self._session.set_ab_enhanced()

  @Slot(int)
  def selectInputDevice(self, index: int) -> None:
    if self._session is not None:
      self._session.select_input_device(index)

  @Slot(int)
  def selectOutputDevice(self, index: int) -> None:
    if self._session is not None:
      self._session.select_output_device(index)

  @Slot(int)
  def selectModel(self, index: int) -> None:
    if self._session is not None:
      self._session.select_model(index)

  @Slot()
  def refreshDevices(self) -> None:
    if self._session is not None:
      self._session.refresh_devices()

  @Slot(bool)
  def setShowAllDevices(self, show_all: bool) -> None:
    if self._session is not None:
      self._session.set_show_all_devices(show_all)

  @Property(list, notify=historyUpdated)
  def procTimeHistory(self) -> list[float]:
    return list(self._proc_time_hist)

  @Property(list, notify=historyUpdated)
  def bufferFillHistory(self) -> list[float]:
    return list(self._buffer_fill_hist)

  @Property(list, notify=historyUpdated)
  def droppedHistory(self) -> list[float]:
    return list(self._dropped_hist)

  @Property(list, notify=historyUpdated)
  def rtfHistory(self) -> list[float]:
    return list(self._rtf_hist)

  def set_error(self, message: str) -> None:
    self._error_message = message
    self.errorChanged.emit()
    self.telemetryUpdated.emit()

  def clear_error(self) -> None:
    if self._error_message:
      self._error_message = ""
      self.errorChanged.emit()

  def set_stream_metadata(self, *, model_name: str, sample_rate: int) -> None:
    self._latest_telemetry.model_name = model_name
    self._latest_telemetry.sample_rate = sample_rate
    self.telemetryUpdated.emit()

  def begin_telemetry_session(self) -> None:
    """Drop held numbers and start a new measurement session for this mode."""

    self._discard_pending_snapshot()
    self._reset_measurement_values()
    self._telemetry_token += 1
    self._telemetry_session_open = True
    self._telemetry_hold_note = ""
    self._emit_measurement_signals()

  def end_telemetry_session(self, note: str) -> None:
    """Keep the last samples from this session and label them as held."""

    self._telemetry_session_open = False
    self._telemetry_hold_note = note
    if self._processing_measured or self._overflow_measured:
      self._telemetry_note = note
    self.telemetryUpdated.emit()

  def clear_mode_telemetry(self) -> None:
    """Forget measurements so another mode cannot display them."""

    self._discard_pending_snapshot()
    self._telemetry_token += 1
    self._telemetry_session_open = False
    self._telemetry_hold_note = ""
    self._reset_measurement_values()
    self._emit_measurement_signals()

  def _discard_pending_snapshot(self) -> None:
    with self._telemetry_lock:
      self._pending_snapshot = _TelemetrySnapshot()

  def _reset_measurement_values(self) -> None:
    model_name = self._latest_telemetry.model_name
    sample_rate = self._latest_telemetry.sample_rate
    self._latest_telemetry = AudioTelemetry()
    self._latest_telemetry.model_name = model_name
    self._latest_telemetry.sample_rate = sample_rate
    self._processing_measured = False
    self._rtf_measured = False
    self._overflow_measured = False
    self._overflow_count = 0
    self._live_input_overflows = 0
    self._telemetry_note = ""
    self._proc_time_hist.clear()
    self._buffer_fill_hist.clear()
    self._dropped_hist.clear()
    self._rtf_hist.clear()
    self._latest_input_waveform = []
    self._latest_output_waveform = []

  def _emit_measurement_signals(self) -> None:
    self.telemetryUpdated.emit()
    self.historyUpdated.emit()
    self.liveStateChanged.emit()
    self.inputWaveformUpdated.emit(self._latest_input_waveform)
    self.outputWaveformUpdated.emit(self._latest_output_waveform)

  def publish_data(
    self,
    input_chunk: np.ndarray,
    output_chunk: np.ndarray,
    proc_time_s: float,
    stats: dict | None = None,
  ) -> None:
    """Called from the audio thread with the latest chunk snapshot."""

    snapshot = _TelemetrySnapshot(
      input_chunk=(
        np.array(input_chunk, dtype=np.float32, copy=True)
        if len(input_chunk) > 0
        else None
      ),
      output_chunk=(
        np.array(output_chunk, dtype=np.float32, copy=True)
        if len(output_chunk) > 0
        else None
      ),
      processing_time_s=proc_time_s,
      stats=dict(stats) if stats else {},
      has_update=True,
      source_mode=self._operation_mode,
      session_token=self._telemetry_token,
    )

    with self._telemetry_lock:
      self._pending_snapshot = snapshot

  def _consume_snapshot(self) -> _TelemetrySnapshot | None:
    with self._telemetry_lock:
      if not self._pending_snapshot.has_update:
        return None

      snapshot = self._pending_snapshot
      self._pending_snapshot = _TelemetrySnapshot()
      return snapshot

  def _apply_snapshot(self, snapshot: _TelemetrySnapshot) -> bool:
    if snapshot.session_token != self._telemetry_token:
      return False
    if snapshot.source_mode != self._operation_mode:
      return False
    if self._operation_mode not in {"demo", "live"}:
      return False

    t = self._latest_telemetry
    t.is_live = self._operation_mode == "live"
    t.processing_time_ms = snapshot.processing_time_s * 1000.0
    self._processing_measured = True

    input_chunk = snapshot.input_chunk
    output_chunk = snapshot.output_chunk

    if input_chunk is not None and len(input_chunk) > 0:
      rms_in = float(np.sqrt(np.mean(input_chunk**2) + 1e-10))
      peak_in = float(np.max(np.abs(input_chunk)) + 1e-10)
      t.input_level_db = 20 * math.log10(rms_in)
      t.input_peak_db = 20 * math.log10(peak_in)

    if output_chunk is not None and len(output_chunk) > 0:
      rms_out = float(np.sqrt(np.mean(output_chunk**2) + 1e-10))
      peak_out = float(np.max(np.abs(output_chunk)) + 1e-10)
      t.output_level_db = 20 * math.log10(rms_out)
      t.output_peak_db = 20 * math.log10(peak_out)

    chunk_samples = len(input_chunk) if input_chunk is not None else 0
    chunk_duration = chunk_samples / max(1, t.sample_rate)
    if chunk_duration > 0:
      # Processing RTF: time inside process_stream divided by chunk duration.
      # This is not wall-clock RTF and not an end-to-end live factor.
      t.realtime_factor = snapshot.processing_time_s / chunk_duration
      self._rtf_measured = True

    # Buffer fill is not read from PortAudio or the playback queue.
    t.buffer_fill_percent = 0.0

    if self._operation_mode == "live" and "input_overflows" in snapshot.stats:
      overflows = int(snapshot.stats.get("input_overflows", 0))
      self._overflow_count = overflows
      self._overflow_measured = True
      self._live_input_overflows = overflows
      t.dropped_frames = overflows

    if self._telemetry_session_open:
      self._telemetry_note = ""
    elif self._telemetry_hold_note:
      self._telemetry_note = self._telemetry_hold_note

    input_reduced, output_reduced = self._waveform_processor.process(
      input_chunk if input_chunk is not None else np.array([], dtype=np.float32),
      output_chunk if output_chunk is not None else np.array([], dtype=np.float32),
    )
    self._latest_input_waveform = input_reduced.tolist()
    self._latest_output_waveform = output_reduced.tolist()
    return True

  @Slot()
  def _on_timeout(self) -> None:
    snapshot = self._consume_snapshot()
    applied = False

    if snapshot is not None:
      applied = self._apply_snapshot(snapshot)
    elif (
      self._use_fake_visuals
      and not self._telemetry_session_open
      and not self._processing_measured
      and self._operation_mode != "benchmark"
    ):
      self._generate_fake_waveforms()

    if applied:
      t = self._latest_telemetry
      self._proc_time_hist.append(t.processing_time_ms)
      if self._rtf_measured:
        self._rtf_hist.append(t.realtime_factor)
      if self._overflow_measured:
        self._dropped_hist.append(float(self._overflow_count))
      self.historyUpdated.emit()

    self.telemetryUpdated.emit()
    self.inputWaveformUpdated.emit(self._latest_input_waveform)
    self.outputWaveformUpdated.emit(self._latest_output_waveform)

  def _generate_fake_waveforms(self) -> None:
    """Animate waveforms for --fake. Do not invent latency, RTF, or overflows."""

    self._phase += 0.15
    envelope = max(0, math.sin(self._phase * 0.4) * math.sin(self._phase * 0.13))
    envelope = envelope**2

    x = np.linspace(0, 10 * np.pi, 500)
    carrier = (
      np.sin(x * 3.5) + 0.5 * np.sin(x * 7.2) + 0.25 * np.sin(x * 15.1)
    )
    clean_speech = carrier * envelope * 0.8
    noise_envelope = 0.15 + 0.05 * math.sin(self._phase * 0.1)
    noise = np.random.normal(0, noise_envelope, 500)
    noisy_speech = clean_speech + noise

    self._latest_input_waveform = noisy_speech.tolist()
    self._latest_output_waveform = clean_speech.tolist()
