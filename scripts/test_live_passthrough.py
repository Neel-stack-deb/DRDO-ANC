import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from drdo_anc.audio import save_mono_wav
from drdo_anc.audio.live import (
    StreamingPipeline,
    SoundDeviceDuplexSession,
    close_sounddevice_io,
    format_device_listing,
    open_sounddevice_io,
)
from drdo_anc.audio.live.sounddevice_backend import (
    _device_channel_count,
    _import_sounddevice,
    upmix_mono_to_channels,
)


DEFAULT_SAMPLE_RATE = 48_000
DEFAULT_CHUNK_SIZE = 1024


def _parse_device(value: str | None) -> int | str | None:
    if value is None:
        return None

    try:
        return int(value)
    except ValueError:
        return value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Hardware live-audio diagnostics for passthrough debugging."
        ),
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List host audio devices and exit.",
    )
    parser.add_argument(
        "--mode",
        choices=["passthrough", "pipeline", "sine", "capture"],
        default="passthrough",
        help=(
            "passthrough: minimal duplex read/write loop; "
            "pipeline: StreamingPipeline pass-through; "
            "sine: 440 Hz tone to output; "
            "capture: record microphone to WAV without playback."
        ),
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=DEFAULT_SAMPLE_RATE,
        help="Audio sample rate in Hz.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help="Samples per read/write block.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=5.0,
        help="Run duration in seconds for timed modes.",
    )
    parser.add_argument(
        "--input-device",
        default=None,
        help="Input device index or name.",
    )
    parser.add_argument(
        "--output-device",
        default=None,
        help="Output device index or name.",
    )
    parser.add_argument(
        "--output-wav",
        type=Path,
        default=Path("data/live_capture.wav"),
        help="Output WAV path for capture mode.",
    )
    return parser


def _print_stats(payload: dict) -> None:
    print(json.dumps(payload, indent=2), flush=True)


def run_minimal_passthrough(
    session: SoundDeviceDuplexSession,
    *,
    chunk_size: int,
    duration_s: float,
) -> None:
    """Direct duplex read/write without StreamingPipeline."""

    frames_target = int(session.sample_rate * duration_s)
    frames_done = 0

    print("Mode: minimal duplex passthrough")
    print(
        "dtype=float32 range=[-1, 1] "
        f"host_in={session.input_channels} "
        f"host_out={session.output_channels}"
    )

    while frames_done < frames_target:
        mono, overflowed = session.read_mono(chunk_size)

        if overflowed:
            print("INPUT OVERFLOW", flush=True)

        if mono.size == 0:
            break

        session.write_mono(mono)
        frames_done += mono.size

    session.stats.mark_stop()
    _print_stats(session.stats.as_dict())


def run_pipeline_passthrough(
    *,
    sample_rate: int,
    input_device,
    output_device,
    chunk_size: int,
    duration_s: float,
) -> None:
    audio_input, audio_output = open_sounddevice_io(
        sample_rate,
        input_device=input_device,
        output_device=output_device,
        blocksize=chunk_size,
    )

    print("Mode: StreamingPipeline pass-through")

    pipeline = StreamingPipeline(
        audio_input,
        audio_output,
        enhancer=None,
        read_chunk_size=chunk_size,
    )

    max_chunks = int(
        (duration_s * sample_rate) / chunk_size
    ) + 1

    try:
        pipeline.run(
            diagnose=True,
            diagnose_interval_s=1.0,
            max_chunks=max_chunks,
        )
    finally:
        close_sounddevice_io(audio_input, audio_output)
        _print_stats(audio_input.stats.as_dict())


