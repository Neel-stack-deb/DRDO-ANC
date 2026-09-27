"""Pytest entry for GUI telemetry ownership."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parent.parent / "scripts" / "test_gui_telemetry.py"
    spec = importlib.util.spec_from_file_location("test_gui_telemetry", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_mod = _load()


def test_labels_match_the_measurement() -> None:
    _mod.test_labels_match_the_measurement()


def test_live_telemetry_does_not_appear_as_demo() -> None:
    _mod.test_live_telemetry_does_not_appear_as_demo()


def test_demo_does_not_reuse_hardcoded_overflows() -> None:
    _mod.test_demo_does_not_reuse_hardcoded_overflows()


def test_reset_clears_demo_telemetry() -> None:
    _mod.test_reset_clears_demo_telemetry()


def test_live_stop_holds_last_session_until_mode_change() -> None:
    _mod.test_live_stop_holds_last_session_until_mode_change()


def test_mode_cycle_does_not_leak_telemetry() -> None:
    _mod.test_mode_cycle_does_not_leak_telemetry()


def test_benchmark_metrics_stay_independent() -> None:
    _mod.test_benchmark_metrics_stay_independent()


def test_pending_snapshot_from_previous_mode_is_discarded() -> None:
    _mod.test_pending_snapshot_from_previous_mode_is_discarded()


def test_qml_labels_follow_bridge() -> None:
    _mod.test_qml_labels_follow_bridge()
