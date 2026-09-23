#!/usr/bin/env python3
"""Job 4: demo preflight, emergency reset, and live fallback tests."""

from __future__ import annotations

import argparse
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

src_dir = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(src_dir))

from drdo_anc.enhancement.finetuned import FINETUNED_MODEL_NAME
from drdo_anc.gui.demo_preflight import run_demo_preflight
from drdo_anc.gui.devices import devices_from_records
from drdo_anc.gui.live_state import LIVE_STATUS_ERROR, LIVE_STATUS_IDLE, LIVE_STATUS_LIVE
from drdo_anc.gui.preflight_state import (
    PREFLIGHT_FAILED,
    PREFLIGHT_READY,
    PREFLIGHT_WARNING,
)
from drdo_anc.gui.session import ApplicationSession


def _record(
    index: int,
    name: str,
    *,
    ins: int = 0,
    outs: int = 0,
) -> dict:
    return {
        "index": index,
        "name": name,
        "max_input_channels": ins,
        "max_output_channels": outs,
        "default_sample_rate": 48000.0,
        "hostapi": 2,
        "hostapi_name": "Windows WASAPI",
    }


def _devices():
    records = [
        _record(1, "Mic", ins=1),
        _record(2, "Phones", outs=2),
    ]
    all_dev = devices_from_records(records)
    inputs = [d for d in all_dev if d.is_input]
    outputs = [d for d in all_dev if d.is_output]
    return inputs[0], outputs[0], inputs, outputs


@dataclass
class _FakeCatalog:
    scenarios: list


class _BridgeProbe:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.preflight: dict = {}
        self.fallback_offered = False
        self.fallback_message = ""
        self._live_fallback_offered = False
        self.operation_mode = "demo"
        self.live_status = LIVE_STATUS_IDLE
        self.demo_status = "IDLE"
        self.devices_locked = False
        self.playback_state = "stopped"
        self.audio_status = ""
        self.pipeline_stage = ""
        self.live_overflows = 0

    def set_error(self, message: str) -> None:
        self.errors.append(message)

    def clear_error(self) -> None:
        self.errors.clear()

    def offer_live_fallback(self, message: str, *, kind: str = "live") -> None:
        self.fallback_offered = True
        self.fallback_message = message
        self._live_fallback_offered = True

    def clear_live_fallback(self) -> None:
        self.fallback_offered = False
        self.fallback_message = ""
        self._live_fallback_offered = False

    def set_preflight_checking(self) -> None:
        self.preflight["checking"] = True

    def set_preflight_report(self, *, status: str, summary: str, check_lines: list[str]) -> None:
        self.preflight = {
            "status": status,
            "summary": summary,
            "check_lines": check_lines,
        }

    def set_operation_mode(self, mode: str) -> None:
        self.operation_mode = mode

    def set_live_status(self, status: str) -> None:
        self.live_status = status

    def set_demo_status(self, status: str) -> None:
        self.demo_status = status

    def set_devices_locked(self, locked: bool) -> None:
        self.devices_locked = locked

    def set_playback_state(self, state: str) -> None:
        self.playback_state = state

    def set_audio_status(self, status: str) -> None:
        self.audio_status = status

    def set_pipeline_stage(self, stage: str) -> None:
        self.pipeline_stage = stage

    def set_live_input_overflows(self, count: int) -> None:
        self.live_overflows = count

    def set_live_device_summaries(self, **kwargs) -> None:
        return None

    def set_stream_metadata(self, **kwargs) -> None:
        return None

    def set_device_choices(self, **kwargs) -> None:
        return None


class _LiveProbe:
    def __init__(self, state: str = LIVE_STATUS_IDLE) -> None:
        self.state = state
        self.stop_calls = 0
        self.recover_calls = 0
        self.start_calls = 0

    @property
    def is_started(self) -> bool:
        return self.state in {LIVE_STATUS_LIVE, "STARTING", "STOPPING"}

    def stop(self) -> None:
        self.stop_calls += 1
        self.state = LIVE_STATUS_IDLE

    def recover(self) -> None:
        self.recover_calls += 1
        self.state = LIVE_STATUS_IDLE

    def start(self) -> None:
        self.start_calls += 1

    def set_devices(self, **kwargs) -> None:
        return None

    def set_model_name(self, name: str) -> None:
        return None


