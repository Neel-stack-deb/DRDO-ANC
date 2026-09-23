#!/usr/bin/env python3

import argparse

import os

import sys

from pathlib import Path



src_dir = Path(__file__).resolve().parent.parent / "src"

sys.path.insert(0, os.fspath(src_dir))



from drdo_anc.audio.live import format_device_listing

from drdo_anc.gui.app import run_gui

from drdo_anc.gui.bridge import GUIBridge

from drdo_anc.gui.live_controller import LiveAudioController

from drdo_anc.gui.session import ApplicationSession



DEFAULT_MODEL_NAME = "DeepFilterNet3-Finetuned"

DEFAULT_READ_CHUNK_SIZE = 1024





def _parse_device(value: str | None) -> int | str | None:

  if value is None:

    return None



  try:

    return int(value)

  except ValueError:

    return value





def _build_parser() -> argparse.ArgumentParser:

  parser = argparse.ArgumentParser(description="DRDO-ANC Real-Time GUI")

  parser.add_argument(

    "--list-devices",

    action="store_true",

    help="List host audio devices and exit.",

  )

  parser.add_argument(

    "--model",

    default=DEFAULT_MODEL_NAME,

    help="Registered enhancer model name.",

  )

  parser.add_argument(

    "--passthrough",

    action="store_true",

    help="Copy microphone input directly to the speaker (live mode).",

  )

  parser.add_argument(

    "--sample-rate",

    type=int,

    default=None,

    help="Audio sample rate in Hz.",

  )

  parser.add_argument(

    "--chunk-size",

    type=int,

    default=DEFAULT_READ_CHUNK_SIZE,

    help="Samples requested per AudioInput.read() call.",

  )

  parser.add_argument(

    "--input-device",

    default=None,

    help="Input device index or name.",

  )

  parser.add_argument(

    "--output-device",

    default=None,

    help="Output device index or name.",

  )

  parser.add_argument(

    "--fake",

    action="store_true",

    help="Run animated placeholder visuals only (no pipeline).",

  )

  parser.add_argument(

    "--live-on-start",

    action="store_true",

    help="Start live microphone capture immediately instead of demo mode.",

  )

  return parser


def main() -> None:

  parser = _build_parser()

  args, _unknown_args = parser.parse_known_args()



  if args.list_devices:

    print(format_device_listing())

    return



  bridge = GUIBridge()



  if args.fake:

    print("Starting DRDO-ANC Real-Time GUI (Fake Visual Mode)...")

    bridge.enable_fake_visuals(True)

    run_gui(bridge=bridge)

    return



  live_controller = LiveAudioController(args, bridge)

  session = ApplicationSession(bridge, args, live_controller=live_controller)

  bridge.set_session(session)



  def on_ready() -> None:

    if args.live_on_start:

      session.set_live_mode()



  print("Starting PySide6 GUI (default: Demo Mode)...")

  run_gui(

    bridge=bridge,

    on_ready=on_ready,

    on_shutdown=session.shutdown,

  )





if __name__ == "__main__":

  try:

    main()

  except KeyboardInterrupt:

    sys.exit(0)

