"""Synthetic and hardware tests for dual-microphone reference capture."""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TextIO

import numpy as np
import soundfile as sf

from drdo_anc.audio import save_mono_wav
from drdo_anc.audio.live import (
    ChannelRouter,
    DualMicResidualFrame,
    FakeMultiChannelAudioInput,
    MultiMicConfig,
    RoutedPrimaryAudioInput,
    analyze_channel_pair,
    format_device_listing,
    record_dual_microphone,
)
from drdo_anc.audio.live import sounddevice_multimic as sounddevice_multimic_module
from drdo_anc.audio.live.capture_ux import (
    COUNTDOWN_SECONDS,
    emit_analysis_complete,
    emit_analysis_start,
    emit_capture_complete,
    emit_capture_failed,
    finish_progress_line,
    run_countdown,
    update_recording_progress,
)
from drdo_anc.audio.live.sounddevice_multimic import DualMicCaptureResult


DEFAULT_SAMPLE_RATE = 48_000
DEFAULT_OUTPUT_DIR = Path("data") / "dual_mic_recordings"
CAPTURE_CONDITIONS = (
    "speech_only",
    "stationary_noise",
    "impulsive_noise",
)


def _synthetic_stereo(
    length: int,
    *,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    primary_gain: float = 0.8,
    reference_gain: float = 0.5,
    reference_delay: int = 12,
    speech_on_primary_only: bool = True,
) -> np.ndarray:
    time = np.arange(length, dtype=np.float32) / np.float32(sample_rate)
    speech = np.sin(
        np.float32(2.0 * np.pi * 220.0) * time,
        dtype=np.float32,
    )
    noise = np.sin(
        np.float32(2.0 * np.pi * 73.0) * time + np.float32(0.3),
        dtype=np.float32,
    )

    primary = primary_gain * noise
    if speech_on_primary_only:
        primary = primary + 0.35 * speech

    reference = np.zeros(length, dtype=np.float32)
    if reference_delay < length:
        reference[reference_delay:] = reference_gain * noise[:-reference_delay]

    return np.column_stack([primary, reference]).astype(np.float32)


def test_configuration_validation() -> None:
    MultiMicConfig(
        sample_rate=48_000,
        input_channels=2,
        primary_channel=0,
        reference_channel=1,
    )

    try:
        MultiMicConfig(
            sample_rate=48_000,
            input_channels=2,
            primary_channel=0,
            reference_channel=0,
        )
    except ValueError as exc:
        assert "must differ" in str(exc)
    else:
        raise AssertionError("Expected duplicate channel indices to fail.")

    try:
        MultiMicConfig(
            sample_rate=0,
            input_channels=2,
            primary_channel=0,
            reference_channel=1,
        )
    except ValueError as exc:
        assert "sample_rate" in str(exc)
    else:
        raise AssertionError("Expected invalid sample rate to fail.")


def test_channel_routing_extracts_configured_channels() -> None:
    stereo = _synthetic_stereo(1_024, reference_delay=8)
    config = MultiMicConfig(
        primary_channel=1,
        reference_channel=0,
        input_channels=2,
    )
    router = ChannelRouter(config)

    primary, reference = router.route(stereo)

    np.testing.assert_allclose(primary, stereo[:, 1])
    np.testing.assert_allclose(reference, stereo[:, 0])


def test_channel_routing_preserves_length() -> None:
    stereo = _synthetic_stereo(777)
    router = ChannelRouter(MultiMicConfig())

    primary, reference = router.route(stereo)

    assert primary.shape == (777,)
    assert reference.shape == (777,)
    assert primary.dtype == np.float32
    assert reference.dtype == np.float32


def test_fake_multichannel_input_streaming() -> None:
    stereo = _synthetic_stereo(2_048)
    chunks = [
        stereo[:300],
        stereo[300:900],
        stereo[900:],
    ]

    source = FakeMultiChannelAudioInput(
        chunks,
        sample_rate=DEFAULT_SAMPLE_RATE,
        channel_count=2,
    )
    router = ChannelRouter(MultiMicConfig())
    primary_input = RoutedPrimaryAudioInput(source, router)

    parts = [
        primary_input.read(512),
        primary_input.read(512),
        primary_input.read(512),
        primary_input.read(512),
    ]

    expected_primary, _ = router.route(stereo)
    actual_primary = np.concatenate([part for part in parts if part.size > 0])

    np.testing.assert_allclose(actual_primary, expected_primary)


