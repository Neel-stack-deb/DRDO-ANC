# DRDO-ANC Real-Time GUI: Implementation Plan & Setup Guide

This document outlines the deployment plan, setup instructions, and process flow for the DRDO-ANC Real-Time GUI. It is designed to allow any team member to clone the repository and get the GUI running immediately.

## 1. Prerequisites & Dependencies

To run the GUI and the underlying audio pipeline, you must have **Python 3.11+** installed. The system requires the following core packages:
- `PySide6` (for the Qt/QML frontend)
- `sounddevice` (for live audio hardware I/O)
- `soundfile` (for audio I/O fallbacks)
- `numpy` & `torch` (for tensor processing and downsampling)
- `deepfilternet` (required for running the actual live Active Noise Cancellation model)

## 2. Setup Instructions

When cloning this repository for the first time, strictly follow this setup sequence:

1. **Clone the Repository**
   ```bash
   git clone <repository_url>
   cd DRDO-ANC
   ```

2. **Create a Virtual Environment**
   ```bash
   python -m venv .venv
   ```

3. **Activate the Virtual Environment**
   - On Windows: `.\.venv\Scripts\activate`
   - On Linux/Mac: `source .venv/bin/activate`

4. **Install Dependencies**
   ```bash
   pip install -e .
   pip install PySide6 sounddevice soundfile numpy torch
   # Note: To install deepfilternet, Rust/Cargo must be installed on your system.
   ```

## 3. Execution Commands

The master launcher for the application is `scripts/run_live_gui.py`. It bridges your hardware microphone, the DeepFilterNet3 processing engine, and the QML telemetry GUI.

- **Live AI Enhancement Mode (Production):**
  Runs the full DeepFilterNet3 model on your primary microphone in real-time and streams the telemetry to the GUI.
  ```bash
  python scripts/run_live_gui.py --model DeepFilterNet3
  ```

- **Pass-through Mode (Hardware Diagnostics):**
  Routes your microphone directly to your speaker, bypassing the AI models to test raw I/O latency and verify the GUI audio scopes.
  ```bash
  python scripts/run_live_gui.py --passthrough
  ```

## 4. Process Flow & Architecture Plan

1. **Audio Ingestion**: `sounddevice` captures audio at 48 kHz.
2. **Streaming Pipeline**: The `StreamingPipeline` runs in a **daemon background thread**, processing 480-sample chunks continuously. 
3. **Telemetry Callback**: Once a chunk is processed (either by the model or passed through), a non-blocking `telemetry_callback` is fired.
4. **GUI Bridge Sync**: The `GUIBridge` (running in the main thread) atomically receives the audio arrays, computes Peak/RMS, and applies envelope-preserving downsampling (to 500 points).
5. **QML Rendering**: The PySide6 engine's QTimer triggers a 60 FPS refresh, requesting the latest data from the bridge and drawing it to the native desktop window using hardware acceleration.

This plan guarantees that the **audio pipeline never waits for the GUI**. If the UI drops a frame, the audio stream remains perfectly stable.
