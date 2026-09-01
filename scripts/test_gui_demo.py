#!/usr/bin/env python3
"""Demo mode streaming tests (no Qt or microphone required)."""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import numpy as np

src_dir = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(src_dir))

from drdo_anc.enhancement.base import Enhancer
from drdo_anc.gui.demo import (
    ReplayAudioInput,
    SelectableAudioOutput,
    apply_impulsive_overlay,
    load_demo_scenarios,
    load_scenario_audio,
)
from drdo_anc.audio.live.fake import FakeAudioOutput
from drdo_anc.audio.live.pipeline import StreamingPipeline
import torch


class _IdentityStreamingEnhancer(Enhancer):
    def __init__(self, sample_rate: int = 48_000, scale: float = 0.75) -> None:
        self._sample_rate = sample_rate
        self._scale = scale
        self.flush_calls = 0

    def load(self) -> None:
        return None

    def reset(self) -> None:
        return None

    def sample_rate(self) -> int:
        return self._sample_rate

    def name(self) -> str:
        return "IdentityStreamingEnhancer"

    def process(self, audio: torch.Tensor) -> torch.Tensor:
        mono = audio.squeeze(0) if audio.ndim == 2 else audio
        return mono.unsqueeze(0)

    def process_stream(self, audio_chunk: torch.Tensor) -> torch.Tensor:
        mono = audio_chunk.squeeze(0) if audio_chunk.ndim == 2 else audio_chunk
        return (mono.float() * self._scale).unsqueeze(0)

    def flush(self) -> torch.Tensor:
        self.flush_calls += 1
        return torch.zeros(1, 0)


class _RecordingBridge:
    def __init__(self) -> None:
        self.snapshots: list[tuple[np.ndarray, np.ndarray, float]] = []

    def set_stream_metadata(self, **kwargs) -> None:
        return None

    def set_demo_scenario(self, label: str) -> None:
        return None

    def clear_error(self) -> None:
        return None

    def set_error(self, message: str) -> None:
        raise RuntimeError(message)

    def publish_data(
        self,
        input_chunk: np.ndarray,
        output_chunk: np.ndarray,
        proc_time_s: float,
        stats: dict | None = None,
    ) -> None:
        self.snapshots.append(
            (
                input_chunk.copy(),
                output_chunk.copy(),
                proc_time_s,
            )
        )

    def set_pipeline_stage(self, stage: str) -> None:
        return None

    def set_audio_status(self, status: str) -> None:
        return None

    def set_playback_state(self, state: str) -> None:
        return None


def test_impulsive_overlay_is_deterministic() -> None:
    audio = np.zeros(200_000, dtype=np.float32)
    audio[5000:15000] = 0.05
    first = apply_impulsive_overlay(audio)
    second = apply_impulsive_overlay(audio)
    np.testing.assert_array_equal(first, second)
    assert first[12_050] > audio[12_050]


def test_replay_audio_input_pause_and_resume() -> None:
    audio = np.arange(4096, dtype=np.float32)
    replay = ReplayAudioInput(audio, 48_000, realtime=False)
    sink = FakeAudioOutput(48_000)
    enhancer = _IdentityStreamingEnhancer()
    pipeline = StreamingPipeline(replay, sink, enhancer, read_chunk_size=1024)

    def run() -> None:
        pipeline.run()

    thread = threading.Thread(target=run, daemon=False)
    thread.start()
    replay.play()
    time.sleep(0.05)
    replay.pause()
    paused_position = replay.position_samples
    assert paused_position > 0
    time.sleep(0.05)
    assert replay.position_samples == paused_position
    replay.play()
    time.sleep(0.05)
    replay.stop()
    pipeline.request_stop()
    thread.join(timeout=5.0)
    assert replay.position_samples == 0


def test_selectable_output_routes_raw_or_enhanced() -> None:
    sink = FakeAudioOutput(48_000)
    output = SelectableAudioOutput(sink)
    raw = np.ones(128, dtype=np.float32) * 0.5
    enhanced = np.ones(128, dtype=np.float32) * 0.1
    output.prepare_raw(raw)
    output.set_mode("raw")
    output.write(enhanced)
    np.testing.assert_allclose(sink.all_written(), raw)
    output.set_mode("enhanced")
    output.write(enhanced)
    written = sink.all_written()
    np.testing.assert_allclose(written[128:], enhanced)


def test_demo_scenarios_use_project_training_assets() -> None:
    _, scenarios = load_demo_scenarios()
    assert len(scenarios) == 2
    assert scenarios[0].wav_path.name == "train_clean_snr5.wav"
    assert scenarios[1].wav_path.name == "train_noisy_snr5.wav"
    assert scenarios[1].enhanced_wav_path is not None
    assert scenarios[1].enhanced_wav_path.name == "train_enh_snr5.wav"
    assert scenarios[0].wav_path.is_file()
    assert scenarios[1].wav_path.is_file()
    assert scenarios[1].enhanced_wav_path.is_file()


def test_demo_pipeline_uses_process_stream_and_flush() -> None:
    _, scenarios = load_demo_scenarios()
    scenario = scenarios[0]
    audio, sample_rate = load_scenario_audio(scenario, source_kind="file")

    replay = ReplayAudioInput(audio[:4096], sample_rate, realtime=False)
    sink = FakeAudioOutput(sample_rate)
    selectable = SelectableAudioOutput(sink)
    enhancer = _IdentityStreamingEnhancer(sample_rate=sample_rate)
    bridge = _RecordingBridge()

    def on_telemetry(in_chunk, out_chunk, proc_time):
        selectable.bind_chunk(in_chunk, out_chunk)
        bridge.publish_data(in_chunk, out_chunk, proc_time)

    pipeline = StreamingPipeline(
        replay,
        selectable,
        enhancer,
        read_chunk_size=1024,
        telemetry_callback=on_telemetry,
    )

    thread = threading.Thread(target=pipeline.run, daemon=False)
    thread.start()
    replay.play()
    thread.join(timeout=10.0)

    assert len(bridge.snapshots) >= 3
    assert sink.all_written().size > 0
    assert enhancer.flush_calls == 1


def test_demo_pipeline_is_deterministic() -> None:
    _, scenarios = load_demo_scenarios()
    scenario = scenarios[0]
    audio, sample_rate = load_scenario_audio(scenario, source_kind="file")
    clip = audio[:8192]

    def run_once() -> np.ndarray:
        replay = ReplayAudioInput(clip, sample_rate, realtime=False)
        sink = FakeAudioOutput(sample_rate)
        enhancer = _IdentityStreamingEnhancer(sample_rate=sample_rate)
        pipeline = StreamingPipeline(
            replay,
            sink,
            enhancer,
            read_chunk_size=1024,
        )
        thread = threading.Thread(target=pipeline.run, daemon=False)
        thread.start()
        replay.play()
        thread.join(timeout=10.0)
        return sink.all_written()

    first = run_once()
    second = run_once()
    np.testing.assert_allclose(first, second, rtol=1e-5, atol=1e-5)


def main() -> None:
    tests = [
        test_impulsive_overlay_is_deterministic,
        test_replay_audio_input_pause_and_resume,
        test_selectable_output_routes_raw_or_enhanced,
        test_demo_scenarios_use_project_training_assets,
        test_demo_pipeline_uses_process_stream_and_flush,
        test_demo_pipeline_is_deterministic,
    ]

    for test in tests:
        test()
        print(f"PASS: {test.__name__}")

    print(f"\nAll {len(tests)} demo tests passed.")


if __name__ == "__main__":
    main()
