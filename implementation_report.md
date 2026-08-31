# DRDO-ANC Real-Time GUI: Implementation Report

This report summarizes the final architecture, design iterations, and completion status of the DRDO-ANC Real-Time Monitoring GUI. The objective was to build a robust, premium visualization dashboard for an active noise cancellation pipeline without blocking audio I/O.

## 1. Architectural Implementation

To satisfy the primary constraint ("The GUI may miss a visualization frame. The audio pipeline must never wait for the GUI"), we successfully implemented a decoupled, multi-threaded architecture using **PySide6** and **QML**.

### Core Components Developed:
- **`pipeline.py` (`StreamingPipeline`)**: Runs purely in a background daemon thread. We introduced a `telemetry_callback` mechanism that fires exactly when an audio chunk finishes processing. It passes the raw input, processed output, and latency metrics out of the thread without blocking.
- **`app.py` & `run_live_gui.py`**: The main entry points. They initialize the PySide6 `QGuiApplication`, boot the QML engine, and spawn the `StreamingPipeline` concurrently.
- **`bridge.py` (`GUIBridge`)**: The core synchronization layer. 
  - Subclasses `QObject` and maintains a `QTimer` running at 60 FPS in the main thread.
  - Exposes QML `Property` fields (e.g., `inputPeakDb`, `processingTimeMs`).
- **`waveform.py` (`WaveformProcessor`)**: Ensures UI performance by performing peak-preserving downsampling on the 48kHz audio chunks down to a strict 500-point array before passing them to the QML Canvas.

## 2. Visual Design & UI Revamp

The user interface underwent a major aesthetic overhaul to meet "Premium UI" requirements, utilizing deep dark aesthetics and glassmorphism.

### Aesthetic Highlights (The "Dark Informative Telemetry" Theme):
- **Background & Panels**: The main window utilizes a deep radial gradient (Dark Navy to Pitch Black). The waveform and metrics containers are styled as translucent panels (`#08FFFFFF` background with subtle borders) mimicking a premium glassmorphic dashboard.
- **Live Oscilloscopes (`Waveform.qml`)**: The raw and enhanced audio waveforms are drawn using the HTML5 Canvas 2D API. The stroke utilizes a glowing cyan effect (`shadowBlur`), and a semi-transparent gradient fill is rendered beneath the waveform down to the center axis to emulate modern audio visualizers.
- **LED Volume Meters (`Metrics.qml`)**: Replaced flat rectangular meters with an advanced multi-stop gradient (Cyan -> Green -> Yellow -> Red) mapped over a masked container. The meters dynamically shrink and grow representing Peak and RMS accurately against the clipping threshold.
- **Sparkline Analytics (`Sparkline.qml`)**: System telemetry (Latency, Real-Time Factor, Buffer Saturation, Dropped Frames) is rendered as dynamic history sparklines with gradient fills, similar to high-end DevOps dashboards.

## 3. Dependency Management (Lazy Loading)

To ensure the GUI application boots instantly in production without waiting for heavy ML frameworks to initialize, the codebase implements strict **Lazy Loading**:
- `torch` and `deepfilternet` imports were removed from the global scope in `pipeline.py` and `run_live_gui.py`.
- They are only loaded dynamically when the audio model is explicitly engaged.
- Type hints use `from __future__ import annotations` and `TYPE_CHECKING`.
- This ensures the UI thread is immediately responsive and can perform hardware initialization before the heavy tensors block the CPU.

## 4. Conclusion

The DRDO-ANC Real-Time GUI is fully operational. It achieves true concurrent execution, preventing any graphical lag from interrupting the crucial Active Noise Cancellation audio loop, while delivering a state-of-the-art visual experience.
