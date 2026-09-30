# DRDO-ANC

## AI/ML-Enabled Adaptive Noise Cancellation & Speech Enhancement for Defence Communication

A real-time speech-enhancement prototype developed for SIH 2026 --- DRDO
Problem Statement 26052.

### Overview

DRDO-ANC is designed to make speech clearer in difficult acoustic
environments by combining AI-based speech enhancement, streaming audio
processing, objective evaluation, and adaptive signal-processing
components.

The practical pipeline is:

``` text
Microphone
  -> Streaming capture / preprocessing
  -> DeepFilterNet3-Finetuned
  -> Enhanced speech
  -> A/B output routing
  -> Headphones / speaker
```

The target hybrid architecture is:

``` text
Microphone
  -> Preprocessing
  -> Fine-tuned AI enhancer
  -> Residual noise
  -> Adaptive NLMS/LMS
  -> Post-processing
  -> Communication output
```

> The system suppresses noise in the captured communication signal. It
> does not physically cancel the acoustic pressure wave of a gunshot or
> explosion.

## Current status

The project currently includes:

-   Pretrained DeepFilterNet3
-   Fine-tuned DeepFilterNet3
-   Model registry and reusable inference
-   Offline and streaming evaluation
-   PC live microphone-to-speaker enhancement
-   Live A/B switching between RAW and ENHANCED output
-   Defence-noise benchmark cases
-   Objective metrics
-   Recording-disjoint evaluation
-   Real-time soak testing
-   PySide6/QML GUI
-   Demo mode with recorded scenarios
-   Demo preflight and emergency fallback
-   Benchmark/results screen
-   Role-aware input/output device selection
-   Standalone NLMS validation
-   Dual-microphone architecture experiments
-   Automated regression/GUI tests

The current verified demonstration path is PC-based. Jetson deployment
remains a future validation target.

## Problem targets

The SIH problem statement specifies:

  Requirement                          Target
  -------------------------------- ----------
  SNR                                \> 15 dB
  STOI                                \> 0.85
  PESQ                                 \> 2.5
  Embedded real-time performance     Required

These are treated as engineering targets rather than assumed
achievements.

## Benchmark results

### Development evaluation

  Metric     Pretrained     Fine-tuned
  -------- ------------ --------------
  SI-SDR       12.71 dB   **14.95 dB**
  STOI            0.667      **0.708**
  PESQ            1.850      **2.119**
  SNR          12.30 dB   **15.01 dB**

The fine-tuned model improved paired SI-SDR by **2.24 dB**. Across 120
paired development evaluations, 118 improved and 2 degraded.

The development aggregate reached **15.01 dB measured SNR**, crossing
the SIH 15 dB SNR target. STOI and PESQ remain below their specified
targets.

### Recording-disjoint evaluation

  Metric     Pretrained     Fine-tuned
  -------- ------------ --------------
  SI-SDR       12.29 dB   **15.47 dB**
  STOI            0.696      **0.728**
  PESQ            1.879      **2.262**
  SNR          12.31 dB   **15.47 dB**

Paired SI-SDR improvement: **+3.18 dB**.

The recording-disjoint evaluation is not described as a verified
training holdout because the project's training-holdout status is
currently unverified.

## Benchmark design

The development benchmark contains:

-   10 clean speakers
-   3 noise categories: UAV/drone, impulsive/firearm, vehicle/engine
-   2 SNR conditions: 0 dB and +5 dB
-   60 deterministic cases
-   120 paired evaluations
-   Fixed evaluation rules and seed

## Real-time system

DeepFilterNet3 currently operates at:

-   48 kHz
-   480 samples per model frame
-   10 ms frame duration
-   Buffered streaming inference
-   Tail flushing

The PC live pipeline supports model selection, input/output device
selection, start/stop, A/B routing, waveform telemetry and recovery
behavior.

Fine-tuned live smoke/soak tests included 30-second and 5-minute runs
with 0 input overflows in the recorded tests. Wall-time RTF was
approximately 0.960 and 0.996 respectively.

These are PC measurements and are not Jetson performance claims.

## GUI

The PySide6/QML application has three main modes:

### Demo

-   Recorded WAV scenarios
-   Scenario selection
-   Play/pause/stop
-   RAW/ENHANCED A/B routing
-   Fine-tuned model
-   Preflight checks
-   Reset/fallback behavior

### Live

-   Input device selection
-   Output device selection
-   Model selection
-   Start/stop
-   A --- RAW
-   B --- ENHANCED
-   Input and enhanced waveforms
-   Runtime telemetry
-   Device refresh
-   Error recovery

### Benchmark

-   Development results
-   Recording-disjoint results
-   Metric comparisons
-   SI-SDR comparison
-   SIH target context
-   Holdout-status disclaimer

## Adaptive DSP

