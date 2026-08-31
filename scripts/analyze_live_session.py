import argparse
import json
import sys
from pathlib import Path

from drdo_anc.audio.live.session_analysis import analyze_live_session


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze a live recording session: align input/enhanced with the "
            "configured model delay and report windows where enhanced energy "
            "drops unusually far below input energy."
        ),
    )

    parser.add_argument(
        "session_dir",
        type=Path,
        help="Path to a live session directory containing WAVs and metadata.",
    )
    parser.add_argument(
        "--delay-samples",
        type=int,
        default=None,
        help=(
            "Model streaming delay in samples. Defaults to "
            "metadata.streaming_delay_samples."
        ),
    )
    parser.add_argument(
        "--window-ms",
        type=float,
        default=50.0,
        help="Analysis window length in milliseconds.",
    )
    parser.add_argument(
        "--hop-ms",
        type=float,
        default=25.0,
        help="Hop size between analysis windows in milliseconds.",
    )
    parser.add_argument(
        "--drop-threshold-db",
        type=float,
        default=-12.0,
        help=(
            "Report windows where enhanced minus input energy is at or "
            "below this value (dB)."
        ),
    )
    parser.add_argument(
        "--min-input-energy-db",
        type=float,
        default=-50.0,
        help="Ignore windows where input energy is below this level (dB).",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Optional path to write the full analysis report as JSON.",
    )

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    report = analyze_live_session(
        args.session_dir,
        delay_samples=args.delay_samples,
        window_ms=args.window_ms,
        hop_ms=args.hop_ms,
        drop_threshold_db=args.drop_threshold_db,
        min_input_energy_db=args.min_input_energy_db,
    )

    print("=" * 70)
    print("DRDO-ANC | Live Session Analysis")
    print("=" * 70)
    print(f"Session:          {report['session_dir']}")
    print(f"Sample rate:      {report['sample_rate']} Hz")
    print(f"Delay samples:    {report['delay_samples']}")
    print(
        f"Input samples:    {report['input_samples']} "
        f"({report['input_samples'] / report['sample_rate']:.3f} s)"
    )
    print(
        f"Enhanced samples: {report['enhanced_samples']} "
        f"({report['enhanced_samples'] / report['sample_rate']:.3f} s)"
    )
    print(f"Lengths match:    {report['lengths_match']}")
    print(f"Drop windows:     {report['drop_window_count']}")

    if report["drop_window_count"] == 0:
        print("\nNo unusual enhanced energy drops detected.")
    else:
        print("\nUnusual enhanced energy drops:")
        print("-" * 70)

        for window in report["drop_windows"]:
            print(
                f"{window['start_s']:8.3f}s - {window['end_s']:8.3f}s | "
                f"input {window['input_energy_db']:6.1f} dB | "
                f"enhanced {window['enhanced_energy_db']:6.1f} dB | "
                f"gain {window['gain_db']:6.1f} dB"
            )

    if args.output_json is not None:
        payload = dict(report)
        payload.pop("metadata", None)
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\nWrote JSON report: {args.output_json}")

    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
