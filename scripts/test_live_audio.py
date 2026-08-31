import numpy as np
import torch

from drdo_anc.audio.live import (
    FakeAudioInput,
    FakeAudioOutput,
    StreamingPipeline,
    downmix_to_mono,
    upmix_mono_to_channels,
)
from drdo_anc.enhancement.base import Enhancer


class TrackingEnhancer(Enhancer):
    """Test double that records streaming calls."""

    def __init__(
        self,
        sample_rate: int = 48_000,
        *,
        flush_output: np.ndarray | None = None,
    ) -> None:
        self._sample_rate = sample_rate
        self.reset_calls = 0
        self.stream_calls = 0
        self.flush_calls = 0
        self.stream_chunk_sizes: list[int] = []
        self._flush_output = (
            flush_output
            if flush_output is not None
            else np.empty(0, dtype=np.float32)
        )

    def load(self) -> None:
        return None

    def reset(self) -> None:
        self.reset_calls += 1

    def sample_rate(self) -> int:
        return self._sample_rate

    def name(self) -> str:
        return "TrackingEnhancer"

    def process(self, audio: torch.Tensor) -> torch.Tensor:
        if audio.ndim == 2:
            audio = audio.squeeze(0)

        return audio.unsqueeze(0)

    def process_stream(
        self,
        audio_chunk: torch.Tensor,
    ) -> torch.Tensor:
        self.stream_calls += 1

        if audio_chunk.ndim == 2:
            audio_chunk = audio_chunk.squeeze(0)

        self.stream_chunk_sizes.append(int(audio_chunk.numel()))

        return audio_chunk.float()

    def flush(self) -> torch.Tensor:
        self.flush_calls += 1
        return torch.from_numpy(self._flush_output.copy())


def test_passthrough_preserves_input_chunks() -> None:
    chunks = [
        np.full(300, 0.25, dtype=np.float32),
        np.full(700, 0.50, dtype=np.float32),
        np.full(250, 0.75, dtype=np.float32),
    ]

    audio_input = FakeAudioInput(chunks, sample_rate=48_000)
    audio_output = FakeAudioOutput(sample_rate=48_000)

    pipeline = StreamingPipeline(
        audio_input,
        audio_output,
        enhancer=None,
        read_chunk_size=512,
    )

    pipeline.run()

    written = audio_output.written_chunks
    assert len(written) == 3
    assert written[0].shape == (300,)
    assert written[1].shape == (700,)
    assert written[2].shape == (250,)
    assert np.allclose(
        audio_output.all_written(),
        np.concatenate(chunks),
    )


def test_enhancer_receives_arbitrary_hardware_chunks() -> None:
    chunks = [
        np.ones(300, dtype=np.float32),
        np.ones(700, dtype=np.float32),
        np.ones(250, dtype=np.float32),
    ]

    enhancer = TrackingEnhancer()
    audio_input = FakeAudioInput(chunks, sample_rate=48_000)
    audio_output = FakeAudioOutput(sample_rate=48_000)

    pipeline = StreamingPipeline(
        audio_input,
        audio_output,
        enhancer,
        read_chunk_size=1024,
    )

    pipeline.run()

    assert enhancer.reset_calls == 1
    assert enhancer.stream_calls == 3
    assert enhancer.stream_chunk_sizes == [300, 700, 250]
    assert enhancer.flush_calls == 1


def test_flush_called_exactly_once_and_writes_tail() -> None:
    chunks = [np.ones(500, dtype=np.float32)]
    tail = np.full(40, 0.5, dtype=np.float32)

    enhancer = TrackingEnhancer(flush_output=tail)
    audio_input = FakeAudioInput(chunks, sample_rate=48_000)
    audio_output = FakeAudioOutput(sample_rate=48_000)

    pipeline = StreamingPipeline(
        audio_input,
        audio_output,
        enhancer,
        read_chunk_size=256,
    )

    pipeline.run()

    assert enhancer.flush_calls == 1
    assert len(audio_output.written_chunks) == 2
    assert audio_output.written_chunks[-1].shape == (40,)


def test_request_stop_triggers_single_flush() -> None:
    enhancer = TrackingEnhancer()
    audio_input = FakeAudioInput(
        [np.ones(480, dtype=np.float32)],
        sample_rate=48_000,
    )
    audio_output = FakeAudioOutput(sample_rate=48_000)

    pipeline = StreamingPipeline(
        audio_input,
        audio_output,
        enhancer,
        read_chunk_size=128,
    )

    pipeline.request_stop()
    pipeline.run()

    assert enhancer.flush_calls == 1


def test_sample_rate_mismatch_raises() -> None:
    enhancer = TrackingEnhancer(sample_rate=48_000)
    audio_input = FakeAudioInput(
        [np.ones(10, dtype=np.float32)],
        sample_rate=16_000,
    )
    audio_output = FakeAudioOutput(sample_rate=16_000)

    try:
        StreamingPipeline(
            audio_input,
            audio_output,
            enhancer,
        )
    except ValueError as exc:
        assert "sample rate" in str(exc).lower()
    else:
        raise AssertionError("Expected sample-rate mismatch error.")


def test_downmix_and_upmix_channel_helpers() -> None:
    stereo = np.array(
        [[1.0, -1.0], [0.5, 0.5]],
        dtype=np.float32,
    )

    mono = downmix_to_mono(stereo)
    assert mono.shape == (2,)
    assert np.allclose(mono, [0.0, 0.5])

    upmixed = upmix_mono_to_channels(
        np.array([0.25, 0.75], dtype=np.float32),
        2,
    )
    assert upmixed.shape == (2, 2)
    assert np.allclose(upmixed[:, 0], upmixed[:, 1])


def test_passthrough_does_not_call_flush() -> None:
    enhancer = TrackingEnhancer()
    audio_input = FakeAudioInput(
        [np.ones(128, dtype=np.float32)],
        sample_rate=48_000,
    )
    audio_output = FakeAudioOutput(sample_rate=48_000)

    pipeline = StreamingPipeline(
        audio_input,
        audio_output,
        enhancer=None,
    )

    pipeline.run()

    assert enhancer.flush_calls == 0


def main() -> None:
    print("=" * 70)
    print("DRDO-ANC | Live Audio Tests")
    print("=" * 70)

    tests = [
        test_passthrough_preserves_input_chunks,
        test_enhancer_receives_arbitrary_hardware_chunks,
        test_flush_called_exactly_once_and_writes_tail,
        test_request_stop_triggers_single_flush,
        test_sample_rate_mismatch_raises,
        test_downmix_and_upmix_channel_helpers,
        test_passthrough_does_not_call_flush,
    ]

    for test in tests:
        test()
        print(f"PASS: {test.__name__}")

    print("=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()
