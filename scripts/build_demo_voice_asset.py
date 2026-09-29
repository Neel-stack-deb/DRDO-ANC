#!/usr/bin/env python3
"""Prepare the default recorded-demo source and fine-tuned output asset."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

from drdo_anc.enhancement import create_enhancer

MAX_DURATION_SECONDS = 7.0
MODEL_NAME = "DeepFilterNet3-Finetuned"


def build(source: Path, enhanced: Path) -> None:
    audio, sample_rate = sf.read(source, dtype="float32")
    if audio.ndim == 2:
        audio = np.mean(audio, axis=1, dtype=np.float32)
    elif audio.ndim != 1:
        raise ValueError(f"Expected mono or stereo WAV, got shape {audio.shape}")

    enhancer = create_enhancer(MODEL_NAME)
    if sample_rate != enhancer.sample_rate():
        raise ValueError(
            f"Expected {enhancer.sample_rate()} Hz input, got {sample_rate} Hz"
        )

    max_samples = int(MAX_DURATION_SECONDS * sample_rate)
    audio = np.asarray(audio[:max_samples], dtype=np.float32)
    sf.write(source, audio, sample_rate)

    enhanced_audio = enhancer.process(torch.from_numpy(audio).unsqueeze(0))
    enhanced_array = enhanced_audio.squeeze(0).detach().cpu().numpy()
    enhanced.parent.mkdir(parents=True, exist_ok=True)
    sf.write(enhanced, enhanced_array, sample_rate)
    print(f"Source:   {source} ({len(audio) / sample_rate:.3f}s mono)")
    print(f"Enhanced: {enhanced}")
    print(f"Model:    {MODEL_NAME}")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=root / "data" / "raw" / "demo_voice.wav",
    )
    parser.add_argument(
        "--enhanced",
        type=Path,
        default=root / "data" / "generated" / "demo_voice_finetuned.wav",
    )
    args = parser.parse_args()
    build(args.source.resolve(), args.enhanced.resolve())


if __name__ == "__main__":
    main()
