import json
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

from drdo_anc.audio import load_mono_wav
from drdo_anc.audio.live.replay import (
    DEFAULT_REPLAY_CHUNK_SIZE,
    load_session_chunk_size,
    replay_wav_file,
    replay_wav_through_enhancer,
    split_into_chunks,
)
from drdo_anc.enhancement import (
    ModelConfig,
    create_enhancer,
    get_model_config,
    register_model,
)
from drdo_anc.enhancement.base import Enhancer


class ReplayTrackingEnhancer(Enhancer):
    """1:1 streaming test double that records API usage."""

    def __init__(
        self,
        sample_rate: int = 48_000,
        *,
        scale: float = 0.5,
        flush_output: np.ndarray | None = None,
    ) -> None:
        self._sample_rate = sample_rate
        self._scale = scale
        self.process_calls = 0
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
        return None

    def sample_rate(self) -> int:
        return self._sample_rate

    def name(self) -> str:
        return "ReplayTrackingEnhancer"

    def process(self, audio: torch.Tensor) -> torch.Tensor:
        self.process_calls += 1
        mono = audio.squeeze(0) if audio.ndim == 2 else audio
        return mono.unsqueeze(0)

    def process_stream(self, audio_chunk: torch.Tensor) -> torch.Tensor:
        self.stream_calls += 1
        mono = (
            audio_chunk.squeeze(0)
            if audio_chunk.ndim == 2
            else audio_chunk
        )
        self.stream_chunk_sizes.append(int(mono.numel()))
        return mono.float() * self._scale

    def flush(self) -> torch.Tensor:
        self.flush_calls += 1
        return torch.from_numpy(self._flush_output.copy())


def _register_replay_test_model() -> str:
    model_name = "ReplayTrackingEnhancer"

    try:
        get_model_config(model_name)
    except KeyError:
        register_model(
            ModelConfig(
                name=model_name,
                streaming_delay_samples=0,
                factory=lambda: ReplayTrackingEnhancer(),
            )
        )

    return model_name


def test_split_into_chunks_handles_arbitrary_sizes() -> None:
    audio = np.arange(1000, dtype=np.float32)
    chunks = split_into_chunks(audio, 137)

    assert [len(chunk) for chunk in chunks] == [137] * 7 + [41]
    assert np.array_equal(np.concatenate(chunks), audio)


def test_replay_loads_wav_correctly() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        input_path = Path(tmp_dir) / "input.wav"
        output_path = Path(tmp_dir) / "replayed.wav"
        audio = np.linspace(-0.5, 0.5, 480, dtype=np.float32)
        sf.write(input_path, audio, 48_000)

        enhancer = ReplayTrackingEnhancer()
        result = replay_wav_file(
            input_path,
            output_path,
            enhancer,
            model_name="ReplayTrackingEnhancer",
            chunk_size=137,
        )

        loaded_input, input_sr = load_mono_wav(input_path)
        loaded_output, output_sr = load_mono_wav(output_path)

        assert input_sr == 48_000
        assert output_sr == 48_000
        assert result.input_samples == len(loaded_input) == 480
        assert np.allclose(loaded_input, audio, atol=1e-4)


def test_registry_creates_requested_model() -> None:
    model_name = _register_replay_test_model()
    enhancer = create_enhancer(model_name, load=False)

    assert isinstance(enhancer, ReplayTrackingEnhancer)
    assert enhancer.name() == "ReplayTrackingEnhancer"


def test_replay_uses_process_stream_not_process() -> None:
    enhancer = ReplayTrackingEnhancer()
    input_audio = np.ones(300, dtype=np.float32)

    replay_wav_through_enhancer(
        input_audio,
        48_000,
        enhancer,
        model_name="ReplayTrackingEnhancer",
        input_path=Path("input.wav"),
        output_path=Path("output.wav"),
        chunk_size=137,
    )

    assert enhancer.stream_calls == 3
    assert enhancer.stream_chunk_sizes == [137, 137, 26]
    assert enhancer.process_calls == 0


def test_replay_calls_flush_exactly_once() -> None:
    enhancer = ReplayTrackingEnhancer(
        flush_output=np.full(16, 0.25, dtype=np.float32),
    )
    input_audio = np.ones(256, dtype=np.float32)

    result = replay_wav_through_enhancer(
        input_audio,
        48_000,
        enhancer,
        model_name="ReplayTrackingEnhancer",
        input_path=Path("input.wav"),
        output_path=Path("output.wav"),
        chunk_size=1024,
    )

    assert enhancer.flush_calls == 1
    assert result.output_samples == 256 + 16


