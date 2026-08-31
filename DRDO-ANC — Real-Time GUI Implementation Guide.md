# DRDO-ANC — Real-Time GUI Implementation Guide

## 1. Your Mission

Build the real-time monitoring GUI for the DRDO-ANC live audio system using:

**Qt 6 + QML**

The GUI should visualize the live system without becoming part of the audio-critical processing path.

The existing system already provides:

```text
Microphone
    ↓
AudioInput
    ↓
StreamingPipeline
    ↓
Enhancer
    ↓
AudioOutput
    ↓
Speaker
```

Your GUI should observe this pipeline:

```text
                         ┌───────────────┐
                         │               │
Microphone → AudioInput → StreamingPipeline → Enhancer → AudioOutput
                         │
                         │ telemetry
                         ▼
                    Qt/QML GUI
```

### Core rule

> **The GUI may miss a visualization frame. The audio pipeline must never wait for the GUI.**

Do not put GUI operations, rendering, locks, or blocking IPC calls inside the real-time audio processing path.

---

# 2. First Read the Repository

Before writing code, inspect:

```text
docs/PROJECT_STATUS.md

src/drdo_anc/audio/live/interfaces.py
src/drdo_anc/audio/live/fake.py
src/drdo_anc/audio/live/sounddevice_backend.py
src/drdo_anc/audio/live/pipeline.py

src/drdo_anc/enhancement/base.py
src/drdo_anc/enhancement/registry.py
src/drdo_anc/enhancement/deepfilternet.py

scripts/run_live_enhancement.py
scripts/test_live_audio.py
```

Understand the existing live architecture before modifying it.

Do NOT recreate:

- AudioInput
- AudioOutput
- StreamingPipeline
- StreamingBuffer
- Enhancer
- model registry
- DF3 streaming implementation

Those already exist.

---

# 3. Technology Choice

Use:

```text
Qt 6
QML
Python Qt binding
```

Prefer **PySide6** unless the repository/project owner explicitly chooses another Qt binding.

The initial implementation should remain Python-based because the current live audio pipeline is Python-based.

Do not rewrite the audio pipeline in C++ just to build the GUI.

The architecture should allow that migration later if embedded deployment requires it.

---

# 4. Target GUI

The first version should be a simple engineering console.

Conceptually:

```text
┌────────────────────────────────────────────────────────────┐
│ DRDO-ANC                                      ● LIVE       │
├────────────────────────────────────────────────────────────┤
│                                                            │
│ INPUT WAVEFORM                                             │
│ ───╱╲────╱╲────╱╲─────╱╲──────╱╲────                     │
│                                                            │
├────────────────────────────────────────────────────────────┤
│                                                            │
│ ENHANCED WAVEFORM                                          │
│ ─────╱╲────╱╲────╱╲────────╱╲────                         │
│                                                            │
├────────────────────────────────────────────────────────────┤
│                                                            │
│ INPUT LEVEL        OUTPUT LEVEL       PROCESSING            │
│ ███████░░░         █████░░░░░         4.2 ms               │
│                                                            │
│ BUFFER             DROPPED             RTF                  │
│ 12%                0                   0.42x                │
│                                                            │
├────────────────────────────────────────────────────────────┤
│ Model: DeepFilterNet3        Sample Rate: 48 kHz           │
└────────────────────────────────────────────────────────────┘
```

Do not build a huge dashboard initially.

---

# 5. Architecture

Separate the application into:

```text
src/drdo_anc/gui/
    __init__.py
    app.py
    telemetry.py
    waveform.py
    bridge.py
    qml/
        Main.qml
        Waveform.qml
        Metrics.qml
```

The exact structure can change if the existing repository conventions suggest a better location.

The important separation is:

```text
Audio system
    ↓
Telemetry / waveform snapshot
    ↓
Qt bridge
    ↓
QML
    ↓
GPU rendering
```

---

# 6. Do Not Put QML in the Audio Callback

This is extremely important.

Never do:

```python
def audio_callback(chunk):
    update_qml(chunk)
    render_waveform()
    ...
```

The audio callback must remain lightweight.

Instead:

```text
Audio callback
    ↓
audio processing
    ↓
non-blocking telemetry publication
    ↓
return immediately
```

The GUI independently consumes the latest available data.

---

# 7. Telemetry Design

Create a small telemetry representation.

Possible fields:

```python
@dataclass
class AudioTelemetry:
    timestamp: float

    input_level: float
    output_level: float

    input_peak: float
    output_peak: float

    processing_time_ms: float
    realtime_factor: float

    buffer_fill: float
    dropped_frames: int
```

Do not blindly copy this structure if the live pipeline already exposes equivalent information.

Inspect the existing implementation first.

The telemetry object should contain **small scalar values** wherever possible.

---

# 8. Waveform Data

The GUI does NOT need every 48,000 audio samples per second.

For example:

```text
Audio:
48,000 samples/sec

GUI:
60 frames/sec
```

The visualization can use a reduced representation.

For example:

