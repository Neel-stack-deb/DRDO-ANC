#!/usr/bin/env python3
"""GUI mode presentation: demo and live controls stay on the correct screen."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QML_DISABLE_DISK_CACHE", "1")

src_dir = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(src_dir))

from PySide6.QtCore import QObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from drdo_anc.gui.bridge import GUIBridge
from drdo_anc.gui.live_state import (
    LIVE_STATUS_ERROR,
    LIVE_STATUS_IDLE,
    LIVE_STATUS_LIVE,
    LIVE_STATUS_STARTING,
    LIVE_STATUS_STOPPING,
)
_APP = QGuiApplication.instance() or QGuiApplication([])

from drdo_anc.gui.mode_presentation import (
    BENCHMARK_DESCRIPTION,
    DEMO_DESCRIPTION,
    DEMO_ONLY_CONTROLS,
    LIVE_DESCRIPTION,
    LIVE_ONLY_CONTROLS,
    activity_caption,
    audio_selectors_enabled,
    mode_banner,
    mode_description,
    visible_controls,
)

QML_CONTROLS = {
    "scenario": "scenarioRow",
    "demo_preflight": "demoPreflightButton",
    "reset_demo": "resetDemoButton",
    "play": "playButton",
    "pause": "pauseButton",
    "stop": "stopButton",
    "reset": "resetButton",
    "ab_raw": "abRawButton",
    "ab_enhanced": "abEnhancedButton",
    "start_live": "startLiveButton",
    "stop_live": "stopLiveButton",
    "live_starting": "liveStartingLabel",
    "recover_live": "recoverLiveButton",
    "live_fallback": "liveFallbackRow",
    "model": "modelRow",
    "input_device": "inputDeviceRow",
    "output_device": "outputDeviceRow",
    "refresh_devices": "refreshDevicesButton",
    "show_all_devices": "showAllDevicesBox",
}


class _SessionProbe:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def set_live_mode(self) -> None:
        self.calls.append("set_live_mode")

    def play(self) -> None:
        self.calls.append("play")

    def stop_live(self) -> None:
        self.calls.append("stop_live")


class _Console:
    def __init__(self) -> None:
        self.app = QGuiApplication.instance() or QGuiApplication([])
        self.bridge = GUIBridge()
        self.engine = QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty("guiBridge", self.bridge)
        qml = Path(__file__).resolve().parent.parent / "src" / "drdo_anc" / "gui" / "qml" / "Main.qml"
        self.engine.load(os.fspath(qml))
        if not self.engine.rootObjects():
            raise RuntimeError(f"Failed to load {qml}")
        self.root = self.engine.rootObjects()[0]
        self.sync()

    def sync(self) -> None:
        self.app.processEvents()

    def item(self, name: str) -> QObject:
        found = self.root.findChild(QObject, name)
        if found is None:
            raise AssertionError(f"QML object {name!r} was not created")
        return found

    def effectively_visible(self, name: str) -> bool:
        item = self.item(name)
        checker = getattr(item, "isVisible", None)
        if checker is not None:
            return bool(checker())
        return bool(item.property("visible"))


def test_demo_and_live_control_sets_are_disjoint() -> None:
    assert DEMO_ONLY_CONTROLS.isdisjoint(LIVE_ONLY_CONTROLS)
    demo = visible_controls("demo", LIVE_STATUS_IDLE)
    live = visible_controls("live", LIVE_STATUS_IDLE)
    assert DEMO_ONLY_CONTROLS <= demo
    assert DEMO_ONLY_CONTROLS.isdisjoint(live)
    assert "start_live" in live
    assert LIVE_ONLY_CONTROLS.isdisjoint(demo)


def test_live_transport_follows_existing_live_status() -> None:
    assert visible_controls("live", LIVE_STATUS_IDLE) >= {"start_live"}
    assert "stop_live" not in visible_controls("live", LIVE_STATUS_IDLE)
    running = visible_controls("live", LIVE_STATUS_LIVE)
    assert "stop_live" in running
    assert "start_live" not in running
    starting = visible_controls("live", LIVE_STATUS_STARTING)
    assert starting >= {"live_starting"}
    assert "start_live" not in starting
    assert "stop_live" not in starting
    assert not audio_selectors_enabled("live", LIVE_STATUS_STARTING, devices_locked=False)
    error = visible_controls("live", LIVE_STATUS_ERROR, live_fallback_offered=True)
    assert "recover_live" in error
    assert "live_fallback" in error
    assert "start_live" not in error
    assert "play" not in error
    stopping = visible_controls("live", LIVE_STATUS_STOPPING)
    assert "stop_live" in stopping
    assert "start_live" not in stopping


def test_headers_and_descriptions_match_mode() -> None:
    assert mode_banner("demo", LIVE_STATUS_LIVE) == "RECORDED DEMO"
    assert mode_banner("live", LIVE_STATUS_IDLE) == "LIVE MICROPHONE · IDLE"
    assert mode_banner("live", LIVE_STATUS_STARTING) == "LIVE MICROPHONE · STARTING"
    assert mode_banner("live", LIVE_STATUS_LIVE) == "LIVE MICROPHONE · LIVE"
    assert mode_banner("live", LIVE_STATUS_ERROR) == "LIVE MICROPHONE · ERROR"
    assert mode_banner("benchmark", LIVE_STATUS_IDLE) == "BENCHMARK"
    assert "RECORDED DEMO" not in mode_banner("live", LIVE_STATUS_IDLE)
    assert mode_description("demo") == DEMO_DESCRIPTION
    assert mode_description("live") == LIVE_DESCRIPTION
    assert mode_description("benchmark") == BENCHMARK_DESCRIPTION


def test_activity_caption_does_not_leak_across_modes() -> None:
    demo = activity_caption(
        "demo",
        demo_status="STOPPED",
        demo_scenario="Mixed Speech — SNR 5 dB",
        ab_mode="raw",
        duration_s=3.0,
        live_status=LIVE_STATUS_LIVE,
        overflows=4,
    )
    assert "Mixed Speech — SNR 5 dB" in demo
    assert "A Raw" in demo
    assert demo.endswith("3.0 s")
    live = activity_caption(
        "live",
        demo_status="STOPPED",
        demo_scenario="Mixed Speech — SNR 5 dB",
        ab_mode="raw",
        duration_s=3.0,
        live_status=LIVE_STATUS_IDLE,
        overflows=0,
    )
    assert live == "LIVE   ·   IDLE   ·   overflows 0"
    assert "Mixed Speech" not in live
    assert "3.0 s" not in live
    assert activity_caption(
        "benchmark",
        demo_status="STOPPED",
        demo_scenario="Mixed Speech — SNR 5 dB",
        ab_mode="enhanced",
        duration_s=3.0,
        live_status=LIVE_STATUS_LIVE,
        overflows=1,
    ) == ""


def test_start_live_slot_uses_live_startup_not_demo_play() -> None:
    bridge = GUIBridge()
    session = _SessionProbe()
    bridge.set_session(session)
    bridge.set_operation_mode("live")
    bridge.startLive()
    bridge.set_operation_mode("demo")
    bridge.startLive()
    bridge.play()
    assert session.calls == ["set_live_mode", "play"]


def _assert_qml_matches_policy(ui: _Console, *, fallback: bool = False) -> None:
    mode = ui.bridge.operationMode
    status = ui.bridge.liveStatus
    expected = visible_controls(mode, status, live_fallback_offered=fallback)
    for control, name in QML_CONTROLS.items():
        shown = ui.effectively_visible(name)
        if shown != (control in expected):
            raise AssertionError(
                f"{mode}/{status} fallback={fallback}: {control} visible={shown}, "
                f"expected {control in expected}"
            )


def test_qml_modes_do_not_leave_stale_controls() -> None:
    ui = _Console()
    bridge = ui.bridge
    bridge.set_demo_status("STOPPED")
    bridge.set_demo_scenario_details(
        label="Mixed Speech — SNR 5 dB",
        source_file="train_noisy_snr5.wav",
        sample_rate=48000,
        model_name="DeepFilterNet3-Finetuned",
        duration_s=3.0,
    )
    bridge.set_operation_mode("demo")
    ui.sync()

    assert ui.item("modeBanner").property("text") == "RECORDED DEMO"
    assert ui.item("modeDescription").property("text") == DEMO_DESCRIPTION
    caption = ui.item("activityCaption").property("text")
    assert "Mixed Speech — SNR 5 dB" in caption
    assert "3.0 s" in caption
    _assert_qml_matches_policy(ui)
    assert ui.effectively_visible("playButton")
    assert ui.effectively_visible("pauseButton")
    assert ui.effectively_visible("stopButton")
    assert ui.effectively_visible("resetButton")
    assert not ui.effectively_visible("startLiveButton")
    assert ui.item("abRawButton").property("active") is True

    bridge.set_operation_mode("live")
    bridge.set_live_status(LIVE_STATUS_IDLE)
    ui.sync()
    assert ui.item("modeBanner").property("text") == "LIVE MICROPHONE · IDLE"
    assert ui.item("modeDescription").property("text") == LIVE_DESCRIPTION
    assert "RECORDED DEMO" not in ui.item("modeBanner").property("text")
    live_caption = ui.item("activityCaption").property("text")
    assert live_caption == "LIVE   ·   IDLE   ·   overflows 0"
    assert "Mixed Speech" not in live_caption
    _assert_qml_matches_policy(ui)
    assert ui.effectively_visible("startLiveButton")
    assert ui.item("startLiveButton").property("enabled") is True
    assert not ui.effectively_visible("stopLiveButton")
    assert ui.effectively_visible("modelRow")
    assert ui.effectively_visible("inputDeviceRow")
    assert ui.effectively_visible("outputDeviceRow")

    bridge.set_live_status(LIVE_STATUS_STARTING)
    ui.sync()
    assert ui.item("modeBanner").property("text") == "LIVE MICROPHONE · STARTING"
    assert ui.effectively_visible("liveStartingLabel")
    assert not ui.effectively_visible("startLiveButton")
    assert not ui.effectively_visible("playButton")
    assert ui.item("inputDeviceCombo").property("enabled") is False
    assert ui.item("modelCombo").property("enabled") is False
    _assert_qml_matches_policy(ui)

    bridge.set_live_status(LIVE_STATUS_LIVE)
    ui.sync()
    assert ui.item("modeBanner").property("text") == "LIVE MICROPHONE · LIVE"
    assert ui.effectively_visible("stopLiveButton")
    assert ui.item("stopLiveButton").property("enabled") is True
    assert not ui.effectively_visible("startLiveButton")
    assert not ui.effectively_visible("demoPreflightButton")
    assert not ui.effectively_visible("scenarioRow")
    _assert_qml_matches_policy(ui)

    bridge.set_live_status(LIVE_STATUS_ERROR)
    bridge.offer_live_fallback("Live audio could not be started.")
    ui.sync()
    assert ui.item("modeBanner").property("text") == "LIVE MICROPHONE · ERROR"
    assert ui.effectively_visible("recoverLiveButton")
    assert ui.effectively_visible("liveFallbackRow")
    assert ui.effectively_visible("tryLiveAgainButton")
    assert ui.effectively_visible("useRecordedDemoButton")
    assert not ui.effectively_visible("startLiveButton")
    assert not ui.effectively_visible("playButton")
    _assert_qml_matches_policy(ui, fallback=True)

    bridge.clear_live_fallback()
    bridge.set_operation_mode("benchmark")
    ui.sync()
    assert ui.item("modeBanner").property("text") == "BENCHMARK"
    assert ui.item("modeDescription").property("text") == BENCHMARK_DESCRIPTION
    assert not ui.effectively_visible("activityCaption")
    assert not ui.effectively_visible("playButton")
    assert not ui.effectively_visible("startLiveButton")
    assert not ui.effectively_visible("stopLiveButton")
    assert not ui.effectively_visible("scenarioRow")
    assert not ui.effectively_visible("modelRow")
    _assert_qml_matches_policy(ui)

    bridge.set_operation_mode("demo")
    bridge.set_live_status(LIVE_STATUS_IDLE)
    ui.sync()
    assert ui.item("modeBanner").property("text") == "RECORDED DEMO"
    assert ui.effectively_visible("playButton")
    assert ui.effectively_visible("pauseButton")
    assert ui.effectively_visible("stopButton")
    assert ui.effectively_visible("resetButton")
    assert ui.effectively_visible("demoPreflightButton")
    assert ui.effectively_visible("resetDemoButton")
    assert ui.effectively_visible("scenarioRow")
    assert ui.effectively_visible("abRawButton")
    assert ui.effectively_visible("abEnhancedButton")
    assert not ui.effectively_visible("startLiveButton")
    assert not ui.effectively_visible("stopLiveButton")
    assert not ui.effectively_visible("liveFallbackRow")
    assert not ui.effectively_visible("recoverLiveButton")
    _assert_qml_matches_policy(ui)


def main() -> int:
    _ = QGuiApplication.instance() or QGuiApplication([])
    tests = [
        test_demo_and_live_control_sets_are_disjoint,
        test_live_transport_follows_existing_live_status,
        test_headers_and_descriptions_match_mode,
        test_activity_caption_does_not_leak_across_modes,
        test_start_live_slot_uses_live_startup_not_demo_play,
        test_qml_modes_do_not_leave_stale_controls,
    ]
    failed = 0
    for test in tests:
        name = getattr(test, "__name__", "test_qml_modes_do_not_leave_stale_controls")
        try:
            test()
            print(f"PASS {name}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {name}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
