from __future__ import annotations

import argparse

from PySide6.QtCore import QSettings

from drdo_anc.enhancement import create_enhancer, list_models
from drdo_anc.gui.bridge import GUIBridge
from drdo_anc.gui.benchmark_bridge import apply_benchmark_presentation
from drdo_anc.gui.benchmark_results import load_gui_benchmark_presentation
from drdo_anc.gui.demo import DemoAudioController, load_benchmark_summary
from drdo_anc.gui.demo_manifest import (
    DemoManifestError,
    MISSING_DEMO_SCENARIO_CATEGORIES,
    compute_demo_reference_metrics,
    load_validated_demo_catalog,
    scenario_source_display_path,
)
from drdo_anc.gui.devices import (
    GuiAudioDevice,
    backend_index_for_combo,
    combo_index_for_backend,
    devices_for_selector,
    enumerate_gui_devices,
    input_devices,
    live_start_block_reason,
    match_preferred,
    output_devices,
    resolve_role_device,
    validate_live_startup,
)
from drdo_anc.enhancement.finetuned import FINETUNED_MODEL_NAME
from drdo_anc.gui.demo_preflight import run_demo_preflight
from drdo_anc.gui.demo_state import DEMO_STATUS_IDLE
from drdo_anc.gui.live_state import LIVE_STATUS_ERROR, LIVE_STATUS_IDLE, LIVE_STATUS_LIVE


def _parse_device(value: str | None) -> int | str | None:
    if value is None:
        return None

    try:
        return int(value)
    except ValueError:
        return value


def _preferred_from_cli_or_saved(
    *,
    cli_value: int | str | None,
    previous: GuiAudioDevice | None,
    settings: QSettings,
    index_key: str,
    name_key: str,
    hostapi_key: str,
) -> tuple[int | None, str | None, str | None]:
    if previous is not None:
        return previous.index, previous.name, previous.hostapi_name
    if isinstance(cli_value, int):
        return cli_value, None, None
    if isinstance(cli_value, str):
        return None, cli_value, None
    return (
        _settings_int(settings, index_key),
        _settings_str(settings, name_key),
        _settings_str(settings, hostapi_key),
    )


