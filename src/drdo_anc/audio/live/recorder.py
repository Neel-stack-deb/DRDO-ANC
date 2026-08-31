from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from drdo_anc.audio.io import load_mono_wav, save_mono_wav

from .alignment import RecordingLengthTracker

DEFAULT_QUEUE_CAPACITY = 256


@dataclass
class LiveInstrumentation:
    """Per-chunk live pipeline measurements."""

    chunk_count: int = 0
    input_samples: int = 0
    output_samples: int = 0
    processing_time_s: float = 0.0
    elapsed_s: float = 0.0
    input_overflows: int | None = None
    dropped_recording_chunks: int = 0
    _start_time: float | None = field(default=None, repr=False)

    def mark_start(self) -> None:
        self._start_time = time.perf_counter()

    def mark_stop(self) -> None:
        if self._start_time is not None:
            self.elapsed_s = time.perf_counter() - self._start_time

    def add_input_chunk(self, num_samples: int) -> None:
        self.chunk_count += 1
        self.input_samples += num_samples

    def add_enhanced_chunk(
        self,
        num_samples: int,
        *,
        processing_time_s: float = 0.0,
    ) -> None:
        self.output_samples += num_samples
        self.processing_time_s += processing_time_s

    def as_dict(self, *, sample_rate: int) -> dict:
        duration_seconds = (
            self.input_samples / sample_rate
            if sample_rate > 0
            else 0.0
        )
        realtime_ratio = (
            duration_seconds / self.elapsed_s
            if self.elapsed_s > 0
            else None
        )

        payload = {
            "chunk_count": self.chunk_count,
            "input_samples": self.input_samples,
            "output_samples": self.output_samples,
            "processing_time_s": self.processing_time_s,
            "elapsed_s": self.elapsed_s,
            "duration_seconds": duration_seconds,
            "realtime_ratio": realtime_ratio,
            "dropped_recording_chunks": self.dropped_recording_chunks,
        }

        if self.input_overflows is not None:
            payload["input_overflows"] = self.input_overflows

        return payload


@dataclass(frozen=True)
class LiveRecordingPaths:
    session_dir: Path
    input_path: Path
    enhanced_path: Path
    metadata_path: Path


def create_live_session_dir(base_dir: Path) -> Path:
    """Create a unique timestamped session directory under ``base_dir``."""

    base_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    session_dir = base_dir / stamp

    if not session_dir.exists():
        session_dir.mkdir(parents=True, exist_ok=False)
        return session_dir

    suffix = 1

    while True:
        candidate = base_dir / f"{stamp}_{suffix:02d}"

        if not candidate.exists():
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate

        suffix += 1


