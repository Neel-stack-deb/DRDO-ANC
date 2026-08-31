from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RecordingLengthTracker:
    """
    Track live input/enhanced sample counts for end-of-session alignment.

    The tracker records whether the gap ``input_samples - enhanced_samples``
    stabilizes after the first non-empty enhanced chunk. A stable gap can be
    corrected by prepending leading silence to ``enhanced.wav`` when the
    lifecycle proves the deficit is constant through ``flush()``.
    """

    input_samples: int = 0
    enhanced_samples: int = 0
    saw_enhanced: bool = False
    gap_after_first_enhanced: int | None = None
    gap_after_last_output: int | None = None
    gap_stable: bool = True
    flush_samples_added: int = 0

    def note_input(self, num_samples: int) -> None:
        if num_samples > 0:
            self.input_samples += num_samples

    def note_enhanced(self, num_samples: int) -> None:
        if num_samples <= 0:
            return

        self.enhanced_samples += num_samples
        gap = self.input_samples - self.enhanced_samples

        if not self.saw_enhanced:
            self.saw_enhanced = True
            self.gap_after_first_enhanced = gap

        if (
            self.gap_after_last_output is not None
            and gap != self.gap_after_last_output
        ):
            self.gap_stable = False

        self.gap_after_last_output = gap

    def note_flush(self, num_samples: int) -> None:
        if num_samples > 0:
            self.flush_samples_added += num_samples
            self.note_enhanced(num_samples)

    @property
    def deficit_samples(self) -> int:
        return self.input_samples - self.enhanced_samples

    def leading_deficit(self) -> int | None:
        if not self.saw_enhanced:
            return None

        return self.gap_after_first_enhanced

    def as_dict(self) -> dict:
        return {
            "input_samples": self.input_samples,
            "enhanced_samples": self.enhanced_samples,
            "deficit_samples": self.deficit_samples,
            "gap_after_first_enhanced": self.gap_after_first_enhanced,
            "gap_after_last_output": self.gap_after_last_output,
            "gap_stable": self.gap_stable,
            "flush_samples_added": self.flush_samples_added,
        }
