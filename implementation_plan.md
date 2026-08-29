# DRDO-ANC UI Redesign: Dark Informative Telemetry

This document outlines the proposed redesign of the real-time monitoring GUI for the DRDO-ANC system. Based on your latest feedback, we are pivoting to a "Dark Informative" layout. This design retains the strict flat minimalism of the previous iteration but inverses the colors (pure black background, white text, cyan accents) and dramatically increases the data density to resemble a professional engineering or F1 telemetry console.

## Target Design Aesthetic

I have generated a new mockup representing this highly informative, dark-mode concept. Key features include:
1. **Pitch Black Background**: Reduces eye strain in dark environments and makes the data pop.
2. **High Data Density**: We will add additional data streams, such as separating volume meters into Peak vs. RMS (currently just single levels), and adding "history sparklines" below the primary metrics (Processing Latency, Buffer, etc).
3. **Strict Flat Geometry**: Sharp 1px white/blue borders, tabular layouts, and micro-text labels for axes.

![Dark Informative Mockup](C:\Users\dabbe\.gemini\antigravity-ide\brain\e9b1eb05-7e05-4512-81a1-2624dbdd25a5\dark_informative_mockup_1788027484175.jpg)

## Open Questions

> [!WARNING]
> Please review and approve the following items before we execute the redesign:
> 1. **Visual Style**: Does this ultra-dense, black-background telemetry console match your vision for an "informative" UI?
> 2. **Telemetry Scope**: To populate this UI, I will need to extend the Python `AudioTelemetry` data structure in `telemetry.py` and `bridge.py` to calculate Peak vs RMS, and to track historical arrays (sparklines) of the last 100 frames for Processing Time, Buffer, Dropped, and RTF. Is it acceptable to add this lightweight tracking to the Python Qt Bridge layer?

## Proposed Implementation Changes

We will need to modify both the Python backend (to track history for sparklines) and the QML frontend.

### [MODIFY] `src/drdo_anc/gui/telemetry.py` & `src/drdo_anc/gui/bridge.py`
- Add historical tracking arrays (`collections.deque` of length 100) for `processing_time`, `buffer_fill`, `dropped_frames`, and `rtf`.
- Expose these arrays as QML Properties (Lists) via `Signal(list)`.

### [MODIFY] `src/drdo_anc/gui/qml/Main.qml`
- Change background to pure black `#000000`.
- Update text colors to pure white `#FFFFFF`.

### [MODIFY] `src/drdo_anc/gui/qml/Waveform.qml`
- Keep the flat canvas rendering, but add complex X/Y axis gridlines and micro-text (using QML `Text` positioned around the canvas).

### [NEW] `src/drdo_anc/gui/qml/Sparkline.qml`
- A new reusable Canvas component that draws a miniature history line graph for the bottom metrics panel.

### [MODIFY] `src/drdo_anc/gui/qml/Metrics.qml`
- Completely overhaul the layout to a dense, multi-column grid.
- Integrate the new `Sparkline` component under each large numeric metric.
- Split the flat volume bars into dual Peak/RMS bars.

## Verification Plan

### Manual Verification
1. Kill the existing GUI process.
2. Run `python scripts/run_live_gui.py`.
3. Verify the historical sparklines are drawing and animating correctly over time.
4. Verify CPU usage remains stable despite the added rendering complexity of the sparklines.
