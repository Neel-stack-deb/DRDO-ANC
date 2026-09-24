#!/usr/bin/env python3
"""Live Mode GUI controller tests (no hardware required)."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

src_dir = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(src_dir))

from drdo_anc.audio.live.fake import FakeAudioInput, FakeAudioOutput
from drdo_anc.gui.devices import (
    GuiAudioDevice,
    devices_from_records,
    input_devices,
    live_start_block_reason,
    output_devices,
    validate_live_sample_rate,
    validate_live_startup,
)
from drdo_anc.gui.live_controller import LiveAudioController
from drdo_anc.gui.live_state import (
    LIVE_STATUS_ERROR,
    LIVE_STATUS_IDLE,
    LIVE_STATUS_LIVE,
)


def _args(**overrides) -> argparse.Namespace:
    base = {
        "passthrough": False,
        "sample_rate": None,
        "chunk_size": 256,
        "model": "DeepFilterNet3-Finetuned",
        "input_device": None,
        "output_device": None,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


class _Bridge:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.live_status = LIVE_STATUS_IDLE
        self.overflows = 0

    def set_live_status(self, status: str) -> None:
        self.live_status = status

    def set_error(self, message: str) -> None:
        self.errors.append(message)

    def clear_error(self) -> None:
        self.errors.clear()

    def set_stream_metadata(self, **kwargs) -> None:
        return None

    def set_audio_status(self, status: str) -> None:
        return None

    def set_pipeline_stage(self, stage: str) -> None:
        return None

    def publish_data(self, *args, **kwargs) -> None:
        return None

    def set_live_input_overflows(self, count: int) -> None:
        self.overflows = count


class _SlowEnhancer:
    def sample_rate(self) -> int:
        return 48_000

    def load(self) -> None:
        return None

    def reset(self) -> None:
        return None

    def name(self) -> str:
        return "SlowEnhancer"

    def process_stream(self, audio_chunk):
        return audio_chunk

    def flush(self):
        import torch

        return torch.zeros(1, 0)


def _open_fake_io(
    sample_rate: int,
    *,
    input_device=None,
    output_device=None,
    blocksize: int,
):
    chunks = [np.zeros(blocksize, dtype=np.float32) for _ in range(2_000)]
    return FakeAudioInput(chunks, sample_rate=sample_rate), FakeAudioOutput(
        sample_rate
    )


def test_invalid_input_device_message() -> None:
    bogus_input = GuiAudioDevice(
        index=1,
        name="Speakers Only",
        hostapi_name="Windows WASAPI",
        max_input_channels=0,
        max_output_channels=2,
        default_sample_rate=48_000.0,
    )
    valid_output = GuiAudioDevice(
        index=2,
        name="Headphones",
        hostapi_name="Windows WASAPI",
        max_input_channels=0,
        max_output_channels=2,
        default_sample_rate=48_000.0,
    )
    reason = live_start_block_reason(
        bogus_input,
        valid_output,
        available_inputs=[bogus_input],
        available_outputs=[valid_output],
    )
    assert reason == "Selected input device is not an audio input."


def test_invalid_output_device_message() -> None:
    valid_input = GuiAudioDevice(
        index=1,
        name="Microphone",
        hostapi_name="Windows WASAPI",
        max_input_channels=2,
        max_output_channels=0,
        default_sample_rate=48_000.0,
    )
    bogus_output = GuiAudioDevice(
        index=2,
        name="Mic Only",
        hostapi_name="Windows WASAPI",
        max_input_channels=2,
        max_output_channels=0,
        default_sample_rate=48_000.0,
    )
    reason = live_start_block_reason(
        valid_input,
        bogus_output,
        available_inputs=[valid_input],
        available_outputs=[bogus_output],
    )
    assert reason == "Selected output device is not an audio output."


def test_validate_live_sample_rate_mismatch() -> None:
    reason, rate = validate_live_sample_rate(
        model_sample_rate=48_000,
        requested_sample_rate=44_100,
    )
    assert reason is not None
    assert "model boundary" in reason
    assert rate == 0


def test_start_stop_lifecycle() -> None:
    bridge = _Bridge()
    controller = LiveAudioController(
        _args(),
        bridge,
        open_io=_open_fake_io,
        create_enhancer=lambda _name: _SlowEnhancer(),
    )
    controller.start()
    assert bridge.live_status == LIVE_STATUS_LIVE
    controller.stop()
    assert bridge.live_status == LIVE_STATUS_IDLE
    assert controller._audio_thread is None


def test_repeated_start_is_idempotent() -> None:
    bridge = _Bridge()
    controller = LiveAudioController(
        _args(),
        bridge,
        open_io=_open_fake_io,
        create_enhancer=lambda _name: _SlowEnhancer(),
    )
    controller.start()
    controller.start()
    assert bridge.live_status == LIVE_STATUS_LIVE
    controller.stop()


def test_repeated_stop_is_idempotent() -> None:
    bridge = _Bridge()
    controller = LiveAudioController(
        _args(),
        bridge,
        open_io=_open_fake_io,
        create_enhancer=lambda _name: _SlowEnhancer(),
    )
    controller.stop()
    controller.stop()
    assert bridge.live_status == LIVE_STATUS_IDLE


def test_start_stop_start_cycle() -> None:
    bridge = _Bridge()
    controller = LiveAudioController(
        _args(),
        bridge,
        open_io=_open_fake_io,
        create_enhancer=lambda _name: _SlowEnhancer(),
    )
    for _ in range(3):
        controller.start()
        assert bridge.live_status == LIVE_STATUS_LIVE
        controller.stop()
    assert bridge.live_status == LIVE_STATUS_IDLE


def test_cleanup_after_open_failure() -> None:
    bridge = _Bridge()

    def _fail_open(*args, **kwargs):
        raise OSError("Error opening stream")

    controller = LiveAudioController(
        _args(),
        bridge,
        open_io=_fail_open,
        create_enhancer=lambda _name: _SlowEnhancer(),
    )
    controller.start()
    assert bridge.live_status == LIVE_STATUS_ERROR
    assert bridge.errors
    assert "unavailable" in bridge.errors[0].lower()
    controller.recover()
    assert bridge.live_status == LIVE_STATUS_IDLE
    assert bridge.errors == []


def test_error_recovery_allows_restart() -> None:
    bridge = _Bridge()
    calls = {"fail": True}

    def _maybe_fail_open(*args, **kwargs):
        if calls["fail"]:
            calls["fail"] = False
            raise RuntimeError("boom")
        return _open_fake_io(*args, **kwargs)

    controller = LiveAudioController(
        _args(),
        bridge,
        open_io=_maybe_fail_open,
        create_enhancer=lambda _name: _SlowEnhancer(),
    )
    controller.start()
    assert bridge.live_status == LIVE_STATUS_ERROR
    controller.recover()
    controller.start()
    assert bridge.live_status == LIVE_STATUS_LIVE
    controller.stop()


def test_validate_live_startup_ok() -> None:
    devices = devices_from_records(
        [
            {
                "index": 1,
                "name": "Mic",
                "max_input_channels": 2,
                "max_output_channels": 0,
                "default_sample_rate": 48000.0,
                "hostapi": 0,
                "hostapi_name": "Windows WASAPI",
            },
            {
                "index": 2,
                "name": "Phones",
                "max_input_channels": 0,
                "max_output_channels": 2,
                "default_sample_rate": 48000.0,
                "hostapi": 0,
                "hostapi_name": "Windows WASAPI",
            },
        ]
    )
    mic = input_devices(devices)[0]
    out = output_devices(devices)[0]
    reason, rate = validate_live_startup(
        mic,
        out,
        available_inputs=input_devices(devices),
        available_outputs=output_devices(devices),
        model_sample_rate=48_000,
    )
    assert reason is None
    assert rate == 48_000


def main() -> int:
    tests = [
        test_invalid_input_device_message,
        test_invalid_output_device_message,
        test_validate_live_sample_rate_mismatch,
        test_start_stop_lifecycle,
        test_repeated_start_is_idempotent,
        test_repeated_stop_is_idempotent,
        test_start_stop_start_cycle,
        test_cleanup_after_open_failure,
        test_error_recovery_allows_restart,
        test_validate_live_startup_ok,
    ]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    print(f"\nAll {len(tests)} live controller tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
