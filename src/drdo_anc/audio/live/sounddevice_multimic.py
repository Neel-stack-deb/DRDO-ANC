from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from .multimic import (
    ChannelPairAnalysis,
    ChannelRouter,
    MultiChannelAudioInput,
    MultiMicConfig,
    analyze_channel_pair,
)
from .sounddevice_backend import _import_sounddevice


@dataclass
class DualMicCaptureResult:
    """Synchronized dual-microphone capture with routed channels."""

    config: MultiMicConfig
    multichannel: np.ndarray
    primary: np.ndarray
    reference: np.ndarray
    analysis: ChannelPairAnalysis | None
    input_overflows: int
    elapsed_s: float


class SoundDeviceMultiChannelInput(MultiChannelAudioInput):
    """
    Desktop multi-channel capture via one PortAudio input stream.

    All channels share the same device clock. Channel routing is **not**
    performed here — use ``ChannelRouter`` on returned ``[T, C]`` buffers.
    """

    def __init__(self, config: MultiMicConfig) -> None:
        config.validate()

        sd = _import_sounddevice()

        self._config = config
        self._closed = False
        self._started = False
        self._input_overflows = 0

        self._stream = sd.InputStream(
            samplerate=config.sample_rate,
            device=config.input_device,
            channels=config.input_channels,
            dtype="float32",
            blocksize=config.blocksize,
            latency="high",
        )

    @property
    def config(self) -> MultiMicConfig:
        return self._config

    @property
    def input_overflows(self) -> int:
        return self._input_overflows

    def sample_rate(self) -> int:
        return self._config.sample_rate

    def channel_count(self) -> int:
        return self._config.input_channels

    def _ensure_started(self) -> None:
        if self._closed:
            raise RuntimeError("MultiChannelAudioInput is closed.")

        if not self._started:
            self._stream.start()
            self._started = True

    def read(self, max_samples: int) -> np.ndarray:
        if self._closed:
            raise RuntimeError("MultiChannelAudioInput is closed.")

        if max_samples <= 0:
            return np.empty(
                (0, self.channel_count()),
                dtype=np.float32,
            )

        self._ensure_started()

        data, overflowed = self._stream.read(max_samples)
        array = np.asarray(data, dtype=np.float32)

        if array.ndim == 1:
            array = array.reshape(-1, 1)

        if overflowed:
            self._input_overflows += 1

        return array

    def close(self) -> None:
        if self._closed:
            return

        if self._started:
            self._stream.stop()

        self._stream.close()
        self._closed = True


class FakeMultiChannelAudioInput(MultiChannelAudioInput):
    """In-memory multi-channel input for synthetic tests."""

    def __init__(
        self,
        chunks: list[np.ndarray],
        *,
        sample_rate: int,
        channel_count: int,
    ) -> None:
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive.")
        if channel_count < 1:
            raise ValueError("channel_count must be positive.")

        self._chunks = [
            np.asarray(chunk, dtype=np.float32)
            for chunk in chunks
        ]
        self._sample_rate = sample_rate
        self._channel_count = channel_count
        self._index = 0
        self._closed = False

        for index, chunk in enumerate(self._chunks):
            if chunk.ndim != 2 or chunk.shape[1] != channel_count:
                raise ValueError(
                    f"Chunk {index} must have shape [T, {channel_count}], "
                    f"got {chunk.shape}."
                )

    def sample_rate(self) -> int:
        return self._sample_rate

    def channel_count(self) -> int:
        return self._channel_count

    def read(self, max_samples: int) -> np.ndarray:
        if self._closed:
            raise RuntimeError("MultiChannelAudioInput is closed.")

        if max_samples <= 0:
            return np.empty(
                (0, self._channel_count),
                dtype=np.float32,
            )

        if self._index >= len(self._chunks):
            return np.empty(
                (0, self._channel_count),
                dtype=np.float32,
            )

        chunk = self._chunks[self._index]
        self._index += 1
        return chunk.astype(np.float32, copy=False)

    def close(self) -> None:
        self._closed = True


def record_dual_microphone(
    config: MultiMicConfig,
    duration_s: float,
    *,
    read_chunk_size: int | None = None,
    on_progress: Callable[[int, int, float], None] | None = None,
    defer_analysis: bool = False,
) -> DualMicCaptureResult:
    """
    Capture synchronized multi-channel audio for a fixed duration.

    Both channels are acquired from one input stream on the same device
    clock. Routed primary and reference channels are extracted via
    ``ChannelRouter``.
    """

    if duration_s <= 0.0:
        raise ValueError("duration_s must be positive.")

    chunk_size = (
        read_chunk_size
        if read_chunk_size is not None
        else config.blocksize
    )

    if chunk_size <= 0:
        raise ValueError("read_chunk_size must be positive.")

    router = ChannelRouter(config)
    capture = SoundDeviceMultiChannelInput(config)

    frames_target = int(config.sample_rate * duration_s)
    frames_done = 0
    chunks: list[np.ndarray] = []
    start = time.perf_counter()

    try:
        while frames_done < frames_target:
            chunk = capture.read(chunk_size)

            if chunk.size == 0:
                break

            chunks.append(chunk.copy())
            frames_done += int(chunk.shape[0])

            if on_progress is not None:
                on_progress(
                    frames_done,
                    frames_target,
                    time.perf_counter() - start,
                )
    finally:
        capture.close()

    elapsed_s = time.perf_counter() - start

    if chunks:
        multichannel = np.concatenate(chunks, axis=0)
    else:
        multichannel = np.empty(
            (0, config.input_channels),
            dtype=np.float32,
        )

    primary, reference = router.route(multichannel)
    analysis = (
        None
        if defer_analysis
        else analyze_channel_pair(primary, reference, config)
    )

    return DualMicCaptureResult(
        config=config,
        multichannel=multichannel,
        primary=primary,
        reference=reference,
        analysis=analysis,
        input_overflows=capture.input_overflows,
        elapsed_s=elapsed_s,
    )