class LiveStreamRecorder:
    """
    Asynchronous mono WAV recorder for live pipeline observability.

    Audio chunks are enqueued from the real-time path and written to disk
    by a background worker thread. If the bounded queue fills up, chunks are
    dropped and counted rather than blocking playback.
    """

    def __init__(
        self,
        session_dir: Path,
        sample_rate: int,
        *,
        queue_capacity: int = DEFAULT_QUEUE_CAPACITY,
        metadata_base: dict | None = None,
    ) -> None:
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive.")

        self._session_dir = session_dir
        self._sample_rate = sample_rate
        self._metadata_base = dict(metadata_base or {})
        self._queue: queue.Queue[tuple[str, np.ndarray | None]] = (
            queue.Queue(maxsize=queue_capacity)
        )
        self._thread: threading.Thread | None = None
        self._started = False
        self._finalized = False
        self._dropped_chunks = 0
        self._input_samples_written = 0
        self._enhanced_samples_written = 0
        self._worker_error: Exception | None = None
        self.length_tracker = RecordingLengthTracker()

        self.paths = LiveRecordingPaths(
            session_dir=session_dir,
            input_path=session_dir / "input.wav",
            enhanced_path=session_dir / "enhanced.wav",
            metadata_path=session_dir / "metadata.json",
        )

    @property
    def dropped_chunks(self) -> int:
        return self._dropped_chunks

    def start(self) -> None:
        if self._started:
            raise RuntimeError("Recorder is already started.")

        self._session_dir.mkdir(parents=True, exist_ok=True)
        self._thread = threading.Thread(
            target=self._worker,
            name="live-stream-recorder",
            daemon=True,
        )
        self._thread.start()
        self._started = True

    def write_input(self, audio: np.ndarray) -> None:
        array = np.asarray(audio, dtype=np.float32).reshape(-1)

        if array.size > 0:
            self.length_tracker.note_input(int(array.size))

        self._enqueue("input", audio)

    def write_enhanced(self, audio: np.ndarray) -> None:
        array = np.asarray(audio, dtype=np.float32).reshape(-1)

        if array.size > 0:
            self.length_tracker.note_enhanced(int(array.size))

        self._enqueue("enhanced", audio)

    def note_flush_enhanced(self, audio: np.ndarray) -> None:
        array = np.asarray(audio, dtype=np.float32).reshape(-1)

        if array.size > 0:
            self.length_tracker.note_flush(int(array.size))
            self._enqueue("enhanced", array)

    def finalize(
        self,
        instrumentation: LiveInstrumentation | None = None,
        *,
        passthrough: bool = False,
        extra_metadata: dict | None = None,
    ) -> LiveRecordingPaths:
        if self._finalized:
            return self.paths

        if self._started:
            self._enqueue("stop", None)
            assert self._thread is not None
            self._thread.join(timeout=10.0)

            if self._thread.is_alive():
                raise RuntimeError(
                    "Recording worker did not stop in time."
                )

        if self._worker_error is not None:
            raise RuntimeError(
                "Recording worker failed."
            ) from self._worker_error

        alignment = align_recorded_streams(
            input_path=self.paths.input_path,
            enhanced_path=self.paths.enhanced_path,
            sample_rate=self._sample_rate,
            tracker=self.length_tracker,
            passthrough=passthrough,
            streaming_delay_samples=self._metadata_base.get(
                "streaming_delay_samples",
            ),
            input_samples_written=self._input_samples_written,
            enhanced_samples_written=self._enhanced_samples_written,
        )

        if alignment["action"] == "prepend_enhanced_leading_silence":
            self._enhanced_samples_written += alignment[
                "samples_padded"
            ]

        metadata = self._build_metadata(
            instrumentation,
            extra_metadata,
            alignment=alignment,
        )

        if (
            metadata["input_samples_recorded"]
            != metadata["enhanced_samples_recorded"]
        ):
            with self.paths.metadata_path.open(
                "w",
                encoding="utf-8",
            ) as handle:
                json.dump(metadata, handle, indent=2)
                handle.write("\n")

            raise RuntimeError(
                "Recording length alignment failed: "
                f"input={metadata['input_samples_recorded']}, "
                f"enhanced={metadata['enhanced_samples_recorded']}. "
                f"See recording_alignment in metadata."
            )

        with self.paths.metadata_path.open(
            "w",
            encoding="utf-8",
        ) as handle:
            json.dump(metadata, handle, indent=2)
            handle.write("\n")

        self._finalized = True
        return self.paths

    def _enqueue(self, stream: str, audio: np.ndarray | None) -> None:
        if self._finalized:
            return

        if audio is not None:
            array = np.asarray(audio, dtype=np.float32).reshape(-1)

            if array.size == 0:
                return

            item = (stream, array.copy())
        else:
            item = (stream, None)

        if not self._started:
            raise RuntimeError(
                "Recorder is not started. Call start() first."
            )

        try:
            self._queue.put_nowait(item)
        except queue.Full:
            self._dropped_chunks += 1

    def _worker(self) -> None:
        try:
            with (
                sf.SoundFile(
                    self.paths.input_path,
                    mode="w",
                    samplerate=self._sample_rate,
                    channels=1,
                    subtype="FLOAT",
                ) as input_file,
                sf.SoundFile(
                    self.paths.enhanced_path,
                    mode="w",
                    samplerate=self._sample_rate,
                    channels=1,
                    subtype="FLOAT",
                ) as enhanced_file,
            ):
                while True:
                    stream, audio = self._queue.get()

                    if stream == "stop":
                        break

                    assert audio is not None

                    if stream == "input":
                        input_file.write(audio)
                        self._input_samples_written += len(audio)
                    elif stream == "enhanced":
                        enhanced_file.write(audio)
                        self._enhanced_samples_written += len(audio)
                    else:
                        raise ValueError(
                            f"Unknown recording stream: {stream}"
                        )
        except Exception as exc:
            self._worker_error = exc
            raise

    def _build_metadata(
        self,
        instrumentation: LiveInstrumentation | None,
        extra_metadata: dict | None,
        *,
        alignment: dict[str, Any] | None = None,
    ) -> dict:
        metadata = {
            "sample_rate": self._sample_rate,
            "format": "mono float32 WAV",
            "range": "[-1.0, 1.0]",
            "input_path": self.paths.input_path.name,
            "enhanced_path": self.paths.enhanced_path.name,
            "input_samples_recorded": self._input_samples_written,
            "enhanced_samples_recorded": self._enhanced_samples_written,
            "dropped_recording_chunks": self._dropped_chunks,
            "recording_length_tracker": self.length_tracker.as_dict(),
        }
        metadata.update(self._metadata_base)

        if alignment is not None:
            metadata["recording_alignment"] = alignment

        if instrumentation is not None:
            instrumentation.dropped_recording_chunks = (
                self._dropped_chunks
            )
            metadata.update(
                instrumentation.as_dict(
                    sample_rate=self._sample_rate,
                )
            )

        if extra_metadata:
            metadata.update(extra_metadata)

        return metadata