def test_sample_rate_validation_on_adapter() -> None:
    stereo = _synthetic_stereo(128)
    source = FakeMultiChannelAudioInput(
        [stereo],
        sample_rate=44_100,
        channel_count=2,
    )
    router = ChannelRouter(MultiMicConfig(sample_rate=48_000))

    try:
        RoutedPrimaryAudioInput(source, router)
    except ValueError as exc:
        assert "sample rate" in str(exc)
    else:
        raise AssertionError("Expected sample-rate mismatch to fail.")


def test_correlation_and_delay_on_synthetic_pair() -> None:
    stereo = _synthetic_stereo(4_096, reference_delay=20)
    config = MultiMicConfig(sample_rate=DEFAULT_SAMPLE_RATE)
    router = ChannelRouter(config)
    primary, reference = router.route(stereo)

    analysis = analyze_channel_pair(primary, reference, config)

    assert analysis.num_samples == 4_096
    assert analysis.sample_rate == DEFAULT_SAMPLE_RATE
    assert abs(analysis.correlation) > 0.5
    # reference is a delayed copy of the noise component, so it lags primary.
    assert abs(analysis.relative_delay_samples + 20) <= 2


def test_dual_mic_residual_frame_validation() -> None:
    primary = np.ones(64, dtype=np.float32)
    reference = np.ones(64, dtype=np.float32) * 0.5

    frame = DualMicResidualFrame(
        enhanced_primary=primary,
        reference=reference,
    )

    assert frame.enhanced_primary.shape == (64,)

    try:
        DualMicResidualFrame(
            enhanced_primary=primary,
            reference=primary[:32],
        )
    except ValueError as exc:
        assert "same length" in str(exc)
    else:
        raise AssertionError("Expected length mismatch to fail.")


def test_analysis_reports_rms_and_peak() -> None:
    primary = np.array([0.0, 1.0, -1.0, 0.0], dtype=np.float32)
    reference = np.array([0.5, 0.5, 0.5, 0.5], dtype=np.float32)
    config = MultiMicConfig(sample_rate=1_000)

    analysis = analyze_channel_pair(primary, reference, config)

    assert analysis.primary_peak == 1.0
    assert analysis.reference_peak == 0.5
    assert analysis.primary_rms > 0.0
    assert analysis.reference_rms > 0.0


def test_non_multichannel_routing_rejected() -> None:
    router = ChannelRouter(MultiMicConfig())

    try:
        router.route(np.ones(16, dtype=np.float32))
    except ValueError as exc:
        assert "[T, C]" in str(exc)
    else:
        raise AssertionError("Expected non-multichannel input to fail.")


def _make_capture_result(
    *,
    config: MultiMicConfig,
    num_samples: int,
) -> DualMicCaptureResult:
    stereo = _synthetic_stereo(num_samples)
    router = ChannelRouter(config)
    primary, reference = router.route(stereo)

    return DualMicCaptureResult(
        config=config,
        multichannel=stereo,
        primary=primary,
        reference=reference,
        analysis=None,
        input_overflows=0,
        elapsed_s=0.1,
    )