```text
audio samples
     ↓
peak/RMS reduction
     ↓
~1000 waveform points
     ↓
GUI
```

The exact reduction strategy should be chosen based on measurements.

The important principle is:

> Preserve the audio at full resolution internally; reduce only the data sent to the visualization.

---

# 9. Waveform Rendering

Use Qt Quick/QML for the GUI.

The waveform should eventually be GPU-rendered rather than repeatedly constructing large Python/QML object trees.

Avoid approaches such as:

```text
one QML Rectangle per sample
```

or:

```text
thousands of QML objects recreated every frame
```

Instead aim for:

```text
waveform data
      ↓
single rendering item
      ↓
GPU
```

A custom Qt Quick rendering item can be introduced if necessary.

Start simple and profile before optimizing.

Do not prematurely write complex OpenGL/Vulkan code.

---

# 10. Two Waveforms

The initial GUI should show:

```text
Input waveform
```

and:

```text
Enhanced waveform
```

These should be captured from the existing pipeline.

Do not create a second microphone capture path just for visualization.

The data should originate from the same live stream that feeds the enhancer.

---

# 11. Ring Buffer / Latest-Snapshot Principle

The GUI should not accumulate unlimited audio data.

Use a bounded buffer.

Conceptually:

```text
Audio stream
     ↓
bounded waveform buffer
     ↓
GUI reads latest window
```

For visualization, old frames can be discarded.

There is no reason for the GUI to render audio from 30 seconds ago.

A useful mental model is:

```text
Audio: lossless / must not drop
GUI: lossy visualization / may drop old frames
```

---

# 12. Threading

At minimum think in terms of three logical activities:

```text
Audio thread
    ↓
Real-time processing

GUI thread
    ↓
Qt/QML rendering

Telemetry transfer
    ↓
Non-blocking/bounded communication
```

Do not make the audio thread wait for the GUI.

Avoid:

```python
lock.acquire()
GUI.update()
lock.release()
```

inside the real-time audio path.

Prefer a bounded/latest-value approach.

If synchronization is required, keep the critical section extremely small and prove through profiling that it doesn't interfere with audio.

---

# 13. GUI Update Frequency

Do not update the GUI every audio sample.

A reasonable first target is:

```text
60 FPS
```

Later test:

```text
120 FPS
```

if the hardware/display warrants it.

The audio system may run at:

```text
48,000 samples/sec
```

while the GUI runs at:

```text
60–120 visual updates/sec
```

These are intentionally different rates.

---

# 14. Metrics to Display

Initial version:

```text
Input level
Output level
Input peak
Output peak
Processing time
RTF
Buffer fill
Dropped frames
Model name
Sample rate
Live/offline state
```

Do not invent objective SNR/STOI/PESQ numbers from a live microphone stream unless there is a valid reference signal.

Remember:

```text
Offline benchmark:
clean reference exists
→ objective metrics possible

Live microphone:
clean reference normally doesn't exist
→ objective metrics are generally unavailable
```

The GUI must not pretend otherwise.

---

# 15. Model Information

The model should come from the existing model registry.

For example:

```text
DeepFilterNet3
```

Do not hardcode the GUI to DF3.

The GUI should eventually display:

```text
Model: DeepFilterNet3
```

but if the live CLI starts:

```text
MyFineTunedModel
```

the GUI should be able to display:

```text
Model: MyFineTunedModel
```

without changing the GUI architecture.

---

# 16. Start With Fake Data

Before connecting the real microphone, make the GUI work with:

```text
FakeAudioInput
FakeAudioOutput
```

which already exist in:

```text
src/drdo_anc/audio/live/fake.py
```

Use generated test waveforms:

```text
sine wave
speech-like envelope
noise
changing amplitude
```

This lets you develop the GUI without requiring hardware.

---

# 17. Development Stages

## Stage 1 — Static GUI

Build:

```text
window
waveform area
metrics
model information
status
```

Use fake data.

---

## Stage 2 — Animated fake waveform

Make:

```text
Input waveform
Enhanced waveform
```

move continuously.

Target:

```text
60 FPS
```

Measure CPU usage.

---

## Stage 3 — Connect real telemetry

Connect:

```text
StreamingPipeline
        ↓
telemetry
        ↓
Qt bridge
        ↓
QML
```

The GUI should now show real:

```text
processing time
RTF
buffer status
```

---

## Stage 4 — Connect real waveform

Run:

```text
Microphone
    ↓
AudioInput
    ↓
StreamingPipeline
    ↓
DF3
    ↓
AudioOutput
```

and visualize the actual input/output stream.

---

## Stage 5 — Stress test

Run continuously for:

```text
5 minutes
10 minutes
30 minutes
```

Look for:

- audio glitches
- dropped frames
- memory growth
- GUI freezes
- waveform lag
- CPU spikes
- synchronization problems

---

# 18. Performance Requirements

The GUI must not compromise the audio pipeline.

The most important metric is therefore not:

> "Does the GUI render at 120 FPS?"

It is:

> "Does adding the GUI change the audio pipeline's real-time behavior?"