def create_live_recorder(
    base_dir: Path,
    sample_rate: int,
    *,
    metadata_base: dict | None = None,
) -> LiveStreamRecorder:
    """Create a recorder in a new timestamped session directory."""

    session_dir = create_live_session_dir(base_dir)

    recorder = LiveStreamRecorder(
        session_dir,
        sample_rate,
        metadata_base=metadata_base,
    )
    recorder.start()

    return recorder


def align_recorded_streams(
    *,
    input_path: Path,
    enhanced_path: Path,
    sample_rate: int,
    tracker: RecordingLengthTracker,
    passthrough: bool,
    streaming_delay_samples: int | None,
    input_samples_written: int,
    enhanced_samples_written: int,
) -> dict[str, Any]:
    """
    Align ``enhanced.wav`` to ``input.wav`` when lifecycle metrics prove it.

    Padding is applied only when the post-flush deficit equals the stable
    leading gap observed after the first non-empty enhanced chunk.
    """

    deficit = input_samples_written - enhanced_samples_written
    result: dict[str, Any] = {
        "status": "aligned",
        "action": "none",
        "samples_padded": 0,
        "deficit_samples_before_alignment": deficit,
        "tracker": tracker.as_dict(),
    }

    if streaming_delay_samples is not None:
        result["streaming_delay_samples"] = streaming_delay_samples

    if deficit == 0:
        return result

    if passthrough:
        result.update(
            {
                "status": "mismatch",
                "action": "none",
                "reason": (
                    "Pass-through mode requires equal input and "
                    "enhanced sample counts."
                ),
            }
        )
        return result

    if not tracker.saw_enhanced:
        result.update(
            {
                "status": "mismatch",
                "action": "none",
                "reason": "No enhanced samples were produced.",
            }
        )
        return result

    if not tracker.gap_stable:
        result.update(
            {
                "status": "mismatch",
                "action": "none",
                "reason": (
                    "Input/enhanced length gap was not stable before "
                    "alignment."
                ),
            }
        )
        return result

    leading_deficit = tracker.leading_deficit()

    if (
        leading_deficit is None
        or deficit != leading_deficit
        or tracker.gap_after_last_output != deficit
    ):
        result.update(
            {
                "status": "mismatch",
                "action": "none",
                "reason": (
                    "Post-flush deficit does not match the stable "
                    "leading gap observed during streaming."
                ),
            }
        )
        return result

    enhanced_audio, enhanced_sr = load_mono_wav(enhanced_path)

    if enhanced_sr != sample_rate:
        raise ValueError(
            f"Enhanced sample rate mismatch: {enhanced_sr} != {sample_rate}"
        )

    padded = np.concatenate(
        [
            np.zeros(deficit, dtype=np.float32),
            enhanced_audio.astype(np.float32, copy=False),
        ]
    )
    save_mono_wav(enhanced_path, padded, sample_rate)

    result.update(
        {
            "status": "aligned",
            "action": "prepend_enhanced_leading_silence",
            "samples_padded": deficit,
            "reason": (
                "Stable leading gap after first enhanced output; "
                "prepended silence to enhanced.wav so both recordings "
                "span the same sample timeline after flush()."
            ),
        }
    )

    return result
