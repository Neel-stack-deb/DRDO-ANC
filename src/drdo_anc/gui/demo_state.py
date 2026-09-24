"""Demo Mode v2 lifecycle status labels exposed to the GUI."""

from __future__ import annotations

DEMO_STATUS_IDLE = "IDLE"
DEMO_STATUS_LOADING = "LOADING"
DEMO_STATUS_PROCESSING = "PROCESSING"
DEMO_STATUS_PLAYING_RAW = "PLAYING RAW"
DEMO_STATUS_PLAYING_ENHANCED = "PLAYING ENHANCED"
DEMO_STATUS_STOPPED = "STOPPED"
DEMO_STATUS_ERROR = "ERROR"


def playing_status_for_ab_mode(ab_mode: str) -> str:
    if ab_mode == "raw":
        return DEMO_STATUS_PLAYING_RAW
    return DEMO_STATUS_PLAYING_ENHANCED