def test_countdown_does_not_extend_capture_duration() -> None:
    config = MultiMicConfig(sample_rate=1_000)
    requested_duration = 10.0
    expected_samples = int(config.sample_rate * requested_duration)
    sleep_calls: list[float] = []
    recorded: list[tuple[float, bool]] = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    def fake_record(
        capture_config: MultiMicConfig,
        duration_s: float,
        **kwargs: object,
    ) -> DualMicCaptureResult:
        recorded.append((duration_s, kwargs.get("defer_analysis", False)))
        return _make_capture_result(
            config=capture_config,
            num_samples=int(capture_config.sample_rate * duration_s),
        )

    output = io.StringIO()

    def capture_write(message: str = "", **_: object) -> None:
        output.write(f"{message}\n")

    run_hardware_capture(
        config=config,
        duration_s=requested_duration,
        output_dir=Path("data/test_dual_mic_tmp"),
        sleep=fake_sleep,
        write=capture_write,
        progress_stream=io.StringIO(),
        record_fn=fake_record,
    )

    assert sleep_calls == [1.0, 1.0, 1.0]
    assert recorded == [(requested_duration, True)]
    assert "GET READY" in output.getvalue()
    assert "✓ CAPTURE COMPLETE" in output.getvalue()

    metadata_path = Path("data/test_dual_mic_tmp/metadata.json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["requested_duration_s"] == requested_duration
    assert metadata["samples_captured"] == expected_samples


def test_requested_recording_duration_is_preserved() -> None:
    config = MultiMicConfig(sample_rate=1_000, input_channels=2, blocksize=100)
    duration_s = 2.5
    frames_target = int(config.sample_rate * duration_s)

    class FakeSoundDeviceInput:
        def __init__(self, capture_config: MultiMicConfig) -> None:
            self._remaining = frames_target
            self.input_overflows = 0

        def read(self, max_samples: int) -> np.ndarray:
            count = min(max_samples, self._remaining)
            self._remaining -= count
            return np.zeros((count, 2), dtype=np.float32)

        def close(self) -> None:
            return None

    original_input = sounddevice_multimic_module.SoundDeviceMultiChannelInput
    sounddevice_multimic_module.SoundDeviceMultiChannelInput = FakeSoundDeviceInput

    try:
        result = record_dual_microphone(config, duration_s, read_chunk_size=100)
    finally:
        sounddevice_multimic_module.SoundDeviceMultiChannelInput = original_input

    assert result.primary.shape[0] == frames_target
    assert abs(result.analysis.duration_s - duration_s) < 1e-6


def test_capture_emits_completion_status() -> None:
    config = MultiMicConfig(sample_rate=48_000)
    output = io.StringIO()

    def fake_record(
        capture_config: MultiMicConfig,
        duration_s: float,
        **_: object,
    ) -> DualMicCaptureResult:
        return _make_capture_result(
            config=capture_config,
            num_samples=int(capture_config.sample_rate * duration_s),
        )

    run_hardware_capture(
        config=config,
        duration_s=1.0,
        output_dir=Path("data/test_dual_mic_status"),
        sleep=lambda _: None,
        write=lambda message="", **_: output.write(f"{message}\n"),
        progress_stream=io.StringIO(),
        record_fn=fake_record,
    )

    text = output.getvalue()
    assert "✓ CAPTURE COMPLETE" in text
    assert "Analyzing channels..." in text
    assert "✓ ANALYSIS COMPLETE" in text
    assert text.index("✓ CAPTURE COMPLETE") < text.index("Analyzing channels...")
    assert text.index("Analyzing channels...") < text.index("✓ ANALYSIS COMPLETE")


def test_capture_failure_is_reported() -> None:
    config = MultiMicConfig(sample_rate=48_000)
    output = io.StringIO()

    def failing_record(*_args: object, **_kwargs: object) -> DualMicCaptureResult:
        raise RuntimeError("device open failed")

    try:
        run_hardware_capture(
            config=config,
            duration_s=1.0,
            output_dir=Path("data/test_dual_mic_fail"),
            sleep=lambda _: None,
            write=lambda message="", **_: output.write(f"{message}\n"),
            progress_stream=io.StringIO(),
            record_fn=failing_record,
        )
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("Expected capture failure to exit with code 1.")

    text = output.getvalue()
    assert "✗ CAPTURE FAILED" in text
    assert "device open failed" in text
    assert "✓ CAPTURE COMPLETE" not in text
    assert "✓ ANALYSIS COMPLETE" not in text


def _parse_device(value: str | None) -> int | str | None:
    if value is None:
        return None

    try:
        return int(value)
    except ValueError:
        return value


def _save_stereo_wav(
    path: Path,
    left: np.ndarray,
    right: np.ndarray,
    sample_rate: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stereo = np.column_stack(
        [
            np.asarray(left, dtype=np.float32).reshape(-1),
            np.asarray(right, dtype=np.float32).reshape(-1),
        ]
    )
    sf.write(path, stereo, sample_rate)


def run_hardware_capture(
    *,
    config: MultiMicConfig,
    duration_s: float,
    output_dir: Path,
    condition: str | None = None,
    sleep: Callable[[float], None] = time.sleep,
    write: Callable[..., None] = print,
    progress_stream: TextIO | None = None,
    record_fn: Callable[..., DualMicCaptureResult] = record_dual_microphone,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    write(
        "Synchronized dual-microphone capture "
        f"(device={config.input_device!r}, channels={config.input_channels}, "
        f"primary={config.primary_channel}, reference={config.reference_channel})"
    )
    if condition is not None:
        write(f"condition={condition}")

    try:
        run_countdown(sleep=sleep, write=write)

        def on_progress(frames_done: int, frames_target: int, elapsed_s: float) -> None:
            target_s = (
                frames_target / config.sample_rate
                if config.sample_rate > 0
                else duration_s
            )
            update_recording_progress(
                elapsed_s=elapsed_s,
                total_s=target_s,
                stream=progress_stream,
            )

        result = record_fn(
            config,
            duration_s,
            on_progress=on_progress,
            defer_analysis=True,
        )
        finish_progress_line(progress_stream)
        emit_capture_complete(write=write)

        emit_analysis_start(write=write)
        analysis = analyze_channel_pair(
            result.primary,
            result.reference,
            config,
        )
        emit_analysis_complete(write=write)
    except Exception as exc:
        finish_progress_line(progress_stream)
        emit_capture_failed(exc, write=write)
        raise SystemExit(1) from exc

    primary_path = output_dir / "primary.wav"
    reference_path = output_dir / "reference.wav"
    stereo_path = output_dir / "stereo.wav"
    metadata_path = output_dir / "metadata.json"

    save_mono_wav(primary_path, result.primary, config.sample_rate)
    save_mono_wav(reference_path, result.reference, config.sample_rate)
    _save_stereo_wav(
        stereo_path,
        result.primary,
        result.reference,
        config.sample_rate,
    )

    metadata = {
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "sample_rate": config.sample_rate,
        "channel_count": config.input_channels,
        "primary_channel": config.primary_channel,
        "reference_channel": config.reference_channel,
        "input_device": config.input_device,
        "requested_duration_s": duration_s,
        "samples_captured": int(result.primary.shape[0]),
        "duration_s": analysis.duration_s,
        "input_overflows": result.input_overflows,
        "elapsed_s": result.elapsed_s,
        "analysis": analysis.as_dict(),
        "experiment_conditions": {
            "A_speech_only": (
                "Measure primary/reference RMS, correlation, and delay."
            ),
            "B_speech_plus_stationary_noise": (
                "Check whether reference tracks noise with less speech energy."
            ),
            "C_speech_plus_impulsive_noise": (
                "Check whether impulsive events appear on both channels."
            ),
        },
        "note": (
            "No reference-quality thresholds are defined yet. Compare "
            "statistics across conditions before NLMS integration."
        ),
        "files": {
            "primary_wav": primary_path.name,
            "reference_wav": reference_path.name,
            "stereo_wav": stereo_path.name,
        },
    }

    if condition is not None:
        metadata["condition"] = condition

    metadata_path.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    write(json.dumps(metadata, indent=2))
    write(f"Wrote {primary_path}")
    write(f"Wrote {reference_path}")
    write(f"Wrote {stereo_path}")
    write(f"Wrote {metadata_path}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Dual-microphone reference capture diagnostics. Runs synthetic "
            "tests by default; use --capture for synchronized hardware "
            "recording from one multi-channel input device."
        ),
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List host audio devices and exit.",
    )
    parser.add_argument(
        "--capture",
        action="store_true",
        help="Capture hardware audio and write primary/reference/stereo WAVs.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=5.0,
        help="Capture duration in seconds.",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=DEFAULT_SAMPLE_RATE,
        help="Capture sample rate in Hz.",
    )
    parser.add_argument(
        "--input-device",
        default=None,
        help="Input device index or name.",
    )
    parser.add_argument(
        "--input-channels",
        type=int,
        default=2,
        help="Synchronized input channel count opened on the device.",
    )
    parser.add_argument(
        "--primary-channel",
        type=int,
        default=0,
        help="Primary microphone channel index.",
    )
    parser.add_argument(
        "--reference-channel",
        type=int,
        default=1,
        help="Reference microphone channel index.",
    )
    parser.add_argument(
        "--blocksize",
        type=int,
        default=1024,
        help="PortAudio block size hint.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for capture mode.",
    )
    parser.add_argument(
        "--condition",
        choices=CAPTURE_CONDITIONS,
        default=None,
        help="Optional experiment condition label stored in metadata.json.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.list_devices:
        print(format_device_listing())
        return

    if args.capture:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_dir = (
            args.output_dir
            if args.output_dir is not None
            else DEFAULT_OUTPUT_DIR / timestamp
        )

        config = MultiMicConfig(
            sample_rate=args.sample_rate,
            input_device=_parse_device(args.input_device),
            input_channels=args.input_channels,
            primary_channel=args.primary_channel,
            reference_channel=args.reference_channel,
            blocksize=args.blocksize,
        )

        run_hardware_capture(
            config=config,
            duration_s=args.duration,
            output_dir=output_dir,
            condition=args.condition,
        )
        return

    tests = [
        test_configuration_validation,
        test_channel_routing_extracts_configured_channels,
        test_channel_routing_preserves_length,
        test_fake_multichannel_input_streaming,
        test_sample_rate_validation_on_adapter,
        test_correlation_and_delay_on_synthetic_pair,
        test_dual_mic_residual_frame_validation,
        test_analysis_reports_rms_and_peak,
        test_non_multichannel_routing_rejected,
        test_countdown_does_not_extend_capture_duration,
        test_requested_recording_duration_is_preserved,
        test_capture_emits_completion_status,
        test_capture_failure_is_reported,
    ]

    print("=" * 70)
    print("DRDO-ANC | Dual-Microphone Reference Tests")
    print("=" * 70)

    for test in tests:
        test()
        print(f"PASS: {test.__name__}")

    print("=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
