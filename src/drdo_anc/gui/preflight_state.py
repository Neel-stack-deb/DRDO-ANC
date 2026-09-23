"""Demo preflight readiness states (separate from live audio state machine)."""

from __future__ import annotations

PREFLIGHT_NOT_CHECKED = "NOT_CHECKED"
PREFLIGHT_CHECKING = "CHECKING"
PREFLIGHT_READY = "READY"
PREFLIGHT_WARNING = "WARNING"
PREFLIGHT_FAILED = "FAILED"
