"""Maps ``GuiBenchmarkPresentation`` onto ``GUIBridge`` properties."""

from __future__ import annotations

from drdo_anc.experiments.finetuned_compare.compare import (
    FINETUNED_MODEL_NAME,
    PRETRAINED_MODEL_NAME,
)
from drdo_anc.gui.benchmark_results import (
    BenchmarkComparisonBlock,
    GuiBenchmarkPresentation,
)

DEVELOPMENT_CONTEXT_LINES = (
    "Development Benchmark",
    "",
    "• 60 cases",
    "• 10 clean speakers",
    "• 3 noise categories",
    "• 2 SNR conditions",
    "• deterministic evaluation",
    "• offline + streaming evaluation",
)


def _format_block(block: BenchmarkComparisonBlock | None) -> dict[str, str | float | int | bool]:
    if block is None:
        return {
            "available": False,
            "title": "",
            "context": "",
            "rules_version": "",
            "experiment_version": "",
            "evaluation_modes": "",
            "num_cases": 0,
            "successful_evaluations": 0,
            "paired_evaluations": 0,
            "pretrained_si_sdr": 0.0,
            "pretrained_stoi": 0.0,
            "pretrained_pesq": 0.0,
            "pretrained_snr": 0.0,
            "finetuned_si_sdr": 0.0,
            "finetuned_stoi": 0.0,
            "finetuned_pesq": 0.0,
            "finetuned_snr": 0.0,
            "si_sdr_improvement": 0.0,
            "si_sdr_improved": 0,
            "si_sdr_degraded": 0,
            "si_sdr_tied": 0,
            "pretrained_source": "",
            "finetuned_source": "",
            "holdout_note": "",
        }

    holdout_note = ""
    if block.training_holdout_status:
        holdout_note = (
            "training_holdout_status = unverified — "
            "not a verified training hold-out result."
        )

    context = "\n".join(DEVELOPMENT_CONTEXT_LINES)
    if block.section_id != "development":
        context = (
            f"{block.section_title}\n\n"
            "Recording-disjoint evaluation (independent protocol).\n"
            f"{holdout_note}"
        )

    return {
        "available": True,
        "title": block.section_title,
        "context": context,
        "rules_version": block.rules_version,
        "experiment_version": block.experiment_version,
        "evaluation_modes": block.evaluation_modes,
        "num_cases": block.num_cases,
        "successful_evaluations": block.successful_evaluations,
        "paired_evaluations": block.paired_evaluations,
        "pretrained_si_sdr": block.pretrained.si_sdr_db,
        "pretrained_stoi": block.pretrained.stoi,
        "pretrained_pesq": block.pretrained.pesq,
        "pretrained_snr": block.pretrained.snr_db,
        "finetuned_si_sdr": block.finetuned.si_sdr_db,
        "finetuned_stoi": block.finetuned.stoi,
        "finetuned_pesq": block.finetuned.pesq,
        "finetuned_snr": block.finetuned.snr_db,
        "si_sdr_improvement": block.si_sdr_improvement_db,
        "si_sdr_improved": block.si_sdr_improved,
        "si_sdr_degraded": block.si_sdr_degraded,
        "si_sdr_tied": block.si_sdr_tied,
        "pretrained_source": block.pretrained_source,
        "finetuned_source": block.finetuned_source,
        "holdout_note": holdout_note,
    }


def apply_benchmark_presentation(bridge, presentation: GuiBenchmarkPresentation) -> None:
    bridge.set_benchmark_presentation(
        loaded=presentation.loaded,
        unavailable_message=presentation.error_message
        if not presentation.loaded
        else presentation.error_message,
        pretrained_model=PRETRAINED_MODEL_NAME,
        finetuned_model=FINETUNED_MODEL_NAME,
        development=_format_block(presentation.development),
        recording_disjoint=_format_block(presentation.recording_disjoint),
    )
