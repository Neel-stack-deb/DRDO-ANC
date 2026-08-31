"""Shared terminal UX helpers for experimental microphone capture scripts."""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from typing import TextIO

COUNTDOWN_SECONDS = 3
PROGRESS_BAR_WIDTH = 12


def format_clock_duration(seconds: float) -> str:
    """Format seconds as ``MM:SS.s`` for terminal progress."""

    seconds = max(0.0, float(seconds))
    minutes = int(seconds // 60)
    remainder = seconds - (minutes * 60)
    return f"{minutes:02d}:{remainder:04.1f}"


def render_progress_bar(ratio: float, width: int = PROGRESS_BAR_WIDTH) -> str:
    ratio = min(1.0, max(0.0, float(ratio)))
    filled = int(round(ratio * width))
    return ("█" * filled) + ("░" * (width - filled))


def run_countdown(
    *,
    seconds: int = COUNTDOWN_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
    write: Callable[..., None] = print,
) -> None:
    write("GET READY")
    for remaining in range(seconds, 0, -1):
        write(f"Capture starts in: {remaining}...")
        sleep(1.0)
    write("● RECORDING")


def update_recording_progress(
    *,
    elapsed_s: float,
    total_s: float,
    stream: TextIO | None = None,
) -> None:
    output = stream or sys.stdout
    remaining_s = max(0.0, total_s - elapsed_s)
    ratio = elapsed_s / total_s if total_s > 0 else 1.0
    line = (
        f"\r● RECORDING  "
        f"[{format_clock_duration(elapsed_s)} / {format_clock_duration(total_s)}]  "
        f"{render_progress_bar(ratio)}  "
        f"remaining {format_clock_duration(remaining_s)}"
    )
    output.write(line)
    output.flush()


def finish_progress_line(stream: TextIO | None = None) -> None:
    output = stream or sys.stdout
    output.write("\n")
    output.flush()


def emit_capture_complete(write: Callable[..., None] = print) -> None:
    write("✓ CAPTURE COMPLETE")


def emit_analysis_start(
    write: Callable[..., None] = print,
    *,
    message: str = "Analyzing channels...",
) -> None:
    write(message)


def emit_analysis_complete(write: Callable[..., None] = print) -> None:
    write("✓ ANALYSIS COMPLETE")


def emit_capture_failed(
    error: BaseException,
    *,
    write: Callable[..., None] = print,
) -> None:
    write("✗ CAPTURE FAILED")
    write(str(error))
