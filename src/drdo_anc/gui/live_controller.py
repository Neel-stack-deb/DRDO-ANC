"""GUI live microphone → StreamingPipeline → headphone path."""

from __future__ import annotations

import argparse
import sys
import threading
import traceback
from collections.abc import Callable
from typing import Protocol

from drdo_anc.audio.live import StreamingPipeline, close_sounddevice_io
from drdo_anc.audio.live.interfaces import AudioInput, AudioOutput
from drdo_anc.gui.demo import SelectableAudioOutput
from drdo_anc.gui.telemetry import HOLD_LIVE
from drdo_anc.gui.live_state import (
    LIVE_STATUS_ERROR,
    LIVE_STATUS_IDLE,
    LIVE_STATUS_LIVE,
    LIVE_STATUS_STARTING,
    LIVE_STATUS_STOPPING,
)


class _OpenIoFactory(Protocol):
    def __call__(
        self,
        sample_rate: int,
        *,
        input_device: int | str | None,
        output_device: int | str | None,
        blocksize: int,
    ) -> tuple[AudioInput, AudioOutput]: ...


def _default_open_io(
    sample_rate: int,
    *,
    input_device: int | str | None,
    output_device: int | str | None,
    blocksize: int,
) -> tuple[AudioInput, AudioOutput]:
    from drdo_anc.audio.live import open_sounddevice_io

    return open_sounddevice_io(
        sample_rate,
        input_device=input_device,
        output_device=output_device,
        blocksize=blocksize,
    )


