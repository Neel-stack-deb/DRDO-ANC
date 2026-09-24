"""PC demonstration preflight checks (no long inference runs)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from drdo_anc.enhancement import create_enhancer, get_model_config, list_models
from drdo_anc.enhancement.finetuned import FINETUNED_MODEL_NAME
from drdo_anc.gui.benchmark_results import (
    DEVELOPMENT_COMPARE_DIR,
    project_root,
)
from drdo_anc.gui.devices import GuiAudioDevice, validate_live_sample_rate


def _device_still_available(
    device: GuiAudioDevice,
    role: str,
    available: list[GuiAudioDevice],
) -> bool:
    return any(
        candidate.index == device.index and candidate.has_role(role)
        for candidate in available
    )
from drdo_anc.gui.preflight_state import (
    PREFLIGHT_FAILED,
    PREFLIGHT_READY,
    PREFLIGHT_WARNING,
)


@dataclass(frozen=True)
class PreflightCheck:
    check_id: str
    label: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class PreflightReport:
    status: str
    summary: str
    checks: tuple[PreflightCheck, ...]
    demo_audio_ready: bool

    @property
    def check_lines(self) -> list[str]:
        lines: list[str] = []
        for check in self.checks:
            mark = "✓" if check.passed else "✗"
            line = f"{mark} {check.label}"
            if check.detail and not check.passed:
                line += f" — {check.detail}"
            lines.append(line)
        return lines


def _check_input_device(
    selected_input: GuiAudioDevice | None,
    available_inputs: list[GuiAudioDevice],
) -> tuple[bool, str]:
    if not available_inputs:
        return (
            False,
            "No valid audio input device found. Connect a microphone and refresh devices.",
        )
    if selected_input is None:
        return False, "Selected device is unavailable."
    if not selected_input.is_input:
        return False, "Selected input device is not an audio input."
    if not _device_still_available(selected_input, "input", available_inputs):
        return False, "Selected device is unavailable."
    return True, ""


def _check_output_device(
    selected_output: GuiAudioDevice | None,
    available_outputs: list[GuiAudioDevice],
) -> tuple[bool, str]:
    if not available_outputs:
        return (
            False,
            "No valid audio output device found. Connect headphones and refresh devices.",
        )
    if selected_output is None:
        return False, "Selected device is unavailable."
    if not selected_output.is_output:
        return False, "Selected output device is not an audio output."
    if not _device_still_available(selected_output, "output", available_outputs):
        return False, "Selected device is unavailable."
    return True, ""


def _benchmark_files_present(root: Path) -> tuple[bool, str]:
    dev = root / DEVELOPMENT_COMPARE_DIR
    required = (
        dev / "pretrained_full.json",
        dev / "finetuned_full.json",
    )
    missing = [path for path in required if not path.is_file()]
    if missing:
        names = ", ".join(path.name for path in missing)
        return False, f"Missing development benchmark reports ({names})"
    return True, ""


def _probe_model_load(model_name: str) -> tuple[bool, str]:
    if model_name not in list_models():
        return False, f"Model {model_name!r} is not registered."

    try:
        get_model_config(model_name)
    except KeyError as exc:
        return False, str(exc)

    try:
        enhancer = create_enhancer(model_name, load=False)
        sample_rate = int(enhancer.sample_rate())
        if sample_rate <= 0:
            return False, "Invalid model sample rate."
    except Exception as exc:
        return False, f"Model configuration failed: {exc}"

    if model_name == FINETUNED_MODEL_NAME:
        try:
            from drdo_anc.enhancement.finetuned import (
                finetuned_export_dir,
                resolve_finetuned_artifact_root,
            )

            root = resolve_finetuned_artifact_root()
            export_dir = finetuned_export_dir(root)
            checkpoint = export_dir / "checkpoints" / "model_130.ckpt"
            if not export_dir.is_dir() or not checkpoint.is_file():
                return (
                    False,
                    "Fine-tuned artifact files are missing under models/dfn3_finetuned/.",
                )
        except Exception as exc:
            return False, f"Fine-tuned artifact check failed: {exc}"

    return True, ""


def _probe_io(
    sample_rate: int,
    *,
    input_device: int | str | None,
    output_device: int | str | None,
    blocksize: int,
    open_io: Callable[..., Any],
    close_io: Callable[..., None],
) -> tuple[bool, str]:
    try:
        audio_input, audio_output = open_io(
            sample_rate,
            input_device=input_device,
            output_device=output_device,
            blocksize=blocksize,
        )
        close_io(audio_input, audio_output)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def run_demo_preflight(
    *,
    selected_input: GuiAudioDevice | None,
    selected_output: GuiAudioDevice | None,
    available_inputs: list[GuiAudioDevice],
    available_outputs: list[GuiAudioDevice],
    model_name: str = FINETUNED_MODEL_NAME,
    requested_sample_rate: int | None = None,
    chunk_size: int = 1024,
    catalog_loader: Callable[[], Any] | None = None,
    model_probe: Callable[[str], tuple[bool, str]] | None = None,
    io_probe: Callable[[int, int | str | None, int | str | None], tuple[bool, str]]
    | None = None,
    benchmark_root: Path | None = None,
    skip_io_probe: bool = False,
) -> PreflightReport:
    """Run all preflight checks and return an aggregate report."""

    input_ok, input_detail = _check_input_device(selected_input, available_inputs)
    output_ok, output_detail = _check_output_device(
        selected_output,
        available_outputs,
    )

    using_custom_model_probe = model_probe is not None
    model_ok, model_detail = (model_probe or _probe_model_load)(model_name)

    model_sr = 48_000
    if model_ok:
        try:
            enhancer = create_enhancer(model_name, load=False)
            model_sr = int(enhancer.sample_rate())
        except Exception:
            if using_custom_model_probe:
                model_sr = 48_000
            else:
                model_ok = False
                model_detail = model_detail or "Model sample rate could not be determined."

    if model_ok:
        rate_err, _effective = validate_live_sample_rate(
            model_sample_rate=model_sr,
            requested_sample_rate=requested_sample_rate,
        )
        if rate_err:
            model_ok = False
            model_detail = rate_err

    if input_ok and output_ok and model_ok and not skip_io_probe:
        in_idx = selected_input.index if selected_input else None
        out_idx = selected_output.index if selected_output else None
        if io_probe is not None:
            io_ok, io_detail = io_probe(model_sr, in_idx, out_idx)
        else:
            try:
                from drdo_anc.audio.live import close_sounddevice_io, open_sounddevice_io

                io_ok, io_detail = _probe_io(
                    model_sr,
                    input_device=in_idx,
                    output_device=out_idx,
                    blocksize=chunk_size,
                    open_io=open_sounddevice_io,
                    close_io=close_sounddevice_io,
                )
            except Exception as exc:
                io_ok = False
                io_detail = str(exc)
        if not io_ok:
            input_ok = False
            output_ok = False
            input_detail = io_detail or "Could not open audio input."
            output_detail = io_detail or "Could not open audio output."

    demo_ok = False
    demo_detail = ""
    loader = catalog_loader
    if loader is None:
        from drdo_anc.gui.demo_manifest import load_validated_demo_catalog

        loader = load_validated_demo_catalog
    try:
        catalog = loader()
        if not catalog.scenarios:
            demo_detail = "No demo scenarios in manifest."
        else:
            demo_ok = all(
                scenario.wav_path.is_file() for scenario in catalog.scenarios
            )
            if not demo_ok:
                demo_detail = "One or more scenario WAV files are missing."
    except Exception as exc:
        demo_detail = str(exc)

    bench_root = benchmark_root or (project_root() / "data" / "benchmark_results")
    bench_ok, bench_detail = _benchmark_files_present(bench_root)

    checks = (
        PreflightCheck("input_device", "Input device", input_ok, input_detail),
        PreflightCheck("output_device", "Output device", output_ok, output_detail),
        PreflightCheck(
            "finetuned_model",
            "Fine-tuned model",
            model_ok,
            model_detail,
        ),
        PreflightCheck("demo_audio", "Demo audio", demo_ok, demo_detail),
        PreflightCheck(
            "benchmark_results",
            "Benchmark results",
            bench_ok,
            bench_detail if not bench_ok else "",
        ),
    )

    core_failed = not (input_ok and output_ok and model_ok and demo_ok)
    demo_audio_ready = not core_failed

    if core_failed:
        status = PREFLIGHT_FAILED
        summary = "DEMO NOT READY"
    elif not bench_ok:
        status = PREFLIGHT_WARNING
        summary = "DEMO READY"
    else:
        status = PREFLIGHT_READY
        summary = "DEMO READY"

    return PreflightReport(
        status=status,
        summary=summary,
        checks=checks,
        demo_audio_ready=demo_audio_ready,
    )
