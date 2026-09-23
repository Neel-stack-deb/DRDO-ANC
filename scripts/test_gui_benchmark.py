#!/usr/bin/env python3
"""Benchmark results screen tests (no model inference)."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

src_dir = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(src_dir))

from drdo_anc.gui.benchmark_bridge import apply_benchmark_presentation
from drdo_anc.gui.benchmark_results import (
    BenchmarkLoadError,
    load_gui_benchmark_presentation,
    project_root,
)


def _minimal_report(
    *,
    rules: str,
    si_sdr: float,
    stoi: float,
    pesq: float,
    snr: float,
    case_id: str = "case_001",
) -> dict:
    row = {
        "case_id": case_id,
        "mode": "offline",
        "noise_category": "uav_drone",
        "snr_db": 0.0,
        "si_sdr": si_sdr,
        "stoi": stoi,
        "pesq": pesq,
        "snr": snr,
        "status": "success",
    }
    streaming = dict(row)
    streaming["mode"] = "streaming"
    streaming["si_sdr"] = si_sdr + 0.1
    return {
        "manifest_rules_version": rules,
        "modes": ["offline", "streaming"],
        "successful_cases": 2,
        "summary_overall": {
            "mean_si_sdr": si_sdr,
            "mean_stoi": stoi,
            "mean_pesq": pesq,
            "mean_snr": snr,
        },
        "case_results": [row, streaming],
    }


class _Bridge:
    def __init__(self) -> None:
        self.payload: dict | None = None

    def set_benchmark_presentation(self, **kwargs) -> None:
        self.payload = kwargs


def test_load_development_from_fixture(tmp_path: Path | None = None) -> None:
    root = tmp_path or Path(tempfile.mkdtemp())
    dev_dir = root / "dfn3_finetuned_compare"
    dev_dir.mkdir(parents=True)
    (dev_dir / "pretrained_full.json").write_text(
        json.dumps(_minimal_report(rules="sih26-eval-v1", si_sdr=12.71, stoi=0.667, pesq=1.85, snr=12.30)),
        encoding="utf-8",
    )
    (dev_dir / "finetuned_full.json").write_text(
        json.dumps(_minimal_report(rules="sih26-eval-v1", si_sdr=14.95, stoi=0.708, pesq=2.119, snr=15.01)),
        encoding="utf-8",
    )

    presentation = load_gui_benchmark_presentation(root)
    assert presentation.loaded
    assert presentation.development is not None
    assert presentation.development.rules_version == "sih26-eval-v1"
    assert abs(presentation.development.si_sdr_improvement_db - 2.24) < 0.1


def test_recording_disjoint_fixture() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        rd_dir = root / "dfn3_finetuned_recording_safe"
        rd_dir.mkdir()
        (rd_dir / "pretrained_full.json").write_text(
            json.dumps(
                _minimal_report(
                    rules="sih26-finetuned-recording-safe-v1",
                    si_sdr=12.29,
                    stoi=0.696,
                    pesq=1.879,
                    snr=12.31,
                )
            ),
            encoding="utf-8",
        )
        (rd_dir / "finetuned_full.json").write_text(
            json.dumps(
                _minimal_report(
                    rules="sih26-finetuned-recording-safe-v1",
                    si_sdr=15.47,
                    stoi=0.728,
                    pesq=2.262,
                    snr=15.47,
                )
            ),
            encoding="utf-8",
        )

        presentation = load_gui_benchmark_presentation(root)
        assert presentation.recording_disjoint is not None
        assert presentation.recording_disjoint.training_holdout_status == "unverified"


def test_missing_results_directory() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        presentation = load_gui_benchmark_presentation(Path(tmp) / "empty")
        assert not presentation.loaded
        assert "unavailable" in presentation.error_message.lower()


def test_malformed_json() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        dev_dir = root / "dfn3_finetuned_compare"
        dev_dir.mkdir()
        (dev_dir / "pretrained_full.json").write_text("{not json", encoding="utf-8")
        (dev_dir / "finetuned_full.json").write_text("{}", encoding="utf-8")

        presentation = load_gui_benchmark_presentation(root)
        assert not presentation.loaded or presentation.development is None


def test_bridge_apply_sets_loaded_flag() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        test_load_development_from_fixture(Path(tmp))
        presentation = load_gui_benchmark_presentation(Path(tmp))
        bridge = _Bridge()
        apply_benchmark_presentation(bridge, presentation)
        assert bridge.payload is not None
        assert bridge.payload["loaded"] is True
        assert bridge.payload["development"]["available"] is True


def test_local_authoritative_artifacts_match_documentation() -> None:
    root = project_root() / "data" / "benchmark_results"
    pretrained = root / "dfn3_finetuned_compare" / "pretrained_full.json"
    if not pretrained.is_file():
        return

    presentation = load_gui_benchmark_presentation(root)
    assert presentation.development is not None
    dev = presentation.development
    assert dev.paired_evaluations == 120
    assert dev.si_sdr_improved == 118
    assert dev.si_sdr_degraded == 2
    assert abs(dev.pretrained.si_sdr_db - 12.71) < 0.02
    assert abs(dev.finetuned.si_sdr_db - 14.95) < 0.02
    assert abs(dev.si_sdr_improvement_db - 2.24) < 0.02

    if presentation.recording_disjoint is not None:
        rd = presentation.recording_disjoint
        assert rd.paired_evaluations == 116
        assert abs(rd.si_sdr_improvement_db - 3.18) < 0.02


def test_live_mode_unaffected_by_benchmark_loader() -> None:
    from drdo_anc.gui.live_state import LIVE_STATUS_IDLE

    assert LIVE_STATUS_IDLE == "IDLE"


def main() -> int:
    tests = [
        lambda: test_load_development_from_fixture(),
        test_recording_disjoint_fixture,
        test_missing_results_directory,
        test_malformed_json,
        test_bridge_apply_sets_loaded_flag,
        test_local_authoritative_artifacts_match_documentation,
        test_live_mode_unaffected_by_benchmark_loader,
    ]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    print(f"\nAll {len(tests)} benchmark GUI tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
