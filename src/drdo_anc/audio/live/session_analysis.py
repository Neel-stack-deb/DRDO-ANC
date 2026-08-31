from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from drdo_anc.audio.io import load_mono_wav
from drdo_anc.evaluation.delay import apply_evaluation_delay


@dataclass(frozen=True)
class EnergyDropWindow:
    """Time window where enhanced energy is unusually low vs input."""

    start_s: float
    end_s: float
    input_energy_db: float
    enhanced_energy_db: float
    gain_db: float


def _rms_energy_db(audio: np.ndarray) -> float:
    if audio.size == 0:
        return float("-inf")

    rms = float(np.sqrt(np.mean(np.square(audio), dtype=np.float64)))

    if rms <= 0.0:
        return float("-inf")

    return float(20.0 * np.log10(rms))


def find_energy_drop_windows(
    input_audio: np.ndarray,
    enhanced_audio: np.ndarray,
    sample_rate: int,
    *,
    delay_samples: int,
    window_ms: float = 50.0,
    hop_ms: float = 25.0,
    drop_threshold_db: float = -12.0,
    min_input_energy_db: float = -50.0,
) -> list[EnergyDropWindow]:
    """
    Find windows where delay-compensated enhanced energy drops far below input.

    ``delay_samples`` is the configured model streaming delay used for offline
    evaluation alignment. It is applied here so input and enhanced are compared
    on the same timeline without modifying the recorded WAV files.
    """

    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive.")

    if window_ms <= 0 or hop_ms <= 0:
        raise ValueError("window_ms and hop_ms must be positive.")

    input_aligned, _, enhanced_aligned = apply_evaluation_delay(
        input_audio,
        input_audio,
        enhanced_audio,
        delay_samples,
    )

    window_samples = max(1, int(round(sample_rate * window_ms / 1000.0)))
    hop_samples = max(1, int(round(sample_rate * hop_ms / 1000.0)))

    windows: list[EnergyDropWindow] = []

    for start in range(0, len(input_aligned) - window_samples + 1, hop_samples):
        end = start + window_samples
        input_window = input_aligned[start:end]
        enhanced_window = enhanced_aligned[start:end]

        input_energy_db = _rms_energy_db(input_window)
        enhanced_energy_db = _rms_energy_db(enhanced_window)
        gain_db = enhanced_energy_db - input_energy_db

        if (
            input_energy_db >= min_input_energy_db
            and gain_db <= drop_threshold_db
        ):
            windows.append(
                EnergyDropWindow(
                    start_s=start / sample_rate,
                    end_s=end / sample_rate,
                    input_energy_db=input_energy_db,
                    enhanced_energy_db=enhanced_energy_db,
                    gain_db=gain_db,
                )
            )

    return windows


def load_live_session_metadata(session_dir: Path) -> dict:
    metadata_path = session_dir / "metadata.json"

    if not metadata_path.is_file():
        raise FileNotFoundError(
            f"Missing metadata.json in session directory: {session_dir}"
        )

    return json.loads(metadata_path.read_text(encoding="utf-8"))


def resolve_delay_samples(
    metadata: dict,
    *,
    delay_samples: int | None,
) -> int:
    if delay_samples is not None:
        return delay_samples

    if "streaming_delay_samples" in metadata:
        return int(metadata["streaming_delay_samples"])

    alignment = metadata.get("recording_alignment", {})

    if "streaming_delay_samples" in alignment:
        return int(alignment["streaming_delay_samples"])

    raise ValueError(
        "No delay_samples provided and metadata does not contain "
        "streaming_delay_samples."
    )


def analyze_live_session(
    session_dir: Path,
    *,
    delay_samples: int | None = None,
    window_ms: float = 50.0,
    hop_ms: float = 25.0,
    drop_threshold_db: float = -12.0,
    min_input_energy_db: float = -50.0,
) -> dict:
    """Analyze a live recording session directory."""

    session_dir = Path(session_dir)
    metadata = load_live_session_metadata(session_dir)

    input_path = session_dir / metadata.get("input_path", "input.wav")
    enhanced_path = session_dir / metadata.get(
        "enhanced_path",
        "enhanced.wav",
    )

    input_audio, sample_rate = load_mono_wav(input_path)
    enhanced_audio, enhanced_sr = load_mono_wav(enhanced_path)

    if enhanced_sr != sample_rate:
        raise ValueError(
            f"Sample rate mismatch: input={sample_rate}, "
            f"enhanced={enhanced_sr}"
        )

    resolved_delay = resolve_delay_samples(
        metadata,
        delay_samples=delay_samples,
    )

    windows = find_energy_drop_windows(
        input_audio,
        enhanced_audio,
        sample_rate,
        delay_samples=resolved_delay,
        window_ms=window_ms,
        hop_ms=hop_ms,
        drop_threshold_db=drop_threshold_db,
        min_input_energy_db=min_input_energy_db,
    )

    return {
        "session_dir": str(session_dir),
        "sample_rate": sample_rate,
        "delay_samples": resolved_delay,
        "input_samples": len(input_audio),
        "enhanced_samples": len(enhanced_audio),
        "lengths_match": len(input_audio) == len(enhanced_audio),
        "window_ms": window_ms,
        "hop_ms": hop_ms,
        "drop_threshold_db": drop_threshold_db,
        "min_input_energy_db": min_input_energy_db,
        "drop_window_count": len(windows),
        "drop_windows": [asdict(window) for window in windows],
        "metadata": metadata,
    }
