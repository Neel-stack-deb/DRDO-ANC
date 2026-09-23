#!/usr/bin/env python3
"""GUI device-role selection tests (no microphone required)."""

from __future__ import annotations

import sys
from pathlib import Path

src_dir = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(src_dir))

from drdo_anc.gui.devices import (
    backend_index_for_combo,
    combo_index_for_backend,
    devices_from_records,
    input_devices,
    live_start_block_reason,
    output_devices,
    pick_default,
    resolve_role_device,
)


def _record(
    index: int,
    name: str,
    *,
    ins: int = 0,
    outs: int = 0,
    sr: float = 48000.0,
    api: str = "Windows WASAPI",
) -> dict:
    return {
        "index": index,
        "name": name,
        "max_input_channels": ins,
        "max_output_channels": outs,
        "default_sample_rate": sr,
        "hostapi": 2,
        "hostapi_name": api,
    }


FAKE_HOST = [
    _record(4, "Speakers (AB13X USB Audio)", outs=2, sr=44100.0, api="MME"),
    _record(
        18,
        "Headphones (Realtek(R) Audio)",
        outs=2,
        sr=48000.0,
        api="Windows WASAPI",
    ),
    _record(
        19,
        "Microphone (AB13X USB Audio)",
        ins=2,
        sr=48000.0,
        api="Windows WASAPI",
    ),
    _record(
        20,
        "Headset (USB Duplex)",
        ins=1,
        outs=2,
        sr=48000.0,
        api="Windows WASAPI",
    ),
    _record(21, "Stereo Mix", ins=2, sr=48000.0, api="Windows WASAPI"),
]


def test_input_selector_excludes_output_only() -> None:
    devices = devices_from_records(FAKE_HOST)
    inputs = input_devices(devices)
    names = [device.name for device in inputs]
    indexes = [device.index for device in inputs]
    assert "Headphones (Realtek(R) Audio)" not in names
    assert 18 not in indexes
    assert 19 in indexes
    assert 20 in indexes
    assert 21 in indexes
    print("PASS: test_input_selector_excludes_output_only")


def test_output_selector_excludes_input_only() -> None:
    devices = devices_from_records(FAKE_HOST)
    outputs = output_devices(devices)
    names = [device.name for device in outputs]
    indexes = [device.index for device in outputs]
    assert "Microphone (AB13X USB Audio)" not in names
    assert 19 not in indexes
    assert 21 not in indexes
    assert 18 in indexes
    assert 20 in indexes
    assert 4 in indexes
    print("PASS: test_output_selector_excludes_input_only")


def test_duplex_device_appears_in_both_selectors() -> None:
    devices = devices_from_records(FAKE_HOST)
    duplex = [device for device in devices if device.index == 20][0]
    assert duplex in input_devices(devices)
    assert duplex in output_devices(devices)
    print("PASS: test_duplex_device_appears_in_both_selectors")


def test_gui_selection_maps_to_pipeline_indexes() -> None:
    devices = devices_from_records(FAKE_HOST)
    inputs = input_devices(devices)
    outputs = output_devices(devices)

    mic = resolve_role_device(
        inputs,
        preferred_name="Microphone (AB13X USB Audio)",
        preferred_hostapi="Windows WASAPI",
    )
    phones = resolve_role_device(
        outputs,
        preferred_name="Headphones (Realtek(R) Audio)",
        preferred_hostapi="Windows WASAPI",
    )
    assert mic is not None and mic.index == 19
    assert phones is not None and phones.index == 18

    input_combo = combo_index_for_backend(inputs, 19)
    output_combo = combo_index_for_backend(outputs, 18)
    assert backend_index_for_combo(inputs, input_combo) == 19
    assert backend_index_for_combo(outputs, output_combo) == 18
    print("PASS: test_gui_selection_maps_to_pipeline_indexes")


def test_defaults_are_not_hard_coded_indexes() -> None:
    devices = devices_from_records(FAKE_HOST)
    default_in = pick_default(input_devices(devices))
    default_out = pick_default(output_devices(devices))
    assert default_in is not None
    assert default_out is not None
    assert default_in.is_input
    assert default_out.is_output
    shifted = devices_from_records(
        [
            _record(3, "Microphone (AB13X USB Audio)", ins=2),
            _record(7, "Headphones (Realtek(R) Audio)", outs=2),
        ]
    )
    shifted_in = resolve_role_device(
        input_devices(shifted),
        preferred_name="Microphone (AB13X USB Audio)",
    )
    shifted_out = resolve_role_device(
        output_devices(shifted),
        preferred_name="Headphones (Realtek(R) Audio)",
    )
    assert shifted_in is not None and shifted_in.index == 3
    assert shifted_out is not None and shifted_out.index == 7
    print("PASS: test_defaults_are_not_hard_coded_indexes")


