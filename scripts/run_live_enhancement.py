import argparse
import sys
from pathlib import Path

from drdo_anc.audio.live import (
    StreamingPipeline,
    close_sounddevice_io,
    create_live_recorder,
    format_device_listing,
    open_sounddevice_io,
)
from drdo_anc.enhancement import create_enhancer, get_model_config, list_models


DEFAULT_MODEL_NAME = "DeepFilterNet3"
DEFAULT_READ_CHUNK_SIZE = 1024
DEFAULT_RECORD_DIR = Path("data") / "live_recordings"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Stream live microphone audio through a registered enhancer "
            "to the speaker. Use --passthrough to measure hardware latency "
            "without model inference."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Audio semantics\n"
            "-----------------\n"
            "Representation:\n"
            "  Host capture/playback uses float32 in [-1, 1].\n"
            "  AudioInput.read() returns mono float32 [T].\n"
            "  Stereo devices are opened at their native channel count;\n"
            "  capture is downmixed to mono and playback is upmixed.\n"
            "\n"
            "Recording:\n"
            "  --record-dir creates a timestamped session directory with\n"
            "  input.wav, enhanced.wav, and metadata.json. Recordings use\n"
            "  mono float32 WAV at the live sample rate with no benchmark\n"
            "  delay compensation applied.\n"
            "\n"
            "Sample rate:\n"
            "  Enhancement mode uses the selected model sample rate\n"
            "  (48 kHz for DeepFilterNet3).\n"
            "  Pass-through defaults to 48 kHz unless --sample-rate is set.\n"
            "\n"
            "Chunk sizes:\n"
            "  --chunk-size is the requested read size. Hardware may return\n"
            "  fewer samples. Chunks are forwarded directly to the enhancer.\n"
            "\n"
            "Device selection:\n"
            "  Use --list-devices to show PortAudio indices and host APIs.\n"
            "  Input and output share one duplex PortAudio stream.\n"
            "\n"
            "Shutdown:\n"
            "  Ctrl+C stops the stream. Enhancement mode calls flush() once.\n"
            "\n"
            "Diagnostics:\n"
            "  Use --diagnose-audio or scripts/test_live_passthrough.py."
        ),
    )

    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List host audio devices and exit.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL_NAME,
        choices=list_models(),
        help="Registered enhancer model name.",
    )
    parser.add_argument(
        "--passthrough",
        action="store_true",
        help="Copy microphone input directly to the speaker.",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=None,
        help="Audio sample rate in Hz.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_READ_CHUNK_SIZE,
        help="Samples requested per AudioInput.read() call.",
    )
    parser.add_argument(
        "--input-device",
        default=None,
        help="Input device index or name (sounddevice/PortAudio).",
    )
    parser.add_argument(
        "--output-device",
        default=None,
        help="Output device index or name (sounddevice/PortAudio).",
    )
    parser.add_argument(
        "--diagnose-audio",
        action="store_true",
        help="Print live stream diagnostics every second.",
    )
    parser.add_argument(
        "--record-dir",
        type=Path,
        default=None,
        help=(
            "Base directory for timestamped live recording sessions "
            "(input.wav, enhanced.wav, metadata.json)."
        ),
    )

    return parser


def _parse_device(value: str | None) -> int | str | None:
    if value is None:
        return None

    try:
        return int(value)
    except ValueError:
        return value


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.list_devices:
        print(format_device_listing())
        return

    if args.passthrough:
        sample_rate = args.sample_rate or 48_000
        enhancer = None
        mode_label = "pass-through"
        model_name = None
        streaming_delay_samples = None
    else:
        model_config = get_model_config(args.model)
        enhancer = create_enhancer(args.model)
        sample_rate = args.sample_rate or enhancer.sample_rate()
        mode_label = args.model
        model_name = args.model
        streaming_delay_samples = model_config.streaming_delay_samples

    if sample_rate <= 0:
        raise SystemExit("--sample-rate must be positive.")

    input_device = _parse_device(args.input_device)
    output_device = _parse_device(args.output_device)

    print("=" * 70)
    print("DRDO-ANC | Live Audio Streaming")
    print("=" * 70)
    print(f"Mode:        {mode_label}")
    print(f"Sample rate: {sample_rate} Hz")
    print(f"Chunk size:  {args.chunk_size} samples/read")
    print(f"Input dev:   {input_device if input_device is not None else 'default'}")
    print(
        f"Output dev:  {output_device if output_device is not None else 'default'}"
    )

    recorder = None

    if args.record_dir is not None:
        metadata_base = {
            "model": model_name,
            "mode": mode_label,
            "input_device": input_device,
            "output_device": output_device,
            "chunk_size": args.chunk_size,
        }

        if streaming_delay_samples is not None:
            metadata_base["streaming_delay_samples"] = (
                streaming_delay_samples
            )

        recorder = create_live_recorder(
            args.record_dir,
            sample_rate,
            metadata_base=metadata_base,
        )
        print(f"Recording input:    {recorder.paths.input_path}")
        print(f"Recording enhanced: {recorder.paths.enhanced_path}")
        print(f"Recording metadata: {recorder.paths.metadata_path}")

    print("\nPress Ctrl+C to stop.")
    print("=" * 70)

    audio_input, audio_output = open_sounddevice_io(
        sample_rate,
        input_device=input_device,
        output_device=output_device,
        blocksize=args.chunk_size,
    )

    print(
        f"Host capture channels:  {audio_input.host_input_channels}"
    )
    print(
        f"Host playback channels: {audio_output.host_output_channels}"
    )

    pipeline = StreamingPipeline(
        audio_input,
        audio_output,
        enhancer,
        read_chunk_size=args.chunk_size,
        recorder=recorder,
        passthrough=args.passthrough,
    )

    try:
        pipeline.run(diagnose=args.diagnose_audio)
    finally:
        close_sounddevice_io(audio_input, audio_output)

    if recorder is not None:
        if recorder.dropped_chunks > 0:
            print(
                f"\nWARNING: dropped {recorder.dropped_chunks} "
                "recording chunk(s) because the writer queue was full."
            )

        print(f"\nSaved recording session: {recorder.paths.session_dir}")

    print("\nStream finished.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
