#!/usr/bin/env python3
"""Telemetry ownership: live numbers must not appear as demo or benchmark results."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QML_DISABLE_DISK_CACHE", "1")

src_dir = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(src_dir))

import numpy as np
from PySide6.QtCore import QObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from drdo_anc.gui.bridge import GUIBridge
from drdo_anc.gui.telemetry import (
    BUFFER_FILL_LABEL,
    HOLD_DEMO,
    HOLD_LIVE,
    INPUT_OVERFLOWS_LABEL,
    PROCESSING_RTF_LABEL,
    TELEMETRY_UNAVAILABLE,
)

_APP = QGuiApplication.instance() or QGuiApplication([])


def _chunk(seconds: float = 0.01, sample_rate: int = 48000) -> np.ndarray:
    count = int(seconds * sample_rate)
    return np.full(count, 0.1, dtype=np.float32)


def _publish_live(bridge: GUIBridge, proc_s: float, overflows: int) -> None:
    bridge.set_operation_mode("live")
    bridge.begin_telemetry_session()
    audio = _chunk()
    bridge.publish_data(
        audio,
        audio,
        proc_s,
        stats={"input_overflows": overflows, "output_underflows": 9},
    )
    bridge._on_timeout()


def test_labels_match_the_measurement() -> None:
    bridge = GUIBridge()
    assert bridge.overflowLabel == INPUT_OVERFLOWS_LABEL
    assert bridge.overflowLabel != "DROPPED PACKETS"
    assert bridge.rtfLabel == PROCESSING_RTF_LABEL
    assert bridge.rtfLabel != "REAL-TIME FACTOR"
    assert bridge.bufferFillLabel == BUFFER_FILL_LABEL
    assert bridge.bufferMeasured is False
    assert bridge.bufferValueText == TELEMETRY_UNAVAILABLE
    assert "chunk duration" in bridge.rtfHint
    assert "PortAudio" in bridge.overflowHint or bridge.operationMode != "live"


def test_live_telemetry_does_not_appear_as_demo() -> None:
    bridge = GUIBridge()
    bridge.set_stream_metadata(model_name="DeepFilterNet3-Finetuned", sample_rate=48000)
    _publish_live(bridge, 0.00261, 4)
    assert bridge.processingMeasured is True
    assert abs(bridge.processingTimeMs - 2.61) < 0.02
    assert bridge.rtfMeasured is True
    assert abs(bridge.realtimeFactor - 0.261) < 0.01
    assert bridge.overflowMeasured is True
    assert bridge.overflowValueText == "4"
    assert bridge.droppedFrames == 4

    bridge.set_operation_mode("demo")
    assert bridge.processingMeasured is False
    assert bridge.rtfMeasured is False
    assert bridge.overflowMeasured is False
    assert bridge.processingValueText == TELEMETRY_UNAVAILABLE
    assert bridge.rtfValueText == TELEMETRY_UNAVAILABLE
    assert bridge.overflowValueText == TELEMETRY_UNAVAILABLE
    assert bridge.procTimeHistory == []
    assert bridge.rtfHistory == []
    assert bridge.modelName == "DeepFilterNet3-Finetuned"
    assert bridge.sampleRate == 48000


def test_demo_does_not_reuse_hardcoded_overflows() -> None:
    bridge = GUIBridge()
    bridge.set_stream_metadata(model_name="DeepFilterNet3-Finetuned", sample_rate=48000)
    bridge.set_operation_mode("demo")
    bridge.begin_telemetry_session()
    audio = _chunk()
    bridge.publish_data(
        audio,
        audio,
        0.001,
        stats={"input_overflows": 0, "output_underflows": 0},
    )
    bridge._on_timeout()
    assert bridge.processingMeasured is True
    assert abs(bridge.processingTimeMs - 1.0) < 0.02
    assert bridge.rtfMeasured is True
    assert bridge.overflowMeasured is False
    assert bridge.overflowValueText == TELEMETRY_UNAVAILABLE
    assert bridge.bufferMeasured is False


def test_reset_clears_demo_telemetry() -> None:
    bridge = GUIBridge()
    bridge.set_operation_mode("demo")
    bridge.begin_telemetry_session()
    audio = _chunk()
    bridge.publish_data(audio, audio, 0.004, stats={})
    bridge._on_timeout()
    assert bridge.processingMeasured is True
    bridge.clear_mode_telemetry()
    assert bridge.processingMeasured is False
    assert bridge.processingValueText == TELEMETRY_UNAVAILABLE
    assert bridge.procTimeHistory == []
    assert bridge.telemetryNote == ""


def test_live_stop_holds_last_session_until_mode_change() -> None:
    bridge = GUIBridge()
    _publish_live(bridge, 0.002, 2)
    bridge.end_telemetry_session(HOLD_LIVE)
    assert bridge.telemetryNote == HOLD_LIVE
    assert bridge.overflowValueText == "2"
    assert abs(bridge.processingTimeMs - 2.0) < 0.02
    bridge._on_timeout()
    assert len(bridge.procTimeHistory) == 1


def test_mode_cycle_does_not_leak_telemetry() -> None:
    bridge = GUIBridge()
    bridge.set_stream_metadata(model_name="DeepFilterNet3-Finetuned", sample_rate=48000)
    bridge.set_operation_mode("demo")
    bridge.begin_telemetry_session()
    audio = _chunk()
    bridge.publish_data(audio, audio, 0.009, stats={"input_overflows": 0})
    bridge._on_timeout()
    assert abs(bridge.processingTimeMs - 9.0) < 0.02

    bridge.set_operation_mode("live")
    assert bridge.processingValueText == TELEMETRY_UNAVAILABLE
    _publish_live(bridge, 0.00261, 7)
    assert bridge.overflowValueText == "7"
    assert abs(bridge.processingTimeMs - 2.61) < 0.02

    bridge.set_operation_mode("demo")
    assert bridge.processingValueText == TELEMETRY_UNAVAILABLE
    assert bridge.overflowValueText == TELEMETRY_UNAVAILABLE
    assert bridge.rtfValueText == TELEMETRY_UNAVAILABLE
    assert "2.61" not in bridge.processingValueText


def test_benchmark_metrics_stay_independent() -> None:
    bridge = GUIBridge()
    bridge.set_benchmark_presentation(
        loaded=True,
        unavailable_message="",
        pretrained_model="DeepFilterNet3",
        finetuned_model="DeepFilterNet3-Finetuned",
        development={"available": True, "pretrained_si_sdr": 12.71},
        recording_disjoint={"available": True, "si_sdr_improvement": 3.18},
    )
    _publish_live(bridge, 0.00261, 5)
    bridge.set_operation_mode("benchmark")
    assert bridge.devPretrainedSiSdr == 12.71
    assert bridge.processingMeasured is False
    assert bridge.overflowMeasured is False
    assert bridge.processingValueText == TELEMETRY_UNAVAILABLE
    assert bridge.isBenchmarkMode is True


def test_pending_snapshot_from_previous_mode_is_discarded() -> None:
    bridge = GUIBridge()
    bridge.set_operation_mode("live")
    bridge.begin_telemetry_session()
    audio = _chunk()
    bridge.publish_data(audio, audio, 0.00261, stats={"input_overflows": 3})
    bridge.set_operation_mode("demo")
    bridge._on_timeout()
    assert bridge.processingMeasured is False
    assert bridge.overflowValueText == TELEMETRY_UNAVAILABLE


def test_qml_labels_follow_bridge() -> None:
    bridge = GUIBridge()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("guiBridge", bridge)
    qml = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "drdo_anc"
        / "gui"
        / "qml"
        / "Main.qml"
    )
    engine.load(os.fspath(qml))
    if not engine.rootObjects():
        raise RuntimeError(f"Failed to load {qml}")
    root = engine.rootObjects()[0]
    _APP.processEvents()

    def text_of(name: str) -> str:
        item = root.findChild(QObject, name)
        if item is None:
            raise AssertionError(f"missing {name}")
        return str(item.property("text"))

    assert text_of("overflowLabel") == INPUT_OVERFLOWS_LABEL
    assert text_of("rtfLabel") == PROCESSING_RTF_LABEL
    assert text_of("bufferFillLabel") == BUFFER_FILL_LABEL
    assert text_of("overflowValue") == TELEMETRY_UNAVAILABLE
    assert text_of("processingValue") == TELEMETRY_UNAVAILABLE
    assert text_of("rtfValue") == TELEMETRY_UNAVAILABLE
    assert "DROPPED PACKETS" not in text_of("overflowLabel")
    assert "REAL-TIME FACTOR" not in text_of("rtfLabel")
    assert text_of("systemGuiFps").endswith(str(bridge.guiFps))

    _publish_live(bridge, 0.00261, 4)
    _APP.processEvents()
    assert text_of("overflowValue") == "4"
    assert text_of("processingValue") == "2.61"

    bridge.set_operation_mode("demo")
    _APP.processEvents()
    assert text_of("overflowValue") == TELEMETRY_UNAVAILABLE
    assert text_of("processingValue") == TELEMETRY_UNAVAILABLE
    assert text_of("rtfValue") == TELEMETRY_UNAVAILABLE
    bridge.end_telemetry_session(HOLD_DEMO)
    assert bridge.telemetryNote == ""


def main() -> int:
    tests = [
        test_labels_match_the_measurement,
        test_live_telemetry_does_not_appear_as_demo,
        test_demo_does_not_reuse_hardcoded_overflows,
        test_reset_clears_demo_telemetry,
        test_live_stop_holds_last_session_until_mode_change,
        test_mode_cycle_does_not_leak_telemetry,
        test_benchmark_metrics_stay_independent,
        test_pending_snapshot_from_previous_mode_is_discarded,
        test_qml_labels_follow_bridge,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {test.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