The project has explored spectral subtraction, Wiener filtering, LMS and
NLMS.

NLMS has been independently validated with automated tests.

The intended hybrid path is:

``` text
AI enhancement
      ↓
Residual noise
      ↓
Adaptive NLMS refinement
```

The integrated AI + NLMS live path should only be presented as a
validated capability after end-to-end measurement.

## Noise classification

A first noise-aware classifier was rejected because its performance was
not adequate.

A second ExtraTrees classifier reached approximately:

-   Validation macro F1: 0.867
-   Test accuracy: 0.895
-   Test macro F1: 0.863

It remains an experimental component rather than a required live
dependency.

A noise-aware adaptive enhancement experiment was also rejected after
reducing average SI-SDR relative to the baseline enhancer.

## Testing

The project has automated tests for audio, streaming, model registry,
benchmarking, GUI behavior, device discovery, demo mode, live control,
preflight and benchmark display.

At the latest documented integration stage:

**32 `scripts/test_*.py` scripts passed with 0 failures.**

## Hardware and deployment

The current live demonstration uses a Windows PC and WASAPI audio
devices.

The application discovers devices by their roles rather than relying
permanently on numeric PortAudio indexes.

The intended embedded deployment path is:

``` text
PyTorch
  -> ONNX
  -> TensorRT
  -> FP16 / possibly INT8
  -> Jetson
```

Jetson real-time performance is not currently a measured result.

## Dual microphone work

A dual-microphone architecture was explored for future
reference-channel/adaptive filtering.

Independent USB microphone experiments showed synchronization and
clock-drift problems. A synchronized multi-channel ADC/interface is
therefore the more robust future direction.

## Engineering principles

1.  Build the simplest working system first.
2.  Reuse strong existing models.
3.  Make defence-specific data and evaluation a major contribution.
4.  Prove improvements with measurements.
5.  Prefer low-latency streaming approaches.
6.  Add complexity only when it improves measured performance.
7.  Never let the dashboard hide bad audio.
8.  Never claim unmeasured performance.
9.  Keep the architecture modular.
10. Optimize for the actual edge hardware.
11. Test before adding complexity.

## Current limitations

-   Jetson real-time performance is not yet verified.
-   STOI remains below the SIH target.
-   PESQ remains below the SIH target.
-   Integrated AI + NLMS live performance still requires end-to-end
    validation.
-   Independent dual microphones are not sufficiently synchronized for
    robust reference-channel operation.
-   Current benchmark results are controlled evaluations, not
    field-performance claims.
-   The system suppresses noise in the captured signal rather than
    physically cancelling acoustic pressure.

## Roadmap

### Near term

-   Complete and validate AI + NLMS integration
-   Expand impulsive and non-stationary noise testing
-   Improve STOI and PESQ
-   Expand defence-specific recordings
-   Perform stronger ablation studies
-   Improve synchronized multi-microphone support

### Edge deployment

-   ONNX validation
-   TensorRT conversion
-   FP16 optimization
-   Jetson integration
-   End-to-end latency and RTF measurement

### Longer term

-   Adaptive noise classification
-   Context-aware enhancement
-   Beamforming
-   Direction-of-arrival estimation
-   Model selection
-   Distillation
-   INT8 optimization
-   Complex-domain enhancement
-   Target-speaker preservation
-   Communication-system integration

## Running the project

From the repository root:

``` powershell
cd C:\Projects\DRDO-ANC
$env:PYTHONPATH="C:\Projects\DRDO-ANC\src"
```

List devices:

``` powershell
python scripts/run_live_gui.py --list-devices
```

Start the GUI:

``` powershell
python scripts/run_live_gui.py
```

Start live mode with explicit devices:

``` powershell
python scripts/run_live_gui.py --input-device <INPUT_ID> --output-device <OUTPUT_ID>
```

Run the live CLI pipeline:

``` powershell
python scripts/run_live_enhancement.py --model DeepFilterNet3-Finetuned --input-device <INPUT_ID> --output-device <OUTPUT_ID>
```

Run the project's test suite using the repository's current test runner.

## Demo story

A strong presentation flow is:

``` text
Problem
  -> Hear the noisy signal
  -> Explain the architecture
  -> Explain supervised fine-tuning
  -> Show measured results
  -> Compare with SIH targets
  -> Run live microphone demo
  -> Switch RAW ↔ ENHANCED
  -> Explain real-time engineering
  -> Show limitations and future direction
```

The core engineering story is:

**hear it -\> measure it -\> run it live.**

## Project positioning

DRDO-ANC is best described as:

> A real-time AI-based speech-enhancement and adaptive noise-suppression
> prototype for defence communication.

It is a research/prototype system, not a deployed military communication
product.

The current project demonstrates a working PC real-time pipeline and
measurable improvement from supervised fine-tuning, while embedded
deployment and several target metrics remain active engineering goals.
