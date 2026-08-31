"""
Two-microphone reference architecture for future AI + NLMS processing.

Signal model
------------
Primary microphone captures speech plus environmental noise. A reference
microphone is positioned to capture correlated environmental noise while
minimizing direct speech pickup. Both microphones connect to the same
synchronized multi-channel audio interface.

Intended future processing chain (not integrated yet)::

    Primary microphone
           |
           v
      AI enhancer  (existing ``Enhancer`` implementations)
           |
           v
       residual
           |
           v
        NLMS  <----- Reference microphone
           |
           v
        Output

This is **not** a complete acoustic ANC system. A useful reference signal
must be validated experimentally before NLMS integration. Channel assignment
(primary vs reference) is configuration — never hardcoded in hardware
backends.

Architecture layers::

    Raw multi-channel capture  [T, C]
            |
            v
      channel routing  (``MultiMicConfig`` + ``ChannelRouter``)
            |
            v
    Primary [T]  +  Reference [T]
            |
            v
    processing pipeline  (mono ``StreamingPipeline`` today; hybrid later)

The existing mono live path remains unchanged::

    ``AudioInput`` -> mono -> ``Enhancer`` -> ``AudioOutput``

Use ``MultiChannelAudioInput`` and ``ChannelRouter`` for dual-microphone
capture experiments. ``RoutedPrimaryAudioInput`` adapts multi-channel capture
to the existing mono ``AudioInput`` interface when only the primary channel
should feed the current pipeline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np

from .interfaces import AudioInput


@dataclass(frozen=True)
class MultiMicConfig:
    """Configuration for synchronized dual-microphone capture.

    Channel indices are zero-based positions in the hardware capture buffer.
    They are **not** assumed to be ``0=primary`` and ``1=reference`` — callers
    must set ``primary_channel`` and ``reference_channel`` explicitly for each
    device layout.

    Parameters
    ----------
    sample_rate:
        Capture sample rate in Hz. Default ``48000``.
    input_device:
        PortAudio input device index or name. ``None`` uses the host default.
    output_device:
        Reserved for future duplex dual-mic + playback scenarios. Not used by
        the input-only capture path.
    input_channels:
        Number of synchronized channels opened on the input stream. Must be
        large enough to include both configured channel indices. Default ``2``.
    primary_channel:
        Index of the primary microphone channel in the capture buffer.
    reference_channel:
        Index of the reference microphone channel in the capture buffer.
    blocksize:
        PortAudio block size hint. Default ``1024``.
    """

    sample_rate: int = 48_000
    input_device: int | str | None = None
    output_device: int | str | None = None
    input_channels: int = 2
    primary_channel: int = 0
    reference_channel: int = 1
    blocksize: int = 1024

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Raise ``ValueError`` when configuration is inconsistent."""

        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be positive.")
        if self.input_channels < 1:
            raise ValueError("input_channels must be positive.")
        if self.blocksize <= 0:
            raise ValueError("blocksize must be positive.")

        for name, index in (
            ("primary_channel", self.primary_channel),
            ("reference_channel", self.reference_channel),
        ):
            if index < 0 or index >= self.input_channels:
                raise ValueError(
                    f"{name}={index} is out of range for "
                    f"input_channels={self.input_channels}."
                )

        if self.primary_channel == self.reference_channel:
            raise ValueError(
                "primary_channel and reference_channel must differ."
            )


class MultiChannelAudioInput(ABC):
    """Hardware-independent synchronized multi-channel capture."""

    @abstractmethod
    def sample_rate(self) -> int:
        """Return the capture sample rate in Hz."""

    @abstractmethod
    def channel_count(self) -> int:
        """Return the number of synchronized capture channels."""

    @abstractmethod
    def read(self, max_samples: int) -> np.ndarray:
        """
        Read up to ``max_samples`` frames of multi-channel float32 audio.

        Returns shape ``[T, C]`` where ``C == channel_count()``. An empty
        array with shape ``[0, C]`` signals end-of-stream.
        """

    @abstractmethod
    def close(self) -> None:
        """Release capture resources."""


