from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from drdo_anc.audio.io import load_mono_wav, save_mono_wav
from drdo_anc.enhancement.base import Enhancer

from .fake import FakeAudioInput, FakeAudioOutput
from .pipeline import StreamingPipeline

DEFAULT_REPLAY_CHUNK_SIZE = 1024


@dataclass(frozen=True)
class ReplayResult:
    """Outcome of replaying a WAV through a streaming enhancer."""

    output_audio: np.ndarray
    sample_rate: int
    input_samples: int
    output_samples: int
    chunk_size: int
    chunk_count: int
    processing_time_s: float
    elapsed_s: float
    realtime_ratio: float | None
    model: str
    input_path: Path
    output_path: Path
    streaming_delay_samples: int | None = None

    def as_metadata(self) -> dict:
        payload = {
            "model": self.model,
            "input_path": str(self.input_path),
            "output_path": str(self.output_path),
            "sample_rate": self.sample_rate,
            "chunk_size": self.chunk_size,
            "chunk_count": self.chunk_count,
            "input_samples": self.input_samples,
            "output_samples": self.output_samples,
            "processing_time_s": self.processing_time_s,
            "elapsed_s": self.elapsed_s,
            "realtime_ratio": self.realtime_ratio,
        }

        if self.streaming_delay_samples is not None:
            payload["streaming_delay_samples"] = (
                self.streaming_delay_samples
            )

        return payload


class _RealtimeAudioInput:
    """Wrap an ``AudioInput`` and sleep for each chunk's audio duration."""

    def __init__(self, inner: FakeAudioInput) -> None:
        self._inner = inner

    def sample_rate(self) -> int:
        return self._inner.sample_rate()

    def read(self, max_samples: int) -> np.ndarray:
        chunk = self._inner.read(max_samples)

        if chunk.size > 0:
            duration_s = chunk.size / self._inner.sample_rate()
            time.sleep(duration_s)

        return chunk

    def close(self) -> None:
        self._inner.close()


def split_into_chunks(
    audio: np.ndarray,
    chunk_size: int,
) -> list[np.ndarray]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive.")

    array = np.asarray(audio, dtype=np.float32).reshape(-1)

    return [
        array[start : start + chunk_size]
        for start in range(0, len(array), chunk_size)
    ]


def load_session_chunk_size(input_path: Path) -> int | None:
    """Return ``chunk_size`` from sibling ``metadata.json`` when present."""

    metadata_path = input_path.parent / "metadata.json"

    if not metadata_path.is_file():
        return None

    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    chunk_size = payload.get("chunk_size")

    if chunk_size is None:
        return None

    return int(chunk_size)


def replay_wav_through_enhancer(
    input_audio: np.ndarray,
    sample_rate: int,
    enhancer: Enhancer,
    *,
    model_name: str,
    input_path: Path,
    output_path: Path,
    chunk_size: int = DEFAULT_REPLAY_CHUNK_SIZE,
    realtime: bool = False,
    streaming_delay_samples: int | None = None,
) -> ReplayResult:
    """
    Replay mono audio through ``enhancer`` using the live streaming path.

    Uses ``StreamingPipeline`` with in-memory fake I/O so chunking,
    ``process_stream()``, and a single ``flush()`` match the microphone
    pipeline behavior.
    """

    if sample_rate != enhancer.sample_rate():
        raise ValueError(
            f"Input sample rate ({sample_rate} Hz) does not match "
            f"enhancer sample rate ({enhancer.sample_rate()} Hz)."
        )

    chunks = split_into_chunks(input_audio, chunk_size)
    fake_input = FakeAudioInput(chunks, sample_rate)
    audio_input = (
        _RealtimeAudioInput(fake_input)
        if realtime
        else fake_input
    )
    audio_output = FakeAudioOutput(sample_rate)

    pipeline = StreamingPipeline(
        audio_input,
        audio_output,
        enhancer,
        read_chunk_size=chunk_size,
        instrumentation=True,
    )

    start = time.perf_counter()
    pipeline.run()
    elapsed_s = time.perf_counter() - start

    output_audio = audio_output.all_written()
    input_samples = int(len(input_audio))
    output_samples = int(len(output_audio))
    duration_seconds = (
        input_samples / sample_rate if sample_rate > 0 else 0.0
    )
    realtime_ratio = (
        duration_seconds / elapsed_s if elapsed_s > 0 else None
    )

    processing_time_s = 0.0

    if pipeline.instrumentation is not None:
        processing_time_s = pipeline.instrumentation.processing_time_s

    return ReplayResult(
        output_audio=output_audio,
        sample_rate=sample_rate,
        input_samples=input_samples,
        output_samples=output_samples,
        chunk_size=chunk_size,
        chunk_count=len(chunks),
        processing_time_s=processing_time_s,
        elapsed_s=elapsed_s,
        realtime_ratio=realtime_ratio,
        model=model_name,
        input_path=input_path,
        output_path=output_path,
        streaming_delay_samples=streaming_delay_samples,
    )


def replay_wav_file(
    input_path: Path,
    output_path: Path,
    enhancer: Enhancer,
    *,
    model_name: str,
    chunk_size: int | None = None,
    realtime: bool = False,
    streaming_delay_samples: int | None = None,
    write_metadata: bool = True,
) -> ReplayResult:
    """Load a WAV, replay it through ``enhancer``, and write output artifacts."""

    input_path = Path(input_path)
    output_path = Path(output_path)

    input_audio, sample_rate = load_mono_wav(input_path)

    resolved_chunk_size = chunk_size
    if resolved_chunk_size is None:
        resolved_chunk_size = (
            load_session_chunk_size(input_path)
            or DEFAULT_REPLAY_CHUNK_SIZE
        )

    result = replay_wav_through_enhancer(
        input_audio,
        sample_rate,
        enhancer,
        model_name=model_name,
        input_path=input_path.resolve(),
        output_path=output_path.resolve(),
        chunk_size=resolved_chunk_size,
        realtime=realtime,
        streaming_delay_samples=streaming_delay_samples,
    )

    save_mono_wav(output_path, result.output_audio, sample_rate)

    if write_metadata:
        metadata_path = output_path.with_suffix(".json")
        metadata_path.write_text(
            json.dumps(result.as_metadata(), indent=2) + "\n",
            encoding="utf-8",
        )

    return result