class _DemoProbe:
    def __init__(self) -> None:
        self.stop_calls = 0
        self.reset_calls = 0
        self.ab_modes: list[str] = []

    def stop(self) -> None:
        self.stop_calls += 1

    def reset(self) -> None:
        self.reset_calls += 1

    def set_ab_mode(self, mode: str) -> None:
        self.ab_modes.append(mode)

    def set_output_device(self, _device) -> None:
        return None


def _session_stub(**overrides) -> ApplicationSession:
    session = ApplicationSession.__new__(ApplicationSession)
    session._bridge = overrides.get("bridge", _BridgeProbe())
    session._live_controller = overrides.get("live", _LiveProbe())
    session._demo_controller = overrides.get("demo", _DemoProbe())
    session._mode = overrides.get("mode", "live")
    session._selected_model = overrides.get("model", FINETUNED_MODEL_NAME)
    session._args = overrides.get(
        "args",
        argparse.Namespace(
            passthrough=False,
            sample_rate=None,
            chunk_size=256,
            model=FINETUNED_MODEL_NAME,
            input_device=None,
            output_device=None,
        ),
    )
    session._selected_input = overrides.get("selected_input")
    session._selected_output = overrides.get("selected_output")
    session._input_choices = overrides.get("input_choices", [])
    session._output_choices = overrides.get("output_choices", [])
    return session


def test_preflight_all_pass_with_mocks() -> None:
    mic, phones, inputs, outputs = _devices()
    scenario = type("S", (), {"wav_path": Path("exists.wav")})()
    scenario.wav_path = Path(__file__)

    def catalog_loader():
        return _FakeCatalog([scenario])

    def model_probe(_name: str):
        return True, ""

    def io_probe(_sr, _in, _out):
        return True, ""

    with tempfile.TemporaryDirectory() as tmp:
        bench_root = Path(tmp)
        dev = bench_root / "dfn3_finetuned_compare"
        dev.mkdir(parents=True)
        (dev / "pretrained_full.json").write_text("{}", encoding="utf-8")
        (dev / "finetuned_full.json").write_text("{}", encoding="utf-8")

        report = run_demo_preflight(
            selected_input=mic,
            selected_output=phones,
            available_inputs=inputs,
            available_outputs=outputs,
            catalog_loader=catalog_loader,
            model_probe=model_probe,
            io_probe=io_probe,
            benchmark_root=bench_root,
            skip_io_probe=True,
        )

    assert report.status == PREFLIGHT_READY
    assert report.summary == "DEMO READY"
    assert report.demo_audio_ready
    assert all(check.passed for check in report.checks)


def test_preflight_missing_input_device() -> None:
    _, phones, _, outputs = _devices()
    report = run_demo_preflight(
        selected_input=None,
        selected_output=phones,
        available_inputs=[],
        available_outputs=outputs,
        model_probe=lambda _n: (True, ""),
        skip_io_probe=True,
        catalog_loader=lambda: _FakeCatalog([]),
    )
    assert report.status == PREFLIGHT_FAILED
    input_check = next(c for c in report.checks if c.check_id == "input_device")
    assert not input_check.passed


def test_preflight_invalid_input_role() -> None:
    records = [_record(1, "Speaker only", outs=2), _record(2, "Phones", outs=2)]
    all_dev = devices_from_records(records)
    outputs = [d for d in all_dev if d.is_output]
    bad_input = all_dev[0]
    report = run_demo_preflight(
        selected_input=bad_input,
        selected_output=outputs[0],
        available_inputs=[bad_input],
        available_outputs=outputs,
        model_probe=lambda _n: (True, ""),
        skip_io_probe=True,
        catalog_loader=lambda: _FakeCatalog([]),
    )
    input_check = next(c for c in report.checks if c.check_id == "input_device")
    assert not input_check.passed
    assert "not an audio input" in input_check.detail.lower()


def test_preflight_missing_output_device() -> None:
    mic, _, inputs, _ = _devices()
    report = run_demo_preflight(
        selected_input=mic,
        selected_output=None,
        available_inputs=inputs,
        available_outputs=[],
        model_probe=lambda _n: (True, ""),
        skip_io_probe=True,
        catalog_loader=lambda: _FakeCatalog([]),
    )
    output_check = next(c for c in report.checks if c.check_id == "output_device")
    assert not output_check.passed


