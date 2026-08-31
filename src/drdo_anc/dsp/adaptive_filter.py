"""NLMS adaptive residual-noise filter (DSP core).

This module implements a stateful Normalized Least Mean Squares (NLMS)
FIR filter for adaptive noise cancellation when a reference signal is
available. It is **not** a complete acoustic ANC system: a suitable
reference channel is required, and single-microphone prototype integration
is a later stage.
"""

from __future__ import annotations

import numpy as np


class NLMSFilter:
    """Stateful NLMS adaptive residual-noise filter.

    Models the standard adaptive-noise-cancellation formulation::

        reference x[n] -> adaptive FIR -> estimated noise y[n]
        primary d[n] - y[n] -> error e[n] (desired output)

    Coefficients update with the normalized LMS rule using a small
    ``epsilon`` stability term in the normalization denominator.

    Parameters
    ----------
    filter_length:
        Number of FIR taps. Default ``128``.
    step_size:
        Adaptation step size (``mu``). Default ``0.1``.
    epsilon:
        Positive normalization floor to avoid division by zero.
        Default ``1e-8``.
    """

    def __init__(
        self,
        filter_length: int = 128,
        step_size: float = 0.1,
        epsilon: float = 1e-8,
    ) -> None:
        if filter_length <= 0:
            raise ValueError("filter_length must be positive.")
        if step_size <= 0.0:
            raise ValueError("step_size must be positive.")
        if epsilon <= 0.0:
            raise ValueError("epsilon must be positive.")

        self._filter_length = int(filter_length)
        self._step_size = float(step_size)
        self._epsilon = float(epsilon)

        self._weights = np.zeros(
            self._filter_length,
            dtype=np.float32,
        )
        self._ref_buffer = np.zeros(
            self._filter_length,
            dtype=np.float32,
        )

    @property
    def filter_length(self) -> int:
        return self._filter_length

    @property
    def step_size(self) -> float:
        return self._step_size

    @property
    def epsilon(self) -> float:
        return self._epsilon

    @property
    def weights(self) -> np.ndarray:
        """Copy of the current adaptive FIR coefficients."""

        return self._weights.copy()

    def reset(self) -> None:
        """Clear filter state without changing configuration."""

        self._weights.fill(0.0)
        self._ref_buffer.fill(0.0)

    def process(
        self,
        primary: np.ndarray,
        reference: np.ndarray,
    ) -> np.ndarray:
        """Process one mono chunk while preserving internal state.

        Parameters
        ----------
        primary:
            Primary signal ``d[n]``, shape ``[T]``, ``float32``.
        reference:
            Reference signal ``x[n]``, shape ``[T]``, ``float32``.

        Returns
        -------
        np.ndarray
            Error signal ``e[n]`` (residual output), shape ``[T]``,
            ``float32``.
        """

        primary = self._validate_signal(primary, name="primary")
        reference = self._validate_signal(reference, name="reference")

        if primary.shape[0] != reference.shape[0]:
            raise ValueError(
                "primary and reference must have the same length: "
                f"{primary.shape[0]} != {reference.shape[0]}"
            )

        if primary.size == 0:
            return np.empty(0, dtype=np.float32)

        output = np.empty(primary.shape[0], dtype=np.float32)

        for index in range(primary.shape[0]):
            output[index] = self._process_sample(
                float(primary[index]),
                float(reference[index]),
            )

        return output

    def _process_sample(self, primary_sample: float, reference_sample: float) -> float:
        self._ref_buffer[1:] = self._ref_buffer[:-1]
        self._ref_buffer[0] = reference_sample

        estimated_noise = float(np.dot(self._weights, self._ref_buffer))
        error = primary_sample - estimated_noise

        norm = float(np.dot(self._ref_buffer, self._ref_buffer)) + self._epsilon
        self._weights += (
            (self._step_size * error / norm) * self._ref_buffer
        ).astype(np.float32)

        return error

    @staticmethod
    def _validate_signal(signal: np.ndarray, *, name: str) -> np.ndarray:
        array = np.asarray(signal, dtype=np.float32)

        if array.ndim != 1:
            raise ValueError(
                f"{name} must be mono audio with shape [T], got shape {array.shape}"
            )

        return array
