"""Read-only SIH benchmark summaries for the GUI (no inference)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from drdo_anc.experiments.finetuned_compare import (
    EXPERIMENT_VERSION,
    compare_benchmark_reports,
    load_benchmark_report,
)
from drdo_anc.experiments.finetuned_compare.compare import (
    FINETUNED_MODEL_NAME,
    PRETRAINED_MODEL_NAME,
)
from drdo_anc.experiments.finetuned_compare.heldout import HELD_OUT_RULES_VERSION

DEVELOPMENT_COMPARE_DIR = "dfn3_finetuned_compare"
RECORDING_SAFE_DIR = "dfn3_finetuned_recording_safe"
REPORT_LABEL = "full"

TRAINING_HOLDOUT_STATUS = "unverified"


class BenchmarkLoadError(Exception):
    """Benchmark artifacts are missing or invalid."""


@dataclass(frozen=True)
class ModelMetricMeans:
    si_sdr_db: float
    stoi: float
    pesq: float
    snr_db: float


@dataclass(frozen=True)
class BenchmarkComparisonBlock:
    """One offline benchmark comparison (development or recording-disjoint)."""

    section_id: str
    section_title: str
    rules_version: str
    experiment_version: str
    evaluation_modes: str
    num_cases: int
    successful_evaluations: int
    total_evaluations: int
    paired_evaluations: int
    pretrained: ModelMetricMeans
    finetuned: ModelMetricMeans
    si_sdr_improvement_db: float
    si_sdr_improved: int
    si_sdr_degraded: int
    si_sdr_tied: int
    pretrained_source: str
    finetuned_source: str
    training_holdout_status: str | None = None
    training_holdout_claim: bool = False


@dataclass(frozen=True)
class GuiBenchmarkPresentation:
    loaded: bool
    error_message: str
    development: BenchmarkComparisonBlock | None
    recording_disjoint: BenchmarkComparisonBlock | None


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _relative_source(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _means_from_report(report: dict[str, Any]) -> ModelMetricMeans:
    summary = report.get("summary_overall") or {}
    required = ("mean_si_sdr", "mean_stoi", "mean_pesq", "mean_snr")
    missing = [key for key in required if key not in summary]
    if missing:
        raise BenchmarkLoadError(
            f"Report summary_overall missing keys: {', '.join(missing)}"
        )
    return ModelMetricMeans(
        si_sdr_db=float(summary["mean_si_sdr"]),
        stoi=float(summary["mean_stoi"]),
        pesq=float(summary["mean_pesq"]),
        snr_db=float(summary["mean_snr"]),
    )


def _validate_report_structure(report: dict[str, Any], path: Path) -> None:
    if "case_results" not in report:
        raise BenchmarkLoadError(f"Invalid benchmark report (no case_results): {path}")
    if not isinstance(report["case_results"], list):
        raise BenchmarkLoadError(f"Invalid case_results in: {path}")


def _load_pair(
    directory: Path,
    *,
    section_id: str,
    section_title: str,
    experiment_version: str,
    training_holdout_status: str | None = None,
) -> BenchmarkComparisonBlock:
    root = project_root()
    pretrained_path = directory / f"pretrained_{REPORT_LABEL}.json"
    finetuned_path = directory / f"finetuned_{REPORT_LABEL}.json"

    if not pretrained_path.is_file():
        raise BenchmarkLoadError(f"Missing pretrained report: {pretrained_path}")
    if not finetuned_path.is_file():
        raise BenchmarkLoadError(f"Missing fine-tuned report: {finetuned_path}")

    try:
        pretrained_report = load_benchmark_report(pretrained_path)
        finetuned_report = load_benchmark_report(finetuned_path)
    except json.JSONDecodeError as exc:
        raise BenchmarkLoadError(
            f"Benchmark report is not valid JSON: {exc}"
        ) from exc

    _validate_report_structure(pretrained_report, pretrained_path)
    _validate_report_structure(finetuned_report, finetuned_path)

    rules_version = str(
        pretrained_report.get("manifest_rules_version")
        or finetuned_report.get("manifest_rules_version")
        or ""
    )
    if not rules_version:
        raise BenchmarkLoadError("Report missing manifest_rules_version.")

    modes = pretrained_report.get("modes") or finetuned_report.get("modes") or []
    modes_text = " + ".join(str(mode) for mode in modes) if modes else "offline + streaming"

    successful = int(pretrained_report.get("successful_cases", 0))
    total_rows = len(pretrained_report.get("case_results", []))
    if successful <= 0:
        raise BenchmarkLoadError("Pretrained report has no successful cases.")

    comparison = compare_benchmark_reports(
        pretrained_report,
        finetuned_report,
    )
    si_summary = comparison.get("metrics", {}).get("si_sdr")
    if si_summary is None:
        raise BenchmarkLoadError("Could not compute paired SI-SDR comparison.")

    num_cases = successful // max(1, len(modes)) if modes else successful // 2

    return BenchmarkComparisonBlock(
        section_id=section_id,
        section_title=section_title,
        rules_version=rules_version,
        experiment_version=experiment_version,
        evaluation_modes=modes_text,
        num_cases=num_cases,
        successful_evaluations=successful,
        total_evaluations=total_rows,
        paired_evaluations=int(comparison.get("num_paired_rows", 0)),
        pretrained=_means_from_report(pretrained_report),
        finetuned=_means_from_report(finetuned_report),
        si_sdr_improvement_db=float(si_summary["mean_difference"]),
        si_sdr_improved=int(si_summary["improved"]),
        si_sdr_degraded=int(si_summary["degraded"]),
        si_sdr_tied=int(si_summary["tied"]),
        pretrained_source=_relative_source(pretrained_path.resolve(), root),
        finetuned_source=_relative_source(finetuned_path.resolve(), root),
        training_holdout_status=training_holdout_status,
        training_holdout_claim=False,
    )


def load_gui_benchmark_presentation(
    results_root: Path | None = None,
) -> GuiBenchmarkPresentation:
    """Load development + recording-disjoint comparisons for the GUI."""

    root = results_root or (project_root() / "data" / "benchmark_results")
    errors: list[str] = []
    development: BenchmarkComparisonBlock | None = None
    recording_disjoint: BenchmarkComparisonBlock | None = None

    try:
        development = _load_pair(
            root / DEVELOPMENT_COMPARE_DIR,
            section_id="development",
            section_title="Development Benchmark",
            experiment_version=EXPERIMENT_VERSION,
        )
    except BenchmarkLoadError as exc:
        errors.append(str(exc))

    try:
        recording_disjoint = _load_pair(
            root / RECORDING_SAFE_DIR,
            section_id="recording_disjoint",
            section_title="Recording-Disjoint Evaluation",
            experiment_version=HELD_OUT_RULES_VERSION,
            training_holdout_status=TRAINING_HOLDOUT_STATUS,
        )
    except BenchmarkLoadError as exc:
        errors.append(str(exc))

    if development is None and recording_disjoint is None:
        message = "Benchmark results unavailable."
        if errors:
            message += " " + "; ".join(errors)
        return GuiBenchmarkPresentation(
            loaded=False,
            error_message=message,
            development=None,
            recording_disjoint=None,
        )

    return GuiBenchmarkPresentation(
        loaded=True,
        error_message="; ".join(errors) if errors else "",
        development=development,
        recording_disjoint=recording_disjoint,
    )