def test_preflight_invalid_output_role() -> None:
    records = [_record(1, "Mic only", ins=1), _record(2, "Mic two", ins=1)]
    all_dev = devices_from_records(records)
    inputs = [d for d in all_dev if d.is_input]
    bad_output = all_dev[1]
    report = run_demo_preflight(
        selected_input=inputs[0],
        selected_output=bad_output,
        available_inputs=inputs,
        available_outputs=[bad_output],
        model_probe=lambda _n: (True, ""),
        skip_io_probe=True,
        catalog_loader=lambda: _FakeCatalog([]),
    )
    output_check = next(c for c in report.checks if c.check_id == "output_device")
    assert not output_check.passed


def test_preflight_missing_model() -> None:
    mic, phones, inputs, outputs = _devices()
    report = run_demo_preflight(
        selected_input=mic,
        selected_output=phones,
        available_inputs=inputs,
        available_outputs=outputs,
        model_probe=lambda _n: (False, "not registered"),
        skip_io_probe=True,
        catalog_loader=lambda: _FakeCatalog(
            [type("S", (), {"wav_path": Path(__file__)})()],
        ),
    )
    model_check = next(c for c in report.checks if c.check_id == "finetuned_model")
    assert not model_check.passed


def test_preflight_model_init_failure() -> None:
    mic, phones, inputs, outputs = _devices()
    report = run_demo_preflight(
        selected_input=mic,
        selected_output=phones,
        available_inputs=inputs,
        available_outputs=outputs,
        model_probe=lambda _n: (False, "Model configuration failed: broken"),
        skip_io_probe=True,
        catalog_loader=lambda: _FakeCatalog(
            [type("S", (), {"wav_path": Path(__file__)})()],
        ),
    )
    assert report.status == PREFLIGHT_FAILED


def test_preflight_missing_demo_asset() -> None:
    mic, phones, inputs, outputs = _devices()
    missing = type("S", (), {})()
    missing.wav_path = Path("/nonexistent/demo.wav")
    report = run_demo_preflight(
        selected_input=mic,
        selected_output=phones,
        available_inputs=inputs,
        available_outputs=outputs,
        model_probe=lambda _n: (True, ""),
        skip_io_probe=True,
        catalog_loader=lambda: _FakeCatalog([missing]),
    )
    demo_check = next(c for c in report.checks if c.check_id == "demo_audio")
    assert not demo_check.passed


def test_preflight_benchmark_warning_only() -> None:
    mic, phones, inputs, outputs = _devices()
    scenario = type("S", (), {"wav_path": Path(__file__)})()
    with tempfile.TemporaryDirectory() as tmp:
        report = run_demo_preflight(
            selected_input=mic,
            selected_output=phones,
            available_inputs=inputs,
            available_outputs=outputs,
            model_probe=lambda _n: (True, ""),
            skip_io_probe=True,
            catalog_loader=lambda: _FakeCatalog([scenario]),
            benchmark_root=Path(tmp),
        )
    assert report.status == PREFLIGHT_WARNING
    assert report.summary == "DEMO READY"
    assert report.demo_audio_ready
    bench = next(c for c in report.checks if c.check_id == "benchmark_results")
    assert not bench.passed


def test_emergency_reset_idle() -> None:
    bridge = _BridgeProbe()
    live = _LiveProbe()
    demo = _DemoProbe()
    session = _session_stub(bridge=bridge, live=live, demo=demo, mode="demo")
    session.emergency_reset_demo()
    assert live.stop_calls >= 1
    assert live.recover_calls >= 1
    assert demo.reset_calls == 1
    assert bridge.operation_mode == "demo"
    assert not bridge.devices_locked


def test_emergency_reset_during_live() -> None:
    live = _LiveProbe(state=LIVE_STATUS_LIVE)
    demo = _DemoProbe()
    bridge = _BridgeProbe()
    session = _session_stub(bridge=bridge, live=live, demo=demo, mode="live")
    session.emergency_reset_demo()
    assert live.state == LIVE_STATUS_IDLE
    assert demo.ab_modes == ["raw"]