def test_replay_output_length_is_correct_for_identity_streaming() -> None:
    enhancer = ReplayTrackingEnhancer(scale=1.0)
    input_audio = np.linspace(0.0, 1.0, 1000, dtype=np.float32)

    result = replay_wav_through_enhancer(
        input_audio,
        48_000,
        enhancer,
        model_name="ReplayTrackingEnhancer",
        input_path=Path("input.wav"),
        output_path=Path("output.wav"),
        chunk_size=1024,
    )

    assert result.input_samples == 1000
    assert result.output_samples == 1000
    assert np.allclose(result.output_audio, input_audio, atol=1e-6)


def test_replay_writes_valid_output_wav_and_metadata() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        input_path = Path(tmp_dir) / "input.wav"
        output_path = Path(tmp_dir) / "replayed_test.wav"
        metadata_path = output_path.with_suffix(".json")
        audio = np.full(512, 0.3, dtype=np.float32)
        sf.write(input_path, audio, 48_000)

        enhancer = ReplayTrackingEnhancer()
        result = replay_wav_file(
            input_path,
            output_path,
            enhancer,
            model_name="ReplayTrackingEnhancer",
            chunk_size=137,
            streaming_delay_samples=0,
        )

        loaded_output, output_sr = load_mono_wav(output_path)
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))

        assert output_sr == 48_000
        assert loaded_output.dtype == np.float32
        assert len(loaded_output) == result.output_samples
        assert payload["model"] == "ReplayTrackingEnhancer"
        assert payload["chunk_size"] == 137
        assert payload["input_samples"] == 512
        assert payload["output_samples"] == result.output_samples
        assert payload["streaming_delay_samples"] == 0
        assert Path(payload["input_path"]) == input_path.resolve()
        assert Path(payload["output_path"]) == output_path.resolve()


def test_repeated_replay_is_deterministic() -> None:
    input_audio = np.linspace(-1.0, 1.0, 999, dtype=np.float32)

    first = replay_wav_through_enhancer(
        input_audio,
        48_000,
        ReplayTrackingEnhancer(scale=0.75),
        model_name="ReplayTrackingEnhancer",
        input_path=Path("input.wav"),
        output_path=Path("output_a.wav"),
        chunk_size=137,
    )
    second = replay_wav_through_enhancer(
        input_audio,
        48_000,
        ReplayTrackingEnhancer(scale=0.75),
        model_name="ReplayTrackingEnhancer",
        input_path=Path("input.wav"),
        output_path=Path("output_b.wav"),
        chunk_size=137,
    )

    assert np.array_equal(first.output_audio, second.output_audio)


def test_load_session_chunk_size_reads_metadata() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        session_dir = Path(tmp_dir)
        input_path = session_dir / "input.wav"
        sf.write(input_path, np.zeros(10, dtype=np.float32), 48_000)
        (session_dir / "metadata.json").write_text(
            json.dumps({"chunk_size": 777}),
            encoding="utf-8",
        )

        assert load_session_chunk_size(input_path) == 777


def test_default_chunk_size_when_metadata_missing() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        input_path = Path(tmp_dir) / "input.wav"
        sf.write(input_path, np.zeros(10, dtype=np.float32), 48_000)

        assert load_session_chunk_size(input_path) is None


def main() -> None:
    print("=" * 70)
    print("DRDO-ANC | Live Replay Tests")
    print("=" * 70)

    tests = [
        test_split_into_chunks_handles_arbitrary_sizes,
        test_replay_loads_wav_correctly,
        test_registry_creates_requested_model,
        test_replay_uses_process_stream_not_process,
        test_replay_calls_flush_exactly_once,
        test_replay_output_length_is_correct_for_identity_streaming,
        test_replay_writes_valid_output_wav_and_metadata,
        test_repeated_replay_is_deterministic,
        test_load_session_chunk_size_reads_metadata,
        test_default_chunk_size_when_metadata_missing,
    ]

    for test in tests:
        test()
        print(f"PASS: {test.__name__}")

    print("=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()
