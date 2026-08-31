"""Regression tests for the NLMS adaptive residual-noise filter core."""

from __future__ import annotations

import numpy as np

from drdo_anc.dsp import NLMSFilter


# Floating-point tolerance for streaming vs full-batch equivalence.
# Sample-by-sample NLMS is deterministic; tiny differences can appear from
# float32 accumulation order when comparing chunked vs contiguous runs.
STREAMING_RTOL = 1e-5
STREAMING_ATOL = 1e-6

CHUNK_SIZES = (1, 17, 128, 480, 1024, 2048)


def _sine_wave(
    length: int,
    frequency_hz: float,
    sample_rate: int = 16_000,
    *,
    amplitude: float = 1.0,
    phase: float = 0.0,
) -> np.ndarray:
    time = np.arange(length, dtype=np.float32) / np.float32(sample_rate)
    return (
        amplitude
        * np.sin(
            np.float32(2.0 * np.pi * frequency_hz) * time + np.float32(phase)
        )
    ).astype(np.float32)


def _signal_power(signal: np.ndarray) -> float:
    return float(np.mean(np.square(signal, dtype=np.float64)))


def _correlated_noise_scenario(
    length: int = 8_192,
    *,
    sample_rate: int = 16_000,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build deterministic speech + correlated-noise mixture."""

    speech = _sine_wave(length, 220.0, sample_rate, amplitude=0.35)
    noise = _sine_wave(length, 73.0, sample_rate, amplitude=0.55, phase=0.4)

    delay = 5
    gain = 0.85
    reference = np.zeros(length, dtype=np.float32)
    reference[delay:] = gain * noise[:-delay]

    # Mild deterministic amplitude modulation on the reference path.
    modulation = (
        1.0
        + 0.05
        * np.sin(
            np.float32(2.0 * np.pi * 3.0)
            * np.arange(length, dtype=np.float32)
            / np.float32(sample_rate)
        )
    ).astype(np.float32)
    reference *= modulation

    primary = (speech + noise).astype(np.float32)
    return speech, noise, primary, reference


def test_construction_and_configuration() -> None:
    filt = NLMSFilter(filter_length=64, step_size=0.05, epsilon=1e-7)

    assert filt.filter_length == 64
    assert filt.step_size == 0.05
    assert filt.epsilon == 1e-7
    assert filt.weights.shape == (64,)
    assert filt.weights.dtype == np.float32
    assert np.all(filt.weights == 0.0)


def test_mismatched_input_lengths_rejected() -> None:
    filt = NLMSFilter(filter_length=32)

    primary = np.ones(10, dtype=np.float32)
    reference = np.ones(9, dtype=np.float32)

    try:
        filt.process(primary, reference)
    except ValueError as exc:
        assert "same length" in str(exc)
    else:
        raise AssertionError("Expected ValueError for mismatched lengths")


def test_non_mono_inputs_rejected() -> None:
    filt = NLMSFilter(filter_length=16)

    try:
        filt.process(
            np.ones((4, 2), dtype=np.float32),
            np.ones(4, dtype=np.float32),
        )
    except ValueError as exc:
        assert "primary" in str(exc)
    else:
        raise AssertionError("Expected ValueError for non-mono primary")


def test_zero_reference_preserves_primary() -> None:
    rng = np.random.default_rng(7)
    primary = rng.standard_normal(4_096).astype(np.float32)

    filt = NLMSFilter(filter_length=128, step_size=0.2)
    output = filt.process(primary, np.zeros_like(primary))

    np.testing.assert_allclose(output, primary, rtol=1e-6, atol=1e-6)
    assert np.allclose(filt.weights, 0.0)


def test_correlated_noise_attenuation() -> None:
    rng = np.random.default_rng(11)
    speech, noise, primary, reference = _correlated_noise_scenario(rng=rng)

    filt = NLMSFilter(filter_length=256, step_size=0.3)
    output = filt.process(primary, reference)

    residual_noise = output - speech
    noise_power_before = _signal_power(noise)
    noise_power_after = _signal_power(residual_noise)

    assert noise_power_after < noise_power_before


def test_convergence_changes_weights_and_reduces_noise_power() -> None:
    rng = np.random.default_rng(23)
    speech, noise, primary, reference = _correlated_noise_scenario(
        length=16_384,
        rng=rng,
    )

    filt = NLMSFilter(filter_length=512, step_size=0.5)
    initial_weights = filt.weights.copy()

    output = filt.process(primary, reference)
    final_weights = filt.weights.copy()

    assert not np.allclose(initial_weights, final_weights)

    residual_noise = output - speech
    assert _signal_power(residual_noise) < _signal_power(noise)


def test_streaming_matches_full_processing() -> None:
    rng = np.random.default_rng(31)
    _, _, primary, reference = _correlated_noise_scenario(
        length=10_000,
        rng=rng,
    )

    full_filter = NLMSFilter(filter_length=128, step_size=0.25)
    full_output = full_filter.process(primary, reference)

    stream_filter = NLMSFilter(filter_length=128, step_size=0.25)
    chunks = (1, 17, 128, 480, 333, 1024, 2048, 512)
    stream_parts: list[np.ndarray] = []
    position = 0

    while position < len(primary):
        for chunk_size in chunks:
            if position >= len(primary):
                break

            end = min(position + chunk_size, len(primary))
            stream_parts.append(
                stream_filter.process(
                    primary[position:end],
                    reference[position:end],
                )
            )
            position = end

    stream_output = np.concatenate(stream_parts)

    np.testing.assert_allclose(
        stream_output,
        full_output,
        rtol=STREAMING_RTOL,
        atol=STREAMING_ATOL,
    )


def test_arbitrary_chunk_sizes() -> None:
    rng = np.random.default_rng(37)
    _, _, primary, reference = _correlated_noise_scenario(length=6_000, rng=rng)

    for chunk_size in CHUNK_SIZES:
        filt = NLMSFilter(filter_length=64, step_size=0.15)
        parts: list[np.ndarray] = []

        for start in range(0, len(primary), chunk_size):
            end = min(start + chunk_size, len(primary))
            parts.append(
                filt.process(
                    primary[start:end],
                    reference[start:end],
                )
            )

        output = np.concatenate(parts)
        assert output.shape == primary.shape
        assert output.dtype == np.float32
        assert np.isfinite(output).all()


def test_state_persists_across_chunks() -> None:
    rng = np.random.default_rng(41)
    _, _, primary, reference = _correlated_noise_scenario(length=2_048, rng=rng)

    continuous = NLMSFilter(filter_length=96, step_size=0.2)
    continuous_output = continuous.process(primary, reference)

    split_filter = NLMSFilter(filter_length=96, step_size=0.2)
    midpoint = 777
    first = split_filter.process(primary[:midpoint], reference[:midpoint])
    second = split_filter.process(primary[midpoint:], reference[midpoint:])
    split_output = np.concatenate([first, second])

    np.testing.assert_allclose(
        split_output,
        continuous_output,
        rtol=STREAMING_RTOL,
        atol=STREAMING_ATOL,
    )
    assert not np.allclose(split_filter.weights, 0.0)


def test_reset_matches_fresh_instance() -> None:
    rng = np.random.default_rng(43)
    _, _, primary, reference = _correlated_noise_scenario(length=3_000, rng=rng)

    fresh = NLMSFilter(filter_length=128, step_size=0.2)
    fresh_output = fresh.process(primary, reference)

    reused = NLMSFilter(filter_length=128, step_size=0.2)
    reused.process(primary, reference)
    reused.reset()
    reset_output = reused.process(primary, reference)

    np.testing.assert_allclose(
        reset_output,
        fresh_output,
        rtol=STREAMING_RTOL,
        atol=STREAMING_ATOL,
    )
    np.testing.assert_allclose(
        reused.weights,
        fresh.weights,
        rtol=STREAMING_RTOL,
        atol=STREAMING_ATOL,
    )


def test_zero_input_stability() -> None:
    filt = NLMSFilter(filter_length=128, step_size=0.5)

    zeros = np.zeros(2_048, dtype=np.float32)
    output = filt.process(zeros, zeros)

    assert np.all(output == 0.0)
    assert np.isfinite(filt.weights).all()
    assert np.max(np.abs(filt.weights)) < 1.0


def test_small_reference_stability() -> None:
    rng = np.random.default_rng(47)
    primary = rng.standard_normal(4_096).astype(np.float32) * np.float32(1e-4)
    reference = rng.standard_normal(4_096).astype(np.float32) * np.float32(1e-6)

    filt = NLMSFilter(filter_length=64, step_size=0.8, epsilon=1e-8)
    output = filt.process(primary, reference)

    assert np.isfinite(output).all()
    assert np.isfinite(filt.weights).all()
    assert np.max(np.abs(filt.weights)) < 10.0


def test_no_nan_or_inf_outputs() -> None:
    rng = np.random.default_rng(53)
    speech, _, primary, reference = _correlated_noise_scenario(length=5_000, rng=rng)

    filt = NLMSFilter(filter_length=256, step_size=0.4)
    output = filt.process(primary, reference)

    assert np.isfinite(output).all()
    assert np.isfinite(filt.weights).all()

    residual = output - speech
    assert _signal_power(residual) < _signal_power(primary)


def main() -> None:
    tests = [
        test_construction_and_configuration,
        test_mismatched_input_lengths_rejected,
        test_non_mono_inputs_rejected,
        test_zero_reference_preserves_primary,
        test_correlated_noise_attenuation,
        test_convergence_changes_weights_and_reduces_noise_power,
        test_streaming_matches_full_processing,
        test_arbitrary_chunk_sizes,
        test_state_persists_across_chunks,
        test_reset_matches_fresh_instance,
        test_zero_input_stability,
        test_small_reference_stability,
        test_no_nan_or_inf_outputs,
    ]

    print("=" * 70)
    print("DRDO-ANC | NLMS Adaptive Filter Tests")
    print("=" * 70)

    for test in tests:
        test()
        print(f"PASS: {test.__name__}")

    print("=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()
