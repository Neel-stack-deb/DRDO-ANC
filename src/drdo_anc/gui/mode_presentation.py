"""Which controls and labels each GUI mode is allowed to show.

Live capture has no runtime raw/enhanced switch. A/B routing stays on the
recorded-demo playback queue only.
"""

from __future__ import annotations

from drdo_anc.gui.live_state import (
    LIVE_STATUS_ERROR,
    LIVE_STATUS_IDLE,
    LIVE_STATUS_LIVE,
    LIVE_STATUS_STARTING,
    LIVE_STATUS_STOPPING,
)

DEMO_MODE = "demo"
LIVE_MODE = "live"
BENCHMARK_MODE = "benchmark"

DEMO_DESCRIPTION = (
    "Recorded comparison — hear the same noisy speech before and after enhancement."
)
LIVE_DESCRIPTION = "Live microphone — speech is enhanced continuously in real time."
BENCHMARK_DESCRIPTION = (
    "Offline evaluation — pretrained vs fine-tuned model on the SIH-26 evaluation protocol."
)

MODE_DESCRIPTION = {
    DEMO_MODE: DEMO_DESCRIPTION,
    LIVE_MODE: LIVE_DESCRIPTION,
    BENCHMARK_MODE: BENCHMARK_DESCRIPTION,
}

DEMO_ONLY_CONTROLS = frozenset(
    {
        "scenario",
        "demo_preflight",
        "reset_demo",
        "play",
        "pause",
        "stop",
        "reset",
        "ab_raw",
        "ab_enhanced",
    }
)

LIVE_ONLY_CONTROLS = frozenset(
    {
        "start_live",
        "stop_live",
        "live_starting",
        "recover_live",
        "live_fallback",
    }
)

SHARED_AUDIO_CONTROLS = frozenset(
    {
        "model",
        "input_device",
        "output_device",
        "refresh_devices",
        "show_all_devices",
    }
)

_LIVE_SELECTOR_LOCK = {
    LIVE_STATUS_STARTING,
    LIVE_STATUS_LIVE,
    LIVE_STATUS_STOPPING,
}


def mode_banner(mode: str, live_status: str) -> str:
    if mode == BENCHMARK_MODE:
        return "BENCHMARK"
    if mode == LIVE_MODE:
        return f"LIVE MICROPHONE · {live_status}"
    return "RECORDED DEMO"


def mode_description(mode: str) -> str:
    return MODE_DESCRIPTION.get(mode, DEMO_DESCRIPTION)


def visible_controls(
    mode: str,
    live_status: str,
    *,
    live_fallback_offered: bool = False,
) -> frozenset[str]:
    """Control ids that should be visible for this mode and live status."""

    if mode == BENCHMARK_MODE:
        return frozenset()
    if mode == DEMO_MODE:
        return DEMO_ONLY_CONTROLS | SHARED_AUDIO_CONTROLS
    if mode != LIVE_MODE:
        return frozenset()

    controls = set(SHARED_AUDIO_CONTROLS)
    if live_fallback_offered:
        controls.add("live_fallback")
    if live_status == LIVE_STATUS_IDLE and not live_fallback_offered:
        controls.add("start_live")
    elif live_status == LIVE_STATUS_STARTING:
        controls.add("live_starting")
    elif live_status in {LIVE_STATUS_LIVE, LIVE_STATUS_STOPPING}:
        controls.add("stop_live")
    elif live_status == LIVE_STATUS_ERROR:
        controls.add("recover_live")
    return frozenset(controls)


def audio_selectors_enabled(
    mode: str,
    live_status: str,
    *,
    devices_locked: bool,
) -> bool:
    if mode not in {DEMO_MODE, LIVE_MODE}:
        return False
    if devices_locked:
        return False
    if mode == LIVE_MODE and live_status in _LIVE_SELECTOR_LOCK:
        return False
    return True


def stop_live_enabled(mode: str, live_status: str) -> bool:
    return mode == LIVE_MODE and live_status == LIVE_STATUS_LIVE


def activity_caption(
    mode: str,
    *,
    demo_status: str,
    demo_scenario: str,
    ab_mode: str,
    duration_s: float,
    live_status: str,
    overflows: int,
    overflows_measured: bool = False,
) -> str:
    if mode == DEMO_MODE:
        listening = "B Enhanced" if ab_mode == "enhanced" else "A Raw"
        return (
            f"{demo_status}   ·   {demo_scenario}   ·   {listening}"
            f"   ·   {duration_s:.1f} s"
        )
    if mode == LIVE_MODE:
        overflow_text = str(overflows) if overflows_measured else "—"
        return f"LIVE   ·   {live_status}   ·   overflows {overflow_text}"
    return ""
