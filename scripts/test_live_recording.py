import json
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

from drdo_anc.audio import load_mono_wav
from drdo_anc.audio.live import (
    FakeAudioInput,
    FakeAudioOutput,
    LiveStreamRecorder,
    StreamingPipeline,
    create_live_session_dir,
)
from drdo_anc.audio.live.alignment import RecordingLengthTracker
from drdo_anc.audio.live.recorder import align_recorded_streams
from drdo_anc.audio.live.session_analysis import (
    analyze_live_session,
    find_energy_drop_windows,
)
from drdo_anc.enhancement.base import Enhancer


class TrackingEnhancer(Enhancer):
    """Identity enhancer that scales input for enhanced-path verification."""

    def __init__(self, sample_rate: int = 48_000) -> None:
        self._sample_rate = sample_rate
        self.flush_calls = 0
        self._flush_output = np.empty(0, dtype=np.float32)

    def load(self) -> None:
        return None

    def reset(self) -> None:
        return None

    def sample_rate(self) -> int:
        return self._sample_rate

    def name(self) -> str:
        return "TrackingEnhancer"

    def process(self, audio: torch.Tensor) -> torch.Tensor:
        mono = audio.squeeze(0) if audio.ndim == 2 else audio
        return (mono * 0.5).unsqueeze(0)

    def process_stream(self, audio_chunk: torch.Tensor) -> torch.Tensor:
        mono = (
            audio_chunk.squeeze(0)
            if audio_chunk.ndim == 2
            else audio_chunk
        )
        return mono * 0.5

    def flush(self) -> torch.Tensor:
        self.flush_calls += 1
        return torch.from_numpy(self._flush_output.copy())


class DelayedEnhancer(Enhancer):
    """Identity enhancer with a stable startup delay like streaming DF3."""

    def __init__(
        self,
        sample_rate: int = 48_000,
        *,
        delay_samples: int = 480,
        flush_samples: int = 0,
    ) -> None:
        self._sample_rate = sample_rate
        self._delay_samples = delay_samples
        self._flush_samples = flush_samples
        self._input_buf = np.empty(0, dtype=np.float32)
        self._emitted = 0
        self.flush_calls = 0

    def load(self) -> None:
        return None

    def reset(self) -> None:
        self._input_buf = np.empty(0, dtype=np.float32)
        self._emitted = 0

    def sample_rate(self) -> int:
        return self._sample_rate

    def name(self) -> str:
        return "DelayedEnhancer"

    def process(self, audio: torch.Tensor) -> torch.Tensor:
        mono = audio.squeeze(0) if audio.ndim == 2 else audio
        return mono.unsqueeze(0)

    def process_stream(self, audio_chunk: torch.Tensor) -> torch.Tensor:
        mono = (
            audio_chunk.squeeze(0)
            if audio_chunk.ndim == 2
            else audio_chunk
        )
        mono_np = mono.detach().cpu().numpy().astype(np.float32, copy=False)
        self._input_buf = np.concatenate([self._input_buf, mono_np])

        target_emitted = max(0, len(self._input_buf) - self._delay_samples)

        if target_emitted <= self._emitted:
            return torch.empty(0, dtype=torch.float32)

        out = self._input_buf[self._emitted:target_emitted]
        self._emitted = target_emitted
        return torch.from_numpy(out.copy())

    def flush(self) -> torch.Tensor:
        self.flush_calls += 1
        available = len(self._input_buf) - self._delay_samples
        out = self._input_buf[self._emitted:max(0, available)]

        if self._flush_samples > 0:
            out = np.concatenate(
                [
                    out,
                    np.zeros(self._flush_samples, dtype=np.float32),
                ]
            )

        self._emitted += len(out)
        return torch.from_numpy(out.copy())


def test_recorder_writes_valid_wav() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        session_dir = create_live_session_dir(Path(tmp_dir))
        recorder = LiveStreamRecorder(session_dir, 48_000)
        recorder.start()

        recorder.write_input(np.ones(480, dtype=np.float32))
        recorder.write_enhanced(np.full(480, 0.5, dtype=np.float32))
        recorder.finalize()

        input_audio, input_sr = load_mono_wav(recorder.paths.input_path)
        enhanced_audio, enhanced_sr = load_mono_wav(
            recorder.paths.enhanced_path,
        )

        assert input_sr == 48_000
        assert enhanced_sr == 48_000
        assert len(input_audio) == 480
        assert len(enhanced_audio) == 480
        assert np.allclose(input_audio, 1.0)
        assert np.allclose(enhanced_audio, 0.5)


