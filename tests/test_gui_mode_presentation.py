"""Mode header, description, and control-visibility rules."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from drdo_anc.gui.live_state import (
    LIVE_STATUS_ERROR,
    LIVE_STATUS_IDLE,
    LIVE_STATUS_LIVE,
    LIVE_STATUS_STARTING,
)
from drdo_anc.gui.mode_presentation import (
    BENCHMARK_DESCRIPTION,
    DEMO_DESCRIPTION,
    DEMO_ONLY_CONTROLS,
    LIVE_DESCRIPTION,
    LIVE_ONLY_CONTROLS,
    activity_caption,
    mode_banner,
    mode_description,
    visible_controls,
)


def test_demo_does_not_expose_live_only_controls() -> None:
    shown = visible_controls("demo", LIVE_STATUS_IDLE)
    assert LIVE_ONLY_CONTROLS.isdisjoint(shown)
    assert {"play", "pause", "stop", "reset", "scenario", "demo_preflight", "reset_demo"} <= shown


def test_live_does_not_expose_demo_only_controls() -> None:
    for status in (LIVE_STATUS_IDLE, LIVE_STATUS_LIVE, LIVE_STATUS_STARTING, LIVE_STATUS_ERROR):
        shown = visible_controls("live", status, live_fallback_offered=True)
        assert DEMO_ONLY_CONTROLS.isdisjoint(shown)


def test_live_idle_shows_start_and_running_shows_stop() -> None:
    assert "start_live" in visible_controls("live", LIVE_STATUS_IDLE)
    assert "stop_live" not in visible_controls("live", LIVE_STATUS_IDLE)
    running = visible_controls("live", LIVE_STATUS_LIVE)
    assert "stop_live" in running
    assert "start_live" not in running


def test_headers_and_descriptions() -> None:
    assert mode_banner("demo", LIVE_STATUS_IDLE) == "RECORDED DEMO"
    assert mode_banner("live", LIVE_STATUS_IDLE) == "LIVE MICROPHONE · IDLE"
    assert mode_banner("live", LIVE_STATUS_STARTING) == "LIVE MICROPHONE · STARTING"
    assert mode_banner("live", LIVE_STATUS_LIVE) == "LIVE MICROPHONE · LIVE"
    assert mode_banner("live", LIVE_STATUS_ERROR) == "LIVE MICROPHONE · ERROR"
    assert mode_banner("benchmark", LIVE_STATUS_LIVE) == "BENCHMARK"
    assert mode_description("demo") == DEMO_DESCRIPTION
    assert mode_description("live") == LIVE_DESCRIPTION
    assert mode_description("benchmark") == BENCHMARK_DESCRIPTION


def test_mode_cycle_does_not_keep_previous_controls() -> None:
    sequence = ["demo", "live", "benchmark", "demo"]
    previous: frozenset[str] = frozenset()
    for mode in sequence:
        shown = visible_controls(mode, LIVE_STATUS_IDLE)
        if mode == "demo":
            assert "play" in shown
            assert "start_live" not in shown
        elif mode == "live":
            assert "start_live" in shown
            assert "play" not in shown
            assert previous.isdisjoint(DEMO_ONLY_CONTROLS & shown)
        else:
            assert shown == frozenset()
            assert "play" not in shown
            assert "start_live" not in shown
        previous = shown


def test_live_caption_omits_recorded_demo_fields() -> None:
    live = activity_caption(
        "live",
        demo_status="PLAYING RAW",
        demo_scenario="Mixed Speech — SNR 5 dB",
        ab_mode="raw",
        duration_s=3.0,
        live_status=LIVE_STATUS_IDLE,
        overflows=0,
    )
    assert "Mixed Speech" not in live
    assert "3.0 s" not in live
