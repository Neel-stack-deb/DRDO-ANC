"""GUI helpers for input/output device selection.

Enumeration is delegated to ``list_audio_devices()``. This module only
filters by role, formats labels, and resolves defaults. It does not open
streams or change the live audio backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from drdo_anc.audio.live import list_audio_devices

Role = Literal["input", "output"]


@dataclass(frozen=True)
class GuiAudioDevice:
    """One PortAudio device as presented in the GUI selectors."""

    index: int
    name: str
    hostapi_name: str
    max_input_channels: int
    max_output_channels: int
    default_sample_rate: float

    @property
    def is_input(self) -> bool:
        return self.max_input_channels > 0

    @property
    def is_output(self) -> bool:
        return self.max_output_channels > 0

    def has_role(self, role: Role) -> bool:
        if role == "input":
            return self.is_input
        return self.is_output

    def label(self) -> str:
        sr = int(round(self.default_sample_rate))
        capability: list[str] = []
        if self.is_input:
            capability.append(f"in={self.max_input_channels}")
        if self.is_output:
            capability.append(f"out={self.max_output_channels}")
        return (
            f"{self.name} - {self.hostapi_name} - {sr} Hz "
            f"({', '.join(capability)})"
        )

    def channel_count_for_role(self, role: Role) -> int:
        if role == "input":
            return self.max_input_channels
        return self.max_output_channels

    def summary_lines(self, role: Role) -> list[str]:
        """Multi-line device facts for the live-mode panel."""

        channels = self.channel_count_for_role(role)
        ch_label = "channel" if channels == 1 else "channels"
        sr = int(round(self.default_sample_rate))
        return [
            self.name,
            self.hostapi_name,
            f"{channels} {ch_label}",
            f"{sr} Hz",
        ]

    def summary_text(self, role: Role) -> str:
        return "\n".join(self.summary_lines(role))


def devices_from_records(records: list[dict[str, Any]]) -> list[GuiAudioDevice]:
    """Convert ``list_audio_devices()`` dicts into GUI device objects."""

    devices: list[GuiAudioDevice] = []
    for record in records:
        devices.append(
            GuiAudioDevice(
                index=int(record["index"]),
                name=str(record["name"]),
                hostapi_name=str(record.get("hostapi_name") or f"hostapi {record.get('hostapi')}"),
                max_input_channels=int(record["max_input_channels"]),
                max_output_channels=int(record["max_output_channels"]),
                default_sample_rate=float(record["default_sample_rate"]),
            )
        )
    return devices


def enumerate_gui_devices() -> list[GuiAudioDevice]:
    """Enumerate host devices using the existing live-audio listing."""

    return devices_from_records(list_audio_devices())


def input_devices(devices: list[GuiAudioDevice]) -> list[GuiAudioDevice]:
    """Devices that can be used as microphone/input."""

    return [device for device in devices if device.is_input]


def output_devices(devices: list[GuiAudioDevice]) -> list[GuiAudioDevice]:
    """Devices that can be used as speaker/headphone output."""

    return [device for device in devices if device.is_output]


def is_hidden_gui_device(device: GuiAudioDevice) -> bool:
    """Host endpoints that are valid PortAudio devices but unusable for live DF3."""

    api = device.hostapi_name.lower()
    name = device.name.lower()
    if "wdm-ks" in api or "wdmks" in api:
        return True
    if "mapper" in name or name.startswith("primary sound"):
        return True
    if "bthhfenum" in name or "hands-free" in name:
        return True
    if name.startswith("headphones ()") or name.startswith("headset ()"):
        return True
    if 0 < device.default_sample_rate < 16_000:
        return True
    return False


def _api_rank(device: GuiAudioDevice) -> int:
    api = device.hostapi_name.lower()
    if "wasapi" in api:
        return 0
    if "directsound" in api:
        return 1
    if api == "mme" or api.endswith(" mme"):
        return 2
    return 3


def sort_gui_devices(devices: list[GuiAudioDevice]) -> list[GuiAudioDevice]:
    """WASAPI 48 kHz first; keep role lists independent."""

    return sorted(
        devices,
        key=lambda device: (
            _api_rank(device),
            0 if abs(device.default_sample_rate - 48_000.0) < 1.0 else 1,
            device.name.lower(),
            device.index,
        ),
    )


def _dedupe_legacy_host_apis(
    devices: list[GuiAudioDevice],
) -> list[GuiAudioDevice]:
    """If WASAPI exists for a device name, hide MME/DirectSound copies."""

    by_name: dict[str, list[GuiAudioDevice]] = {}
    for device in devices:
        by_name.setdefault(device.name.strip().lower(), []).append(device)

    kept: list[GuiAudioDevice] = []
    for group in by_name.values():
        wasapi = [
            device for device in group if "wasapi" in device.hostapi_name.lower()
        ]
        if wasapi:
            kept.extend(wasapi)
        else:
            kept.extend(group)
    return kept


def devices_for_selector(
    devices: list[GuiAudioDevice],
    role: Role,
    *,
    show_all: bool = False,
    keep: GuiAudioDevice | None = None,
) -> list[GuiAudioDevice]:
    """Role-filtered list for one GUI combo box."""

    role_devices = (
        input_devices(devices) if role == "input" else output_devices(devices)
    )
    if show_all:
        chosen = list(role_devices)
    else:
        chosen = [
            device for device in role_devices if not is_hidden_gui_device(device)
        ]
        chosen = _dedupe_legacy_host_apis(chosen)
        if not chosen:
            chosen = list(role_devices)

    if keep is not None and keep.has_role(role):
        if all(device.index != keep.index for device in chosen):
            chosen = [keep, *chosen]

    return sort_gui_devices(chosen)


def _preference_score(device: GuiAudioDevice) -> tuple[int, int, int]:
    api = device.hostapi_name.lower()
    name = device.name.lower()
    wasapi = 1 if "wasapi" in api else 0
    rate_48k = 1 if abs(device.default_sample_rate - 48_000.0) < 1.0 else 0
    mapper = 1 if "mapper" in name or "primary sound" in name else 0
    return (wasapi, rate_48k, -mapper)


def pick_default(candidates: list[GuiAudioDevice]) -> GuiAudioDevice | None:
    """Choose a sensible default without hard-coding machine indexes."""

    if not candidates:
        return None

    return max(candidates, key=lambda device: (_preference_score(device), -device.index))


def match_preferred(
    candidates: list[GuiAudioDevice],
    *,
    index: int | None = None,
    name: str | None = None,
    hostapi_name: str | None = None,
) -> GuiAudioDevice | None:
    """Restore a previous selection if it is still a valid device for this role."""

    if index is not None:
        for device in candidates:
            if device.index != index:
                continue
            if name is None or device.name == name:
                return device
            break

    if name:
        named = [device for device in candidates if device.name == name]
        if hostapi_name:
            api_matches = [
                device for device in named if device.hostapi_name == hostapi_name
            ]
            if api_matches:
                return pick_default(api_matches)
        if named:
            return pick_default(named)

    return None


def resolve_role_device(
    candidates: list[GuiAudioDevice],
    *,
    preferred_index: int | None = None,
    preferred_name: str | None = None,
    preferred_hostapi: str | None = None,
) -> GuiAudioDevice | None:
    """CLI/persisted preference, else a default valid device for the role."""

    matched = match_preferred(
        candidates,
        index=preferred_index,
        name=preferred_name,
        hostapi_name=preferred_hostapi,
    )
    if matched is not None:
        return matched
    return pick_default(candidates)


def combo_index_for_backend(
    candidates: list[GuiAudioDevice],
    backend_index: int | None,
) -> int:
    if backend_index is None:
        return -1
    for combo_index, device in enumerate(candidates):
        if device.index == backend_index:
            return combo_index
    return -1


def backend_index_for_combo(
    candidates: list[GuiAudioDevice],
    combo_index: int,
) -> int | None:
    if 0 <= combo_index < len(candidates):
        return candidates[combo_index].index
    return None


def _device_still_available(
    device: GuiAudioDevice,
    role: Role,
    available: list[GuiAudioDevice],
) -> bool:
    return any(
        candidate.index == device.index and candidate.has_role(role)
        for candidate in available
    )


def live_start_block_reason(
    selected_input: GuiAudioDevice | None,
    selected_output: GuiAudioDevice | None,
    *,
    available_inputs: list[GuiAudioDevice],
    available_outputs: list[GuiAudioDevice],
) -> str | None:
    """Return a user-visible error if Live Mode must not start."""

    if not available_inputs:
        return "No valid audio input device found. Connect a microphone and refresh devices."
    if not available_outputs:
        return (
            "No valid audio output device found. Connect headphones or speakers "
            "and refresh devices."
        )
    if selected_input is None:
        return "Selected device is unavailable."
    if selected_output is None:
        return "Selected device is unavailable."
    if not selected_input.is_input:
        return "Selected input device is not an audio input."
    if not selected_output.is_output:
        return "Selected output device is not an audio output."
    if not _device_still_available(selected_input, "input", available_inputs):
        return "Selected device is unavailable."
    if not _device_still_available(selected_output, "output", available_outputs):
        return "Selected device is unavailable."
    return None


def validate_live_sample_rate(
    *,
    model_sample_rate: int,
    requested_sample_rate: int | None = None,
) -> tuple[str | None, int]:
    """Validate the rate used for ``open_sounddevice_io``."""

    effective = int(requested_sample_rate or model_sample_rate)
    if effective <= 0:
        return "Sample rate must be positive.", 0
    if effective != model_sample_rate:
        return (
            f"Requested sample rate ({effective} Hz) does not match the "
            f"model boundary ({model_sample_rate} Hz). "
            "Omit --sample-rate or use the model rate."
        ), 0
    return None, effective


def validate_live_startup(
    selected_input: GuiAudioDevice | None,
    selected_output: GuiAudioDevice | None,
    *,
    available_inputs: list[GuiAudioDevice],
    available_outputs: list[GuiAudioDevice],
    model_sample_rate: int,
    requested_sample_rate: int | None = None,
) -> tuple[str | None, int]:
    """Device + sample-rate checks before opening the live stream."""

    block = live_start_block_reason(
        selected_input,
        selected_output,
        available_inputs=available_inputs,
        available_outputs=available_outputs,
    )
    if block is not None:
        return block, 0
    return validate_live_sample_rate(
        model_sample_rate=model_sample_rate,
        requested_sample_rate=requested_sample_rate,
    )