def test_session_metadata_is_valid() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        session_dir = create_live_session_dir(Path(tmp_dir))
        recorder = LiveStreamRecorder(
            session_dir,
            48_000,
            metadata_base={
                "model": "DeepFilterNet3",
                "chunk_size": 1024,
            },
        )
        recorder.start()
        recorder.write_input(np.ones(100, dtype=np.float32))
        recorder.write_enhanced(np.ones(100, dtype=np.float32))
        recorder.finalize()

        payload = json.loads(
            recorder.paths.metadata_path.read_text(encoding="utf-8")
        )

        assert payload["sample_rate"] == 48_000
        assert payload["model"] == "DeepFilterNet3"
        assert payload["chunk_size"] == 1024
        assert payload["input_samples_recorded"] == 100
        assert payload["enhanced_samples_recorded"] == 100


def test_pipeline_with_recording_enabled() -> None:
    chunks = [
        np.full(300, 0.25, dtype=np.float32),
        np.full(700, 0.50, dtype=np.float32),
    ]

    with tempfile.TemporaryDirectory() as tmp_dir:
        session_dir = create_live_session_dir(Path(tmp_dir))
        recorder = LiveStreamRecorder(session_dir, 48_000)
        recorder.start()

        audio_input = FakeAudioInput(chunks, sample_rate=48_000)
        audio_output = FakeAudioOutput(sample_rate=48_000)
        enhancer = TrackingEnhancer()

        pipeline = StreamingPipeline(
            audio_input,
            audio_output,
            enhancer,
            read_chunk_size=512,
            recorder=recorder,
        )

        pipeline.run()

        input_audio, _ = load_mono_wav(recorder.paths.input_path)
        enhanced_audio, _ = load_mono_wav(recorder.paths.enhanced_path)

        assert np.allclose(input_audio, np.concatenate(chunks))
        assert np.allclose(enhanced_audio, np.concatenate(chunks) * 0.5)
        assert enhancer.flush_calls == 1
        assert pipeline.instrumentation is not None
        assert pipeline.instrumentation.chunk_count == 2
        assert pipeline.instrumentation.input_samples == 1000
        assert pipeline.instrumentation.output_samples == 1000


def test_pipeline_without_recording_still_works() -> None:
    chunks = [np.ones(128, dtype=np.float32)]

    audio_input = FakeAudioInput(chunks, sample_rate=48_000)
    audio_output = FakeAudioOutput(sample_rate=48_000)

    pipeline = StreamingPipeline(
        audio_input,
        audio_output,
        enhancer=None,
    )

    pipeline.run()

    assert len(audio_output.written_chunks) == 1
    assert pipeline.instrumentation is None


def test_recorder_reports_dropped_chunks() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        session_dir = create_live_session_dir(Path(tmp_dir))
        recorder = LiveStreamRecorder(
            session_dir,
            48_000,
            queue_capacity=1,
        )
        recorder._started = True
        recorder._queue.put_nowait(
            ("input", np.ones(10, dtype=np.float32)),
        )
        recorder.write_input(np.ones(10, dtype=np.float32))

        assert recorder.dropped_chunks == 1


def test_session_directories_do_not_overwrite() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        base = Path(tmp_dir)
        first = create_live_session_dir(base)
        second = create_live_session_dir(base)

        assert first != second
        assert first.exists()
        assert second.exists()


def test_delayed_enhancer_alignment_prepends_leading_silence() -> None:
    delay_samples = 480
    chunks = [
        np.linspace(0.1, 0.5, 300, dtype=np.float32),
        np.linspace(0.5, 0.9, 700, dtype=np.float32),
    ]

    with tempfile.TemporaryDirectory() as tmp_dir:
        session_dir = create_live_session_dir(Path(tmp_dir))
        recorder = LiveStreamRecorder(
            session_dir,
            48_000,
            metadata_base={
                "model": "DelayedEnhancer",
                "streaming_delay_samples": 1440,
            },
        )
        recorder.start()

        audio_input = FakeAudioInput(chunks, sample_rate=48_000)
        audio_output = FakeAudioOutput(sample_rate=48_000)
        enhancer = DelayedEnhancer(delay_samples=delay_samples)

        pipeline = StreamingPipeline(
            audio_input,
            audio_output,
            enhancer,
            read_chunk_size=512,
            recorder=recorder,
        )

        pipeline.run()

        input_audio, _ = load_mono_wav(recorder.paths.input_path)
        enhanced_audio, _ = load_mono_wav(recorder.paths.enhanced_path)
        metadata = json.loads(
            recorder.paths.metadata_path.read_text(encoding="utf-8")
        )

        assert len(input_audio) == len(enhanced_audio) == 1000
        assert metadata["input_samples_recorded"] == 1000
        assert metadata["enhanced_samples_recorded"] == 1000
        assert metadata["recording_alignment"]["action"] == (
            "prepend_enhanced_leading_silence"
        )
        assert metadata["recording_alignment"]["samples_padded"] == (
            delay_samples
        )
        assert np.allclose(enhanced_audio[:delay_samples], 0.0)
        assert np.allclose(
            enhanced_audio[delay_samples:],
            input_audio[: 1000 - delay_samples],
            atol=1e-4,
        )