class LiveAudioController:
    """Owns the background live microphone thread and pipeline lifecycle."""

    def __init__(
        self,
        args: argparse.Namespace,
        bridge,
        *,
        open_io: _OpenIoFactory | None = None,
        create_enhancer: Callable[[str], object] | None = None,
    ) -> None:
        self._args = args
        self._bridge = bridge
        self._open_io = open_io or _default_open_io
        self._create_enhancer = create_enhancer

        self._pipeline: StreamingPipeline | None = None
        self._audio_input: AudioInput | None = None
        self._audio_output: AudioOutput | None = None
        self._selectable_output: SelectableAudioOutput | None = None
        self._audio_thread: threading.Thread | None = None
        self._lifecycle_lock = threading.RLock()
        self._state = LIVE_STATUS_IDLE

        self._input_device: int | str | None = self._parse_device(args.input_device)
        self._output_device: int | str | None = self._parse_device(args.output_device)
        self._model_name = str(args.model)
        self._on_finished: Callable[[], None] | None = None
        self._output_mode = "raw"

    def set_finished_callback(self, callback: Callable[[], None] | None) -> None:
        self._on_finished = callback

    @staticmethod
    def _parse_device(value: str | None) -> int | str | None:
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return value

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_started(self) -> bool:
        return self._state in {
            LIVE_STATUS_STARTING,
            LIVE_STATUS_LIVE,
            LIVE_STATUS_STOPPING,
        }

    def set_devices(
        self,
        *,
        input_device: int | str | None,
        output_device: int | str | None,
    ) -> None:
        with self._lifecycle_lock:
            if self.is_started:
                return
            self._input_device = input_device
            self._output_device = output_device

    def set_model_name(self, model_name: str) -> None:
        with self._lifecycle_lock:
            if self.is_started:
                return
            self._model_name = model_name

    @property
    def output_mode(self) -> str:
        return self._output_mode

    def set_output_mode(self, mode: str) -> None:
        if mode not in {"raw", "enhanced"}:
            raise ValueError("mode must be 'raw' or 'enhanced'.")
        with self._lifecycle_lock:
            self._output_mode = mode
            if self._selectable_output is not None:
                self._selectable_output.set_mode(mode)

    def _end_telemetry_session(self) -> None:
        end = getattr(self._bridge, "end_telemetry_session", None)
        if end is not None:
            end(HOLD_LIVE)

    def _set_live_status(self, status: str) -> None:
        self._state = status
        setter = getattr(self._bridge, "set_live_status", None)
        if setter is not None:
            setter(status)
        if status == LIVE_STATUS_LIVE:
            self._bridge.set_audio_status("Live")
        elif status == LIVE_STATUS_IDLE:
            self._bridge.set_audio_status("Ready")
        elif status == LIVE_STATUS_ERROR:
            self._bridge.set_audio_status("Error")

    def _release_resources(self, *, join_thread: bool = True) -> None:
        pipeline = self._pipeline
        audio_input = self._audio_input
        audio_output = self._audio_output
        audio_thread = self._audio_thread

        self._pipeline = None

        if pipeline is not None:
            try:
                pipeline.request_stop()
            except Exception:
                traceback.print_exc()

        if join_thread and audio_thread is not None and audio_thread.is_alive():
            if threading.current_thread() is not audio_thread:
                audio_thread.join(timeout=5.0)

        if audio_input is not None and audio_output is not None:
            try:
                close_sounddevice_io(audio_input, audio_output)
            except Exception:
                traceback.print_exc()

        self._audio_input = None
        self._audio_output = None
        self._audio_thread = None

    def start(self) -> None:
        with self._lifecycle_lock:
            if self._state in {LIVE_STATUS_STARTING, LIVE_STATUS_LIVE}:
                return
            if self._state == LIVE_STATUS_STOPPING:
                return

            self._set_live_status(LIVE_STATUS_STARTING)
            self.set_output_mode("raw")
            self._bridge.clear_error()
            begin = getattr(self._bridge, "begin_telemetry_session", None)
            if begin is not None:
                begin()

            try:
                self._start_audio()
            except Exception as exc:
                self._end_telemetry_session()
                self._release_resources(join_thread=True)
                message = self._user_message(exc)
                self._bridge.set_error(message)
                self._set_live_status(LIVE_STATUS_ERROR)
                print(f"Audio startup failed: {exc}", file=sys.stderr)
                traceback.print_exc()
                return

            self._set_live_status(LIVE_STATUS_LIVE)
            self._bridge.set_pipeline_stage("capture")

    def stop(self) -> None:
        with self._lifecycle_lock:
            if self._state == LIVE_STATUS_IDLE:
                self._bridge.set_pipeline_stage("input")
                return

            previous = self._state
            self._set_live_status(LIVE_STATUS_STOPPING)

            self._release_resources(join_thread=True)

            self._set_live_status(LIVE_STATUS_IDLE)
            self._bridge.set_pipeline_stage("input")
            self._end_telemetry_session()
            if previous != LIVE_STATUS_ERROR:
                self._bridge.clear_error()

    def recover(self) -> None:
        """Return to IDLE after ERROR without restarting the application."""

        with self._lifecycle_lock:
            self._release_resources(join_thread=True)
            self._bridge.clear_error()
            self._set_live_status(LIVE_STATUS_IDLE)
            self._bridge.set_pipeline_stage("input")
            clear = getattr(self._bridge, "clear_mode_telemetry", None)
            if clear is not None:
                clear()

    @staticmethod
    def _user_message(exc: BaseException) -> str:
        text = str(exc).strip()
        if not text:
            return "Live audio failed to start. Check devices and try again."
        if text.startswith("Error opening") or "Invalid device" in text:
            return "Selected device is unavailable."
        return f"Live audio failed to start: {text}"

    def _start_audio(self) -> None:
        args = self._args

        if args.passthrough:
            sample_rate = args.sample_rate or 48_000
            enhancer = None
            model_name = "Pass-Through"
        else:
            create = self._create_enhancer
            if create is None:
                from drdo_anc.enhancement import create_enhancer as _create

                create = _create

            enhancer = create(self._model_name)
            sample_rate = args.sample_rate or enhancer.sample_rate()
            model_name = self._model_name

        if sample_rate <= 0:
            raise ValueError("Sample rate must be positive.")

        input_device = self._input_device
        output_device = self._output_device

        audio_input, audio_output = self._open_io(
            sample_rate,
            input_device=input_device,
            output_device=output_device,
            blocksize=args.chunk_size,
        )

        selectable_output = SelectableAudioOutput(audio_output)
        selectable_output.set_mode(self._output_mode)

        self._bridge.set_stream_metadata(
            model_name=model_name,
            sample_rate=sample_rate,
        )

        def on_telemetry(in_chunk, out_chunk, proc_time):
            stats = getattr(audio_input, "stats", None)
            stats_dict = stats.as_dict() if stats is not None else {}
            overflows = int(stats_dict.get("input_overflows", 0))
            overflow_setter = getattr(self._bridge, "set_live_input_overflows", None)
            if overflow_setter is not None:
                overflow_setter(overflows)
            self._bridge.publish_data(in_chunk, out_chunk, proc_time, stats=stats_dict)
            self._bridge.set_pipeline_stage("df3")

        pipeline = StreamingPipeline(
            audio_input,
            selectable_output,
            enhancer,
            read_chunk_size=args.chunk_size,
            passthrough=args.passthrough,
            telemetry_callback=on_telemetry,
        )

        self._audio_input = audio_input
        self._audio_output = audio_output
        self._selectable_output = selectable_output
        self._pipeline = pipeline

        def run_audio_thread() -> None:
            errored = False
            try:
                pipeline.run()
            except Exception as exc:
                errored = True
                self._bridge.set_error(self._user_message(exc))
                self._set_live_status(LIVE_STATUS_ERROR)
                print(f"Audio pipeline error: {exc}", file=sys.stderr)
                traceback.print_exc()
            finally:
                with self._lifecycle_lock:
                    try:
                        close_sounddevice_io(audio_input, audio_output)
                    except Exception:
                        traceback.print_exc()
                    self._pipeline = None
                    self._audio_input = None
                    self._audio_output = None
                    self._selectable_output = None
                    self._audio_thread = None
                    if errored:
                        self._state = LIVE_STATUS_ERROR
                    elif self._state != LIVE_STATUS_STOPPING:
                        self._set_live_status(LIVE_STATUS_IDLE)
                    self._bridge.set_pipeline_stage("input")
                    finished = self._on_finished
                    if finished is not None:
                        finished()

        audio_thread = threading.Thread(
            target=run_audio_thread,
            name="drdo-anc-audio",
            daemon=False,
        )
        self._audio_thread = audio_thread
        audio_thread.start()