class ChannelRouter:
    """Extract configured primary and reference channels from capture buffers."""

    def __init__(self, config: MultiMicConfig) -> None:
        config.validate()
        self._config = config

    @property
    def config(self) -> MultiMicConfig:
        return self._config

    def route(
        self,
        multichannel: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Split ``[T, C]`` capture data into primary and reference mono signals.

        Returns mono float32 arrays ``(primary, reference)`` each with shape
        ``[T]``. Length is preserved from the input time dimension.
        """

        array = _validate_multichannel(multichannel)

        if array.shape[1] < self._config.input_channels:
            raise ValueError(
                f"Expected at least {self._config.input_channels} channels, "
                f"got shape {array.shape}."
            )

        primary = array[:, self._config.primary_channel].astype(
            np.float32,
            copy=False,
        )
        reference = array[:, self._config.reference_channel].astype(
            np.float32,
            copy=False,
        )

        return primary, reference


class RoutedPrimaryAudioInput(AudioInput):
    """
    Adapt ``MultiChannelAudioInput`` to the mono ``AudioInput`` interface.

    Only the configured primary channel is exposed. The reference channel
    remains available via ``read_multichannel()`` for future hybrid stages.
    """

    def __init__(
        self,
        source: MultiChannelAudioInput,
        router: ChannelRouter,
    ) -> None:
        if source.sample_rate() != router.config.sample_rate:
            raise ValueError(
                "MultiChannelAudioInput sample rate does not match "
                f"MultiMicConfig: {source.sample_rate()} != "
                f"{router.config.sample_rate}."
            )

        if source.channel_count() != router.config.input_channels:
            raise ValueError(
                "MultiChannelAudioInput channel count does not match "
                f"MultiMicConfig: {source.channel_count()} != "
                f"{router.config.input_channels}."
            )

        self._source = source
        self._router = router
        self._last_multichannel = np.empty(
            (0, source.channel_count()),
            dtype=np.float32,
        )
        self._closed = False

    def sample_rate(self) -> int:
        return self._source.sample_rate()

    @property
    def last_multichannel(self) -> np.ndarray:
        """Most recent raw capture chunk, shape ``[T, C]``."""

        return self._last_multichannel

    def read_multichannel(self, max_samples: int) -> np.ndarray:
        if self._closed:
            raise RuntimeError("AudioInput is closed.")

        multichannel = self._source.read(max_samples)
        self._last_multichannel = multichannel
        return multichannel

    def read(self, max_samples: int) -> np.ndarray:
        multichannel = self.read_multichannel(max_samples)

        if multichannel.size == 0:
            return np.empty(0, dtype=np.float32)

        primary, _reference = self._router.route(multichannel)
        return primary

    def close(self) -> None:
        if self._closed:
            return

        self._closed = True
        self._source.close()


@dataclass(frozen=True)
class ChannelPairAnalysis:
    """Offline statistics for a routed primary/reference pair."""

    sample_rate: int
    num_samples: int
    duration_s: float
    channel_count: int
    primary_channel: int
    reference_channel: int
    primary_rms: float
    reference_rms: float
    primary_peak: float
    reference_peak: float
    correlation: float
    relative_delay_samples: int
    relative_delay_ms: float

    def as_dict(self) -> dict[str, float | int]:
        return {
            "sample_rate": self.sample_rate,
            "channel_count": self.channel_count,
            "num_samples": self.num_samples,
            "duration_s": self.duration_s,
            "primary_channel": self.primary_channel,
            "reference_channel": self.reference_channel,
            "primary_rms": self.primary_rms,
            "reference_rms": self.reference_rms,
            "primary_peak": self.primary_peak,
            "reference_peak": self.reference_peak,
            "correlation": self.correlation,
            "relative_delay_samples": self.relative_delay_samples,
            "relative_delay_ms": self.relative_delay_ms,
        }


@dataclass(frozen=True)
class DualMicResidualFrame:
    """
    Future integration point for AI + NLMS hybrid processing.

    After AI enhancement of the primary microphone, ``NLMSFilter.process()``
    can use ``enhanced_primary`` as the primary input and ``reference`` as the
    reference input. Both arrays must be the same length and ``float32``.
    """

    enhanced_primary: np.ndarray
    reference: np.ndarray

    def __post_init__(self) -> None:
        primary = np.asarray(self.enhanced_primary, dtype=np.float32)
        reference = np.asarray(self.reference, dtype=np.float32)

        if primary.ndim != 1 or reference.ndim != 1:
            raise ValueError(
                "DualMicResidualFrame expects mono float32 arrays with "
                f"shape [T]; got {primary.shape} and {reference.shape}."
            )

        if primary.shape[0] != reference.shape[0]:
            raise ValueError(
                "enhanced_primary and reference must have the same length: "
                f"{primary.shape[0]} != {reference.shape[0]}."
            )


def _validate_multichannel(multichannel: np.ndarray) -> np.ndarray:
    array = np.asarray(multichannel, dtype=np.float32)

    if array.ndim != 2:
        raise ValueError(
            f"Expected multi-channel audio with shape [T, C], got {array.shape}."
        )

    if array.shape[0] == 0:
        channels = array.shape[1] if array.ndim == 2 else 0
        return np.empty((0, channels), dtype=np.float32)

    return array


def compute_rms(signal: np.ndarray) -> float:
    array = np.asarray(signal, dtype=np.float64).reshape(-1)

    if array.size == 0:
        return 0.0

    return float(np.sqrt(np.mean(np.square(array))))


def compute_peak(signal: np.ndarray) -> float:
    array = np.asarray(signal, dtype=np.float32).reshape(-1)

    if array.size == 0:
        return 0.0

    return float(np.max(np.abs(array)))


def compute_correlation(
    primary: np.ndarray,
    reference: np.ndarray,
) -> float:
    """Pearson correlation between two mono signals of equal length."""

    a = np.asarray(primary, dtype=np.float64).reshape(-1)
    b = np.asarray(reference, dtype=np.float64).reshape(-1)

    if a.shape[0] != b.shape[0]:
        raise ValueError("primary and reference must have the same length.")

    if a.size == 0:
        return 0.0

    a = a - np.mean(a)
    b = b - np.mean(b)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))

    if denom == 0.0:
        return 0.0

    return float(np.dot(a, b) / denom)


def estimate_relative_delay_samples(
    primary: np.ndarray,
    reference: np.ndarray,
    *,
    max_delay_samples: int | None = None,
) -> int:
    """
    Estimate the integer sample lag that best aligns reference to primary.

    Returns a positive value when reference leads primary (reference energy
    appears earlier in time). Returns a negative value when reference lags
    primary. Returns ``0`` when signals are uncorrelated or empty.
    """

    a = np.asarray(primary, dtype=np.float64).reshape(-1)
    b = np.asarray(reference, dtype=np.float64).reshape(-1)

    if a.size == 0 or b.size == 0:
        return 0

    if a.shape[0] != b.shape[0]:
        raise ValueError("primary and reference must have the same length.")

    if max_delay_samples is None:
        max_delay_samples = min(512, max(1, a.size // 4))

    max_delay_samples = max(0, int(max_delay_samples))

    a = a - np.mean(a)
    b = b - np.mean(b)

    if np.linalg.norm(a) == 0.0 or np.linalg.norm(b) == 0.0:
        return 0

    correlation = np.correlate(a, b, mode="full")
    center = len(correlation) // 2
    low = max(0, center - max_delay_samples)
    high = min(len(correlation), center + max_delay_samples + 1)
    window = correlation[low:high]
    lag_index = low + int(np.argmax(window))

    return lag_index - center


def analyze_channel_pair(
    primary: np.ndarray,
    reference: np.ndarray,
    config: MultiMicConfig,
    *,
    max_delay_samples: int | None = None,
) -> ChannelPairAnalysis:
    """Compute routed-channel statistics for experiment reporting."""

    primary = np.asarray(primary, dtype=np.float32).reshape(-1)
    reference = np.asarray(reference, dtype=np.float32).reshape(-1)

    if primary.shape[0] != reference.shape[0]:
        raise ValueError("primary and reference must have the same length.")

    delay = estimate_relative_delay_samples(
        primary,
        reference,
        max_delay_samples=max_delay_samples,
    )

    num_samples = int(primary.shape[0])
    duration_s = (
        num_samples / config.sample_rate if config.sample_rate > 0 else 0.0
    )

    return ChannelPairAnalysis(
        sample_rate=config.sample_rate,
        num_samples=num_samples,
        duration_s=duration_s,
        channel_count=config.input_channels,
        primary_channel=config.primary_channel,
        reference_channel=config.reference_channel,
        primary_rms=compute_rms(primary),
        reference_rms=compute_rms(reference),
        primary_peak=compute_peak(primary),
        reference_peak=compute_peak(reference),
        correlation=compute_correlation(primary, reference),
        relative_delay_samples=delay,
        relative_delay_ms=1000.0 * delay / config.sample_rate,
    )