def _settings_str(settings: QSettings, key: str) -> str | None:
    if not settings.contains(key):
        return None
    value = settings.value(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _settings_int(settings: QSettings, key: str) -> int | None:
    if not settings.contains(key):
        return None
    value = settings.value(key)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class ApplicationSession:
    """Coordinates demo and live audio controllers for the GUI."""

    def __init__(
        self,
        bridge: GUIBridge,
        args: argparse.Namespace,
        *,
        live_controller,
    ) -> None:
        self._bridge = bridge
        self._args = args
        self._live_controller = live_controller
        self._live_controller.set_finished_callback(self._on_live_stream_finished)
        self._mode = "demo"
        self._settings = QSettings()
        self._all_devices: list[GuiAudioDevice] = []
        self._input_choices: list[GuiAudioDevice] = []
        self._output_choices: list[GuiAudioDevice] = []
        self._model_names: tuple[str, ...] = list_models()
        self._selected_input: GuiAudioDevice | None = None
        self._selected_output: GuiAudioDevice | None = None
        self._selected_model = str(args.model)
        self._show_all_devices = bool(
            self._settings.value("audio/show_all_devices", False, type=bool)
        )

        try:
            catalog = load_validated_demo_catalog()
            self._demo_controller = DemoAudioController(
                bridge,
                model_name=args.model,
                chunk_size=args.chunk_size,
                output_device=_parse_device(args.output_device),
            )
        except DemoManifestError as exc:
            bridge.set_error(f"Demo manifest invalid: {exc}")
            bridge.set_audio_status("Error")
            raise

        labels = [scenario.label for scenario in catalog.scenarios]
        self._bridge.set_scenario_labels(labels)
        self._bridge.set_selected_scenario_index(0)
        self._bridge.set_missing_demo_categories(
            [message for _, message in MISSING_DEMO_SCENARIO_CATEGORIES],
        )

        scenario = catalog.scenarios[0]
        self._apply_scenario_to_bridge(scenario)
        self._bridge.set_demo_assets(
            clean_file=scenario.clean_reference_path.name
            if scenario.clean_reference_path
            else "",
            noisy_file=scenario.wav_path.name,
            enhanced_ref_file=scenario.enhanced_wav_path.name
            if scenario.enhanced_wav_path
            else "",
            enhanced_playback=(
                "Live DF3"
                if scenario.enhanced_playback == "live"
                else "Offline Reference"
            ),
        )

        if (
            scenario.clean_reference_path is not None
            and scenario.enhanced_wav_path is not None
        ):
            metrics = compute_demo_reference_metrics(scenario)
            self._bridge.set_demo_reference_metrics(metrics)

        dev_cases, evaluations = load_benchmark_summary()
        self._bridge.set_benchmark_summary(dev_cases, evaluations)
        self._bridge.set_operation_mode("demo")
        self._bridge.set_stream_metadata(
            model_name=args.model,
            sample_rate=catalog.sample_rate,
        )
        self._bridge.set_demo_scenario(labels[0])
        self._demo_controller.set_ab_mode("raw")
        self.refresh_devices()
        self._bridge.set_audio_status("Ready")
        self._bridge.set_demo_status("IDLE")
        self._bridge.set_live_status(LIVE_STATUS_IDLE)
        self._bridge.clear_live_fallback()
        self._publish_live_device_summaries()
        apply_benchmark_presentation(
            bridge,
            load_gui_benchmark_presentation(),
        )

    def _apply_scenario_to_bridge(self, scenario) -> None:
        self._bridge.set_demo_scenario_details(
            label=scenario.label,
            source_file=scenario_source_display_path(scenario),
            sample_rate=scenario.sample_rate,
            model_name=self._selected_model,
            duration_s=scenario.duration_s,
        )

    @property
    def selected_input_backend_index(self) -> int | None:
        if self._selected_input is None:
            return None
        return self._selected_input.index

    @property
    def selected_output_backend_index(self) -> int | None:
        if self._selected_output is None:
            return None
        return self._selected_output.index

    @property
    def selected_model_name(self) -> str:
        return self._selected_model

    def refresh_devices(self) -> None:
        try:
            self._all_devices = enumerate_gui_devices()
        except Exception as exc:
            self._all_devices = []
            self._input_choices = []
            self._output_choices = []
            self._selected_input = None
            self._selected_output = None
            self._publish_device_choices()
            self._bridge.set_error(f"Audio device enumeration failed: {exc}")
            return

        previous_input = self._selected_input
        previous_output = self._selected_output
        cli_input = _parse_device(self._args.input_device)
        cli_output = _parse_device(self._args.output_device)
        input_index, input_name, input_hostapi = _preferred_from_cli_or_saved(
            cli_value=cli_input,
            previous=previous_input,
            settings=self._settings,
            index_key="audio/input_index",
            name_key="audio/input_name",
            hostapi_key="audio/input_hostapi",
        )
        output_index, output_name, output_hostapi = _preferred_from_cli_or_saved(
            cli_value=cli_output,
            previous=previous_output,
            settings=self._settings,
            index_key="audio/output_index",
            name_key="audio/output_name",
            hostapi_key="audio/output_hostapi",
        )

        self._input_choices = devices_for_selector(
            self._all_devices,
            "input",
            show_all=self._show_all_devices,
        )
        self._output_choices = devices_for_selector(
            self._all_devices,
            "output",
            show_all=self._show_all_devices,
        )

        self._selected_input = resolve_role_device(
            self._input_choices,
            preferred_index=input_index,
            preferred_name=input_name,
            preferred_hostapi=input_hostapi,
        )
        self._selected_output = resolve_role_device(
            self._output_choices,
            preferred_index=output_index,
            preferred_name=output_name,
            preferred_hostapi=output_hostapi,
        )

        if self._selected_input is None:
            self._selected_input = match_preferred(
                input_devices(self._all_devices),
                index=input_index,
                name=input_name,
                hostapi_name=input_hostapi,
            )
        if self._selected_output is None:
            self._selected_output = match_preferred(
                output_devices(self._all_devices),
                index=output_index,
                name=output_name,
                hostapi_name=output_hostapi,
            )

        self._input_choices = devices_for_selector(
            self._all_devices,
            "input",
            show_all=self._show_all_devices,
            keep=self._selected_input,
        )
        self._output_choices = devices_for_selector(
            self._all_devices,
            "output",
            show_all=self._show_all_devices,
            keep=self._selected_output,
        )

        self._apply_io_to_controllers()
        self._persist_selection()
        self._publish_device_choices()
        self._publish_live_device_summaries()

        block = live_start_block_reason(
            self._selected_input,
            self._selected_output,
            available_inputs=self._input_choices,
            available_outputs=self._output_choices,
        )
        if block is None:
            self._bridge.clear_error()
        else:
            self._bridge.set_error(block)

    def select_input_device(self, combo_index: int) -> None:
        if self._live_controller.is_started:
            self._bridge.set_error("Stop Live Mode before changing the input device.")
            self._publish_device_choices()
            return

        backend_index = backend_index_for_combo(self._input_choices, combo_index)
        if backend_index is None:
            self._selected_input = None
            self._publish_device_choices()
            self._bridge.set_error("Selected input device is no longer available.")
            return

        self._selected_input = self._input_choices[combo_index]
        self._apply_io_to_controllers()
        self._persist_selection()
        self._publish_device_choices()
        self._bridge.clear_error()

    def select_output_device(self, combo_index: int) -> None:
        if self._live_controller.is_started:
            self._bridge.set_error("Stop Live Mode before changing the output device.")
            self._publish_device_choices()
            return

        backend_index = backend_index_for_combo(self._output_choices, combo_index)
        if backend_index is None:
            self._selected_output = None
            self._publish_device_choices()
            self._bridge.set_error("Selected output device is no longer available.")
            return

        self._selected_output = self._output_choices[combo_index]
        self._apply_io_to_controllers()
        self._persist_selection()
        self._publish_device_choices()
        self._bridge.clear_error()

    def select_model(self, combo_index: int) -> None:
        if self._live_controller.is_started:
            self._bridge.set_error("Stop Live Mode before changing the model.")
            self._publish_device_choices()
            return

        if not (0 <= combo_index < len(self._model_names)):
            self._bridge.set_error("Selected model is not available.")
            return

        model_name = self._model_names[combo_index]
        try:
            self._demo_controller.set_model_name(model_name)
        except RuntimeError as exc:
            self._bridge.set_error(str(exc))
            self._publish_device_choices()
            return

        self._selected_model = model_name
        self._live_controller.set_model_name(model_name)
        self._bridge.set_stream_metadata(
            model_name=model_name,
            sample_rate=self._bridge.sampleRate or 48_000,
        )
        if self._mode == "demo":
            index = self._bridge.selectedScenarioIndex
            if 0 <= index < len(self._demo_controller.catalog.scenarios):
                self._apply_scenario_to_bridge(
                    self._demo_controller.catalog.scenarios[index],
                )
        self._publish_device_choices()
        self._bridge.clear_error()

    def set_show_all_devices(self, show_all: bool) -> None:
        if self._live_controller.is_started:
            self._bridge.set_error("Stop Live Mode before changing the device list.")
            self._publish_device_choices()
            return

        self._show_all_devices = bool(show_all)
        self._settings.setValue("audio/show_all_devices", self._show_all_devices)
        self.refresh_devices()

    def set_benchmark_mode(self) -> None:
        if self._mode == "benchmark":
            return

        self._demo_controller.stop()
        self._live_controller.stop()
        self._bridge.set_devices_locked(False)
        self._mode = "benchmark"
        self._bridge.set_operation_mode("benchmark")
        self._bridge.set_audio_status("Ready")
        self._bridge.clear_error()

    def set_demo_mode(self) -> None:
        if self._mode == "demo":
            return

        self._live_controller.stop()
        self._bridge.set_devices_locked(False)
        self._bridge.clear_live_fallback()
        self._bridge.clear_error()
        self._mode = "demo"
        self._bridge.set_operation_mode("demo")
        self._bridge.set_audio_status("Ready")
        self._bridge.set_live_status(LIVE_STATUS_IDLE)

    def _model_sample_rate(self, *, set_error: bool = True) -> int | None:
        if self._args.passthrough:
            return int(self._args.sample_rate or 48_000)
        try:
            enhancer = create_enhancer(self._selected_model, load=False)
            return int(enhancer.sample_rate())
        except Exception as exc:
            if set_error:
                self._bridge.set_error(
                    f"Model '{self._selected_model}' is not available: {exc}",
                )
            return None

    def _offer_model_init_fallback(self) -> None:
        if self._selected_model == FINETUNED_MODEL_NAME:
            self._bridge.offer_live_fallback(
                "Fine-tuned model could not be initialized.",
                kind="model",
            )
        else:
            self._bridge.offer_live_fallback(
                f"Model '{self._selected_model}' could not be initialized.",
                kind="model",
            )

    def select_live_mode(self) -> None:
        """Switch to Live UI without opening the microphone (use Play to start)."""

        if self._mode == "live":
            return

        self._bridge.clear_live_fallback()
        self._bridge.clear_error()
        self._demo_controller.stop()
        self._mode = "live"
        self._bridge.set_operation_mode("live")
        self._bridge.set_live_status(LIVE_STATUS_IDLE)
        self._publish_live_device_summaries()

    def set_live_mode(self) -> None:
        """Validate devices/model and start live capture (Play in Live mode)."""

        if self._mode != "live":
            self.select_live_mode()

        self._bridge.clear_live_fallback()

        model_sample_rate = self._model_sample_rate(set_error=False)
        if model_sample_rate is None:
            self._offer_model_init_fallback()
            self._bridge.set_live_status(LIVE_STATUS_ERROR)
            return

        block, _effective_sr = validate_live_startup(
            self._selected_input,
            self._selected_output,
            available_inputs=self._input_choices,
            available_outputs=self._output_choices,
            model_sample_rate=model_sample_rate,
            requested_sample_rate=self._args.sample_rate,
        )
        if block is not None:
            self._bridge.offer_live_fallback(
                "Live audio could not be started.",
                kind="live",
            )
            self._bridge.set_live_status(LIVE_STATUS_IDLE)
            return

        if self._live_controller.state == LIVE_STATUS_LIVE:
            return

        self._publish_live_device_summaries()
        self._apply_io_to_controllers()
        self._bridge.set_live_input_overflows(0)
        self._bridge.clear_error()
        self._live_controller.start()
        if self._live_controller.state == LIVE_STATUS_LIVE:
            self._bridge.set_devices_locked(True)
        elif self._live_controller.state == LIVE_STATUS_ERROR:
            self._bridge.offer_live_fallback(
                "Live audio could not be started.",
                kind="live",
            )

    def stop_live(self) -> None:
        if self._mode != "live":
            return
        self._live_controller.stop()
        self._bridge.set_devices_locked(False)

    def recover_live(self) -> None:
        self._live_controller.recover()
        self._bridge.set_devices_locked(False)
        self._bridge.set_live_input_overflows(0)
        self._bridge.clear_live_fallback()
        self._bridge.clear_error()

    def play(self) -> None:
        if self._mode == "benchmark":
            return
        if self._mode == "demo":
            self._live_controller.stop()
            self._bridge.set_devices_locked(False)
            self._demo_controller.play()
        else:
            self.set_live_mode()

    def pause(self) -> None:
        if self._mode == "demo":
            self._demo_controller.pause()

    def stop(self) -> None:
        if self._mode == "benchmark":
            return
        if self._mode == "demo":
            self._demo_controller.stop()
            return

        self.stop_live()
        self._bridge.set_audio_status("Stopped")

    def set_scenario(self, index: int) -> None:
        if self._mode != "demo":
            self.set_demo_mode()

        try:
            self._demo_controller.set_scenario_index(index)
            scenario = self._demo_controller.catalog.scenarios[index]
            self._apply_scenario_to_bridge(scenario)
            self._bridge.set_demo_assets(
                clean_file=scenario.clean_reference_path.name
                if scenario.clean_reference_path
                else "",
                noisy_file=scenario.wav_path.name,
                enhanced_ref_file=scenario.enhanced_wav_path.name
                if scenario.enhanced_wav_path
                else "",
                enhanced_playback=(
                    "Live DF3"
                    if scenario.enhanced_playback == "live"
                    else "Offline Reference"
                ),
            )
            if (
                scenario.clean_reference_path is not None
                and scenario.enhanced_wav_path is not None
            ):
                metrics = compute_demo_reference_metrics(scenario)
                self._bridge.set_demo_reference_metrics(metrics)
            else:
                self._bridge.clear_demo_reference_metrics()
        except DemoManifestError as exc:
            self._bridge.set_error("Demo audio unavailable for this scenario.")
            self._bridge.set_audio_status("Error")
            self._bridge.set_demo_status("ERROR")
            _ = exc

    def reset_demo(self) -> None:
        if self._mode != "demo":
            self.set_demo_mode()
        self._demo_controller.reset()

    def emergency_reset_demo(self) -> None:
        """Stop all audio paths and return to a safe recorded-demo idle state."""

        self._live_controller.stop()
        self._live_controller.recover()
        self._demo_controller.stop()
        self._demo_controller.reset()
        self._demo_controller.set_ab_mode("raw")
        self._bridge.set_devices_locked(False)
        self._bridge.set_live_input_overflows(0)
        self._bridge.clear_live_fallback()
        self._bridge.clear_error()
        self._bridge.set_live_status(LIVE_STATUS_IDLE)
        self._bridge.set_demo_status(DEMO_STATUS_IDLE)
        self._bridge.set_playback_state("stopped")
        self._bridge.set_audio_status("Ready")
        self._bridge.set_pipeline_stage("input")
        self._mode = "demo"
        self._bridge.set_operation_mode("demo")

    def run_demo_preflight(self) -> None:
        self._bridge.set_preflight_checking()
        report = run_demo_preflight(
            selected_input=self._selected_input,
            selected_output=self._selected_output,
            available_inputs=self._input_choices,
            available_outputs=self._output_choices,
            model_name=FINETUNED_MODEL_NAME,
            requested_sample_rate=self._args.sample_rate,
            chunk_size=int(self._args.chunk_size),
        )
        self._bridge.set_preflight_report(
            status=report.status,
            summary=report.summary,
            check_lines=report.check_lines,
        )

    def try_live_again(self) -> None:
        self._bridge.clear_live_fallback()
        self._bridge.clear_error()
        self._live_controller.recover()
        if self._mode != "live":
            self._mode = "live"
            self._bridge.set_operation_mode("live")
        self.set_live_mode()

    def use_recorded_demo(self) -> None:
        self._live_controller.stop()
        self._live_controller.recover()
        self._bridge.set_devices_locked(False)
        self._bridge.clear_live_fallback()
        self._bridge.clear_error()
        self._bridge.set_live_status(LIVE_STATUS_IDLE)
        self.set_demo_mode()

    def set_ab_raw(self) -> None:
        self._demo_controller.set_ab_mode("raw")

    def set_ab_enhanced(self) -> None:
        self._demo_controller.set_ab_mode("enhanced")

    def shutdown(self) -> None:
        self._demo_controller.shutdown()
        self._live_controller.stop()
        self._bridge.set_devices_locked(False)

    def _apply_io_to_controllers(self) -> None:
        input_index = self.selected_input_backend_index
        output_index = self.selected_output_backend_index
        self._live_controller.set_devices(
            input_device=input_index,
            output_device=output_index,
        )
        self._live_controller.set_model_name(self._selected_model)
        self._demo_controller.set_output_device(output_index)

    def _persist_selection(self) -> None:
        if self._selected_input is not None:
            self._settings.setValue("audio/input_index", self._selected_input.index)
            self._settings.setValue("audio/input_name", self._selected_input.name)
            self._settings.setValue(
                "audio/input_hostapi",
                self._selected_input.hostapi_name,
            )
        if self._selected_output is not None:
            self._settings.setValue("audio/output_index", self._selected_output.index)
            self._settings.setValue("audio/output_name", self._selected_output.name)
            self._settings.setValue(
                "audio/output_hostapi",
                self._selected_output.hostapi_name,
            )

    def _on_live_stream_finished(self) -> None:
        self._bridge.set_devices_locked(False)
        if self._live_controller.state == LIVE_STATUS_ERROR:
            if not self._bridge._live_fallback_offered:
                self._bridge.offer_live_fallback(
                    "Live audio could not be started.",
                    kind="live",
                )

    def _publish_live_device_summaries(self) -> None:
        input_text = (
            self._selected_input.summary_text("input")
            if self._selected_input is not None
            else ""
        )
        output_text = (
            self._selected_output.summary_text("output")
            if self._selected_output is not None
            else ""
        )
        self._bridge.set_live_device_summaries(
            input_summary=input_text,
            output_summary=output_text,
        )

    def _publish_device_choices(self) -> None:
        block = live_start_block_reason(
            self._selected_input,
            self._selected_output,
            available_inputs=self._input_choices,
            available_outputs=self._output_choices,
        )
        model_index = 0
        if self._selected_model in self._model_names:
            model_index = self._model_names.index(self._selected_model)

        self._bridge.set_device_choices(
            input_labels=[device.label() for device in self._input_choices],
            output_labels=[device.label() for device in self._output_choices],
            model_labels=list(self._model_names),
            selected_input_index=combo_index_for_backend(
                self._input_choices,
                self.selected_input_backend_index,
            ),
            selected_output_index=combo_index_for_backend(
                self._output_choices,
                self.selected_output_backend_index,
            ),
            selected_model_index=model_index,
            live_can_start=block is None,
            live_block_reason=block or "",
            show_all_devices=self._show_all_devices,
        )
