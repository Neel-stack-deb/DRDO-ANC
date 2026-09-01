from __future__ import annotations

import argparse

from drdo_anc.gui.bridge import GUIBridge
from drdo_anc.gui.demo import DemoAudioController, load_benchmark_summary


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
        self._demo_controller = DemoAudioController(
            bridge,
            model_name=args.model,
            chunk_size=args.chunk_size,
        )
        self._mode = "demo"

        dev_cases, evaluations = load_benchmark_summary()
        self._bridge.set_benchmark_summary(dev_cases, evaluations)
        self._bridge.set_operation_mode("demo")
        self._bridge.set_stream_metadata(
            model_name=args.model,
            sample_rate=48_000,
        )
        self._bridge.set_demo_scenario(
            self._demo_controller.scenarios[0].label
        )

    def set_demo_mode(self) -> None:
        if self._mode == "demo":
            return

        self._live_controller.stop()
        self._mode = "demo"
        self._bridge.set_operation_mode("demo")
        self._bridge.set_audio_status("Ready")

    def set_live_mode(self) -> None:
        if self._mode == "live":
            return

        self._demo_controller.stop()
        self._mode = "live"
        self._bridge.set_operation_mode("live")
        self._live_controller.start()
        self._bridge.set_audio_status("Live")

    def play(self) -> None:
        if self._mode == "demo":
            self._demo_controller.play()
        else:
            self._live_controller.start()

    def pause(self) -> None:
        if self._mode == "demo":
            self._demo_controller.pause()

    def stop(self) -> None:
        if self._mode == "demo":
            self._demo_controller.stop()
        else:
            self._live_controller.stop()

    def set_scenario(self, index: int) -> None:
        if self._mode != "demo":
            self.set_demo_mode()

        self._demo_controller.set_scenario_index(index)

    def set_ab_raw(self) -> None:
        self._demo_controller.set_ab_mode("raw")

    def set_ab_enhanced(self) -> None:
        self._demo_controller.set_ab_mode("enhanced")

    def shutdown(self) -> None:
        self._demo_controller.shutdown()
        self._live_controller.stop()