def test_emergency_reset_repeated() -> None:
    session = _session_stub()
    session.emergency_reset_demo()
    session.emergency_reset_demo()
    assert session._demo_controller.reset_calls == 2


def test_live_startup_failure_offers_fallback() -> None:
    bridge = _BridgeProbe()
    live = _LiveProbe()

    def fail_start():
        live.state = LIVE_STATUS_ERROR

    live.start = fail_start  # type: ignore[method-assign]
    mic, phones, inputs, outputs = _devices()
    demo = _DemoProbe()
    session = _session_stub(
        bridge=bridge,
        live=live,
        demo=demo,
        mode="demo",
        selected_input=mic,
        selected_output=phones,
        input_choices=inputs,
        output_choices=outputs,
    )
    session._model_sample_rate = lambda set_error=True: 48_000  # type: ignore[method-assign]
    session._apply_io_to_controllers = lambda: None  # type: ignore[method-assign]
    session.set_live_mode = ApplicationSession.set_live_mode.__get__(
        session,
        ApplicationSession,
    )
    session.set_live_mode()
    assert bridge.fallback_offered
    assert "Live audio could not be started" in bridge.fallback_message


def test_model_failure_offers_recorded_fallback() -> None:
    bridge = _BridgeProbe()
    live = _LiveProbe()
    session = _session_stub(bridge=bridge, live=live, model=FINETUNED_MODEL_NAME)

    def broken_rate(*, set_error: bool = True):
        return None

    session._model_sample_rate = broken_rate  # type: ignore[method-assign]
    session.set_live_mode()
    assert bridge.fallback_offered
    assert "Fine-tuned model could not be initialized" in bridge.fallback_message


def test_use_recorded_demo_switches_mode() -> None:
    bridge = _BridgeProbe()
    live = _LiveProbe(state=LIVE_STATUS_ERROR)
    demo = _DemoProbe()
    session = _session_stub(bridge=bridge, live=live, demo=demo, mode="live")
    bridge.fallback_offered = True
    session.use_recorded_demo = ApplicationSession.use_recorded_demo.__get__(
        session,
        ApplicationSession,
    )
    session.set_demo_mode = ApplicationSession.set_demo_mode.__get__(
        session,
        ApplicationSession,
    )
    session.use_recorded_demo()
    assert bridge.operation_mode == "demo"
    assert not bridge.fallback_offered


def test_run_demo_preflight_session_hook() -> None:
    mic, phones, inputs, outputs = _devices()
    bridge = _BridgeProbe()
    session = _session_stub(
        bridge=bridge,
        selected_input=mic,
        selected_output=phones,
        input_choices=inputs,
        output_choices=outputs,
    )

    original = run_demo_preflight

    def patched(**kwargs):
        kwargs["skip_io_probe"] = True
        kwargs["model_probe"] = lambda _n: (True, "")
        kwargs["catalog_loader"] = lambda: _FakeCatalog(
            [type("S", (), {"wav_path": Path(__file__)})()],
        )
        with tempfile.TemporaryDirectory() as tmp:
            kwargs["benchmark_root"] = Path(tmp)
            return original(**kwargs)

    import drdo_anc.gui.session as session_mod

    session_mod.run_demo_preflight = patched  # type: ignore[attr-defined]
    try:
        session.run_demo_preflight()
    finally:
        session_mod.run_demo_preflight = original

    assert bridge.preflight.get("summary") == "DEMO READY"


def main() -> int:
    tests = [
        test_preflight_all_pass_with_mocks,
        test_preflight_missing_input_device,
        test_preflight_invalid_input_role,
        test_preflight_missing_output_device,
        test_preflight_invalid_output_role,
        test_preflight_missing_model,
        test_preflight_model_init_failure,
        test_preflight_missing_demo_asset,
        test_preflight_benchmark_warning_only,
        test_emergency_reset_idle,
        test_emergency_reset_during_live,
        test_emergency_reset_repeated,
        test_live_startup_failure_offers_fallback,
        test_model_failure_offers_recorded_fallback,
        test_use_recorded_demo_switches_mode,
        test_run_demo_preflight_session_hook,
    ]
    failed = 0
    for test in tests:
        name = test.__name__
        try:
            test()
            print(f"PASS {name}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {name}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