Compare:

```text
WITHOUT GUI
    ↓
latency
RTF
dropped frames
buffer behavior
```

against:

```text
WITH GUI
    ↓
latency
RTF
dropped frames
buffer behavior
```

The GUI is successful only if the audio path remains healthy.

---

# 19. Benchmark GUI Overhead

Add an optional mode:

```bash
--no-gui
```

and compare it against:

```bash
--gui
```

Eventually record:

```text
                 No GUI       GUI
-------------------------------------
CPU
Memory
RTF
processing time
dropped frames
buffer underruns
```

This is much more useful than simply saying "the GUI is fast."

---

# 20. Live Pipeline Integration

The desired architecture is:

```text
                   ┌──────────────┐
                   │ Microphone   │
                   └──────┬───────┘
                          ↓
                   ┌──────────────┐
                   │ AudioInput   │
                   └──────┬───────┘
                          ↓
                 ┌─────────────────┐
                 │ Streaming       │
                 │ Pipeline        │
                 └──────┬──────────┘
                        │
              ┌─────────┴─────────┐
              ↓                   ↓
         Enhancer             Telemetry
              ↓                   ↓
         AudioOutput          Qt Bridge
              ↓                   ↓
           Speaker               QML
```

The telemetry branch must be observational.

It must not control the audio branch.

---

# 21. Error Handling

The GUI should clearly show:

```text
● LIVE
```

or:

```text
● STOPPED
```

or:

```text
● ERROR
```

Potential errors:

```text
microphone unavailable
speaker unavailable
model failed to load
audio stream stopped
buffer overflow
```

Do not silently continue with invalid audio.

---

# 22. Device Selection

Do not implement a second device-discovery system.

The existing live CLI already supports device selection.

Reuse the existing audio backend/device APIs.

The GUI may eventually expose:

```text
Input Device
Output Device
Sample Rate
Chunk Size
Model
```

but initially keep configuration simple.

---

# 23. What NOT to Build

Do not build yet:

```text
noise classifier
NLMS
TensorRT
Jetson-specific GUI
cloud backend
database
web server
remote dashboard
multi-user system
```

Also do not rewrite the existing Python live audio architecture.

The first goal is:

```text
MIC → DF3 → SPEAKER
             +
          GUI monitor
```

---

# 24. Recommended First Repository Changes

Start with something approximately like:

```text
src/drdo_anc/gui/
    __init__.py
    app.py
    bridge.py
    telemetry.py
    waveform.py

    qml/
        Main.qml
        Waveform.qml
        Metrics.qml

scripts/
    run_live_gui.py

tests/
    ...
```

Adapt the exact locations to the existing repository conventions.

---

# 25. Testing

GUI-specific tests should not require a microphone.

At minimum test:

```text
[ ] GUI starts
[ ] Fake telemetry reaches GUI
[ ] Fake waveform renders
[ ] Telemetry updates
[ ] Bounded buffers don't grow indefinitely
[ ] GUI handles stream stop
[ ] GUI handles audio error
```

Then separately run hardware tests.

---

# 26. Definition of Done — Version 1

The first GUI milestone is complete when:

```text
[ ] Qt 6/QML application starts
[ ] Fake audio can drive the waveform
[ ] Input waveform is displayed
[ ] Enhanced waveform is displayed
[ ] GUI updates smoothly
[ ] Telemetry is displayed
[ ] No unbounded waveform memory growth
[ ] GUI does not block audio processing
[ ] Real microphone can feed the existing pipeline
[ ] DF3 output can be visualized
[ ] Audio remains stable with GUI enabled
[ ] 10+ minute stability test passes
```

---

# 27. Important Architectural Principle

Think of the system as two paths:

```text
                  REAL-TIME PATH
                       │
Mic → Capture → AI/DSP → Output → Speaker
                       │
                       │
                  OBSERVATION
                       │
                       ▼
                  GUI / QML
```

The GUI is **not** part of the real-time audio path.

This distinction will matter enormously when the project moves to Jetson/embedded hardware.

---

# 28. Future Direction

The eventual system can evolve toward:

```text
                    Jetson
                      │
        ┌─────────────┴─────────────┐
        │                           │
    Native audio                Qt/QML
        │                           │
    DSP / AI                   GPU rendering
        │                           │
        └────────── telemetry ──────┘
```

The GUI should therefore be designed as a visualization/monitoring layer, not as the owner of the audio pipeline.

---

# 29. Your First Task

Do these in order:

```text
1. Inspect existing live audio implementation
2. Set up Qt 6 + PySide6
3. Create minimal QML window
4. Create fake telemetry source
5. Render fake input/output waveforms
6. Add real-time metrics
7. Profile GUI CPU/memory usage
8. Connect to real StreamingPipeline
9. Run Microphone → DF3 → Speaker
10. Verify GUI does not affect audio stability
```

Do not skip directly to a complex polished dashboard.

The first objective is:

**A reliable low-latency engineering GUI sitting safely beside the real-time audio pipeline.**