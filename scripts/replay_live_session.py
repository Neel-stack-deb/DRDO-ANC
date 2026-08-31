import argparse
import sys
from pathlib import Path

from drdo_anc.audio.live.replay import (
    DEFAULT_REPLAY_CHUNK_SIZE,
    load_session_chunk_size,
    replay_wav_file,
)
from drdo_anc.enhancement import create_enhancer, get_model_config, list_models


DEFAULT_MODEL_NAME = "DeepFilterNet3"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Replay a recorded live input.wav through a registered enhancer "
            "using the same streaming path and arbitrary chunking behavior "
            "as the live microphone pipeline."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples\n"
            "--------\n"
            "  Fast replay (default):\n"
            "    .venv\\Scripts\\python.exe scripts/replay_live_session.py \\\n"
            "      --input data\\live_recordings\\<session>\\input.wav \\\n"
            "      --model DeepFilterNet3 \\\n"
            "      --output data\\live_recordings\\<session>\\replayed_df3.wav\n"
            "\n"
            "  Arbitrary chunk size:\n"
            "    .venv\\Scripts\\python.exe scripts/replay_live_session.py \\\n"
            "      --input ...\\input.wav --model DeepFilterNet3 \\\n"
            "      --output ...\\replayed_df3.wav --chunk-size 137\n"
            "\n"
            "  Real-time pacing:\n"
            "    .venv\\Scripts\\python.exe scripts/replay_live_session.py \\\n"
            "      --input ...\\input.wav --model DeepFilterNet3 \\\n"
            "      --output ...\\replayed_df3.wav --realtime\n"
            "\n"
            "Notes\n"
            "-----\n"
            "  Uses enhancer.process_stream() and a single flush() call.\n"
            "  Does not use enhancer.process() on the full waveform.\n"
            "  Streaming delay is not removed from the output WAV.\n"
            "  Writes a sibling .json metadata file next to the output WAV."
        ),
    )

    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to a mono float32 input.wav from a live session.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path for the replayed mono float32 output WAV.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL_NAME,
        choices=list_models(),
        help="Registered enhancer model name.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=None,
        help=(
            "Samples per streaming chunk. Defaults to the sibling session "
            f"metadata chunk_size, else {DEFAULT_REPLAY_CHUNK_SIZE}."
        ),
    )
    parser.add_argument(
        "--realtime",
        action="store_true",
        help=(
            "Pace chunk submission by each chunk's audio duration instead "
            "of processing as fast as possible."
        ),
    )

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if not args.input.is_file():
        raise SystemExit(f"Input file not found: {args.input}")

    if args.chunk_size is not None and args.chunk_size <= 0:
        raise SystemExit("--chunk-size must be positive.")

    model_config = get_model_config(args.model)
    enhancer = create_enhancer(args.model)

    chunk_size = args.chunk_size
    if chunk_size is None:
        chunk_size = (
            load_session_chunk_size(args.input)
            or DEFAULT_REPLAY_CHUNK_SIZE
        )

    print("=" * 70)
    print("DRDO-ANC | Live Session Replay")
    print("=" * 70)
    print(f"Model:       {args.model}")
    print(f"Input:       {args.input}")
    print(f"Output:      {args.output}")
    print(f"Chunk size:  {chunk_size} samples/read")
    print(
        f"Mode:        {'real-time' if args.realtime else 'fast'}"
    )
    print(
        "Delay:       "
        f"{model_config.streaming_delay_samples} samples "
        "(metadata only; not removed from output)"
    )
    print("=" * 70)

    result = replay_wav_file(
        args.input,
        args.output,
        enhancer,
        model_name=args.model,
        chunk_size=chunk_size,
        realtime=args.realtime,
        streaming_delay_samples=model_config.streaming_delay_samples,
    )

    metadata_path = args.output.with_suffix(".json")

    print(f"Input samples:    {result.input_samples}")
    print(f"Output samples:   {result.output_samples}")
    print(f"Chunks processed: {result.chunk_count}")
    print(f"Processing time:  {result.processing_time_s:.3f} s")
    print(f"Elapsed time:     {result.elapsed_s:.3f} s")

    if result.realtime_ratio is not None:
        print(f"Realtime ratio:   {result.realtime_ratio:.3f}")

    print(f"\nWrote output:     {args.output}")
    print(f"Wrote metadata:   {metadata_path}")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, ValueError) as exc:
        if isinstance(exc, KeyboardInterrupt):
            sys.exit(0)

        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