def test_missing_device_blocks_live_mode() -> None:
    devices = devices_from_records(FAKE_HOST)
    reason = live_start_block_reason(
        None,
        resolve_role_device(output_devices(devices)),
        available_inputs=input_devices(devices),
        available_outputs=output_devices(devices),
    )
    assert reason is not None and "unavailable" in reason.lower()

    empty_reason = live_start_block_reason(
        None,
        None,
        available_inputs=[],
        available_outputs=output_devices(devices),
    )
    assert empty_reason is not None and "No valid audio input" in empty_reason
    print("PASS: test_missing_device_blocks_live_mode")


def test_device_summary_lines_for_live_panel() -> None:
    devices = devices_from_records(FAKE_HOST)
    mic = [device for device in devices if device.index == 19][0]
    lines = mic.summary_lines("input")
    assert lines[0] == "Microphone (AB13X USB Audio)"
    assert lines[1] == "Windows WASAPI"
    assert lines[2] == "2 channels"
    assert lines[3] == "48000 Hz"
    print("PASS: test_device_summary_lines_for_live_panel")


def test_labels_include_name_api_and_rate() -> None:
    devices = devices_from_records(FAKE_HOST)
    mic = [device for device in devices if device.index == 19][0]
    label = mic.label()
    assert "Microphone (AB13X USB Audio)" in label
    assert "WASAPI" in label
    assert "48000 Hz" in label
    assert "in=2" in label
    print("PASS: test_labels_include_name_api_and_rate")


def test_recommended_list_hides_wdmks_and_duplicate_apis() -> None:
    from drdo_anc.gui.devices import devices_for_selector

    cluttered = devices_from_records(
        FAKE_HOST
        + [
            _record(
                2,
                "Microphone (AB13X USB Audio)",
                ins=1,
                sr=44100.0,
                api="MME",
            ),
            _record(
                10,
                "Microphone (AB13X USB Audio)",
                ins=1,
                sr=44100.0,
                api="Windows DirectSound",
            ),
            _record(
                45,
                "Microphone (AB13X USB Audio)",
                ins=1,
                sr=48000.0,
                api="Windows WDM-KS",
            ),
            _record(
                33,
                "Headset (@System32\\drivers\\bthhfenum.sys,#2;%1 Hands-Free%0;(TWS))",
                ins=1,
                sr=8000.0,
                api="Windows WDM-KS",
            ),
            _record(
                0,
                "Microsoft Sound Mapper - Input",
                ins=2,
                sr=44100.0,
                api="MME",
            ),
        ]
    )
    recommended = devices_for_selector(cluttered, "input", show_all=False)
    names_apis = [(d.name, d.hostapi_name, d.index) for d in recommended]
    assert ("Microphone (AB13X USB Audio)", "Windows WASAPI", 19) in names_apis
    assert all(d.hostapi_name != "MME" or "Mapper" not in d.name for d in recommended)
    assert all("WDM-KS" not in d.hostapi_name for d in recommended)
    assert all("bthhfenum" not in d.name for d in recommended)
    ab13x = [d for d in recommended if d.name == "Microphone (AB13X USB Audio)"]
    assert len(ab13x) == 1
    assert ab13x[0].index == 19

    shown_all = devices_for_selector(cluttered, "input", show_all=True)
    assert any(d.index == 2 for d in shown_all)
    assert any(d.index == 45 for d in shown_all)
    print("PASS: test_recommended_list_hides_wdmks_and_duplicate_apis")


def main() -> int:
    print("=" * 70)
    print("DRDO-ANC | GUI device selection tests")
    print("=" * 70)
    tests = [
        test_input_selector_excludes_output_only,
        test_output_selector_excludes_input_only,
        test_duplex_device_appears_in_both_selectors,
        test_gui_selection_maps_to_pipeline_indexes,
        test_defaults_are_not_hard_coded_indexes,
        test_missing_device_blocks_live_mode,
        test_device_summary_lines_for_live_panel,
        test_labels_include_name_api_and_rate,
        test_recommended_list_hides_wdmks_and_duplicate_apis,
    ]
    for test in tests:
        test()
    print("=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