def run_sine_output(
    *,
    sample_rate: int,
    output_device,
    chunk_size: int,
    duration_s: float,
    frequency: float = 440.0,
) -> None:
    """Generated sine wave directly to output (no microphone)."""

    sd = _import_sounddevice()
    channels = _device_channel_count(output_device, "output")

    print("Mode: generated sine -> output")
    print(
        f"dtype=float32 range=[-1, 1] host_out={channels}"
    )

    stream = sd.OutputStream(
        samplerate=sample_rate,
        device=output_device,
        channels=channels,
        dtype="float32",
        blocksize=chunk_size,
        latency="high",
    )

    frames_target = int(sample_rate * duration_s)
    frames_done = 0
    phase = 0.0
    amplitude = 0.2

    stream.start()

    try:
        while frames_done < frames_target:
            count = min(chunk_size, frames_target - frames_done)
            t = (
                phase
                + np.arange(count, dtype=np.float32)
            ) / sample_rate
            mono = (
                amplitude
                * np.sin(2.0 * np.pi * frequency * t, dtype=np.float32)
            )
            stream.write(
                upmix_mono_to_channels(mono, channels),
            )
            phase += count
            frames_done += count
    finally:
        stream.stop()
        stream.close()

    print(
        json.dumps(
            {
                "samples_written": frames_done,
                "sample_rate": sample_rate,
                "output_channels": channels,
                "dtype": "float32",
            },
            indent=2,
        )
    )


def run_capture_wav(
    *,
    sample_rate: int,
    input_device,
    chunk_size: int,
    duration_s: float,
    output_path: Path,
) -> None:
    """Capture microphone only and save to WAV."""

    sd = _import_sounddevice()
    channels = _device_channel_count(input_device, "input")

    print(f"Mode: microphone capture -> {output_path}")
    print(
        f"dtype=float32 range=[-1, 1] host_in={channels}"
    )

    stream = sd.InputStream(
        samplerate=sample_rate,
        device=input_device,
        channels=channels,
        dtype="float32",
        blocksize=chunk_size,
        latency="high",
    )

    frames_target = int(sample_rate * duration_s)
    frames_done = 0
    chunks: list[np.ndarray] = []
    overflows = 0

    stream.start()

    try:
        while frames_done < frames_target:
            data, overflowed = stream.read(chunk_size)

            if overflowed:
                overflows += 1
                print("INPUT OVERFLOW", flush=True)

            mono = np.asarray(data, dtype=np.float32)

            if mono.ndim == 2:
                mono = mono.mean(axis=1)

            mono = mono.reshape(-1)

            if mono.size == 0:
                break

            chunks.append(mono.copy())
            frames_done += mono.size
    finally:
        stream.stop()
        stream.close()

    if chunks:
        audio = np.concatenate(chunks)
        save_mono_wav(output_path, audio, sample_rate)
        print(f"Wrote {len(audio)} samples to {output_path}")

    _print_stats(
        {
            "samples_read": frames_done,
            "sample_rate": sample_rate,
            "input_channels": channels,
            "input_overflows": overflows,
            "dtype": "float32",
        }
    )


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.list_devices:
        print(format_device_listing())
        return

    input_device = _parse_device(args.input_device)
    output_device = _parse_device(args.output_device)

    if args.mode == "pipeline":
        run_pipeline_passthrough(
            sample_rate=args.sample_rate,
            input_device=input_device,
            output_device=output_device,
            chunk_size=args.chunk_size,
            duration_s=args.duration,
        )
        return

    if args.mode == "sine":
        run_sine_output(
            sample_rate=args.sample_rate,
            output_device=output_device,
            chunk_size=args.chunk_size,
            duration_s=args.duration,
        )
        return

    if args.mode == "capture":
        run_capture_wav(
            sample_rate=args.sample_rate,
            input_device=input_device,
            chunk_size=args.chunk_size,
            duration_s=args.duration,
            output_path=args.output_wav,
        )
        return

    session = SoundDeviceDuplexSession(
        args.sample_rate,
        input_device=input_device,
        output_device=output_device,
        blocksize=args.chunk_size,
    )

    try:
        run_minimal_passthrough(
            session,
            chunk_size=args.chunk_size,
            duration_s=args.duration,
        )
    finally:
        session.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