def test_align_recorded_streams_rejects_unstable_gap() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        session_dir = Path(tmp_dir)
        input_path = session_dir / "input.wav"
        enhanced_path = session_dir / "enhanced.wav"

        sf.write(input_path, np.ones(1000, dtype=np.float32), 48_000)
        sf.write(enhanced_path, np.ones(400, dtype=np.float32), 48_000)

        tracker = RecordingLengthTracker()
        tracker.note_input(600)
        tracker.note_enhanced(100)
        tracker.note_input(400)
        tracker.note_enhanced(300)

        assert tracker.gap_stable is False

        result = align_recorded_streams(
            input_path=input_path,
            enhanced_path=enhanced_path,
            sample_rate=48_000,
            tracker=tracker,
            passthrough=False,
            streaming_delay_samples=1440,
            input_samples_written=1000,
            enhanced_samples_written=400,
        )

        assert result["status"] == "mismatch"
        assert result["action"] == "none"


def test_find_energy_drop_windows_detects_gain_drop() -> None:
    sample_rate = 48_000
    duration = 1.0
    num_samples = int(sample_rate * duration)
    t = np.linspace(0.0, duration, num_samples, endpoint=False)

    input_audio = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    enhanced_audio = input_audio.copy()
    drop_start = int(0.4 * sample_rate)
    drop_end = int(0.6 * sample_rate)
    enhanced_audio[drop_start:drop_end] *= 0.01

    windows = find_energy_drop_windows(
        input_audio,
        enhanced_audio,
        sample_rate,
        delay_samples=0,
        window_ms=50.0,
        hop_ms=25.0,
        drop_threshold_db=-12.0,
        min_input_energy_db=-50.0,
    )

    assert windows
    assert any(
        window.start_s <= 0.45 <= window.end_s for window in windows
    )


def test_analyze_live_session_reads_metadata_delay() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        session_dir = Path(tmp_dir)
        sample_rate = 48_000
        duration = 0.5
        num_samples = int(sample_rate * duration)
        t = np.linspace(0.0, duration, num_samples, endpoint=False)
        input_audio = (0.4 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
        enhanced_audio = input_audio.copy()

        sf.write(session_dir / "input.wav", input_audio, sample_rate)
        sf.write(session_dir / "enhanced.wav", enhanced_audio, sample_rate)
        (session_dir / "metadata.json").write_text(
            json.dumps(
                {
                    "sample_rate": sample_rate,
                    "input_path": "input.wav",
                    "enhanced_path": "enhanced.wav",
                    "streaming_delay_samples": 0,
                }
            ),
            encoding="utf-8",
        )

        report = analyze_live_session(session_dir)

        assert report["delay_samples"] == 0
        assert report["lengths_match"] is True
        assert report["drop_window_count"] == 0


def main() -> None:
    print("=" * 70)
    print("DRDO-ANC | Live Recording Tests")
    print("=" * 70)

    tests = [
        test_recorder_writes_valid_wav,
        test_session_metadata_is_valid,
        test_pipeline_with_recording_enabled,
        test_pipeline_without_recording_still_works,
        test_recorder_reports_dropped_chunks,
        test_session_directories_do_not_overwrite,
        test_delayed_enhancer_alignment_prepends_leading_silence,
        test_align_recorded_streams_rejects_unstable_gap,
        test_find_energy_drop_windows_detects_gain_drop,
        test_analyze_live_session_reads_metadata_delay,
    ]

    for test in tests:
        test()
        print(f"PASS: {test.__name__}")

    print("=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()
