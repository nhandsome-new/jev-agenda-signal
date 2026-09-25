"""Build the Jev `state` for a tick. Pure functions, no I/O."""

from __future__ import annotations

from collections.abc import Sequence

from .models import Utterance


def build_state(utterances: Sequence[Utterance], t_sec: float) -> dict:
    """The whole transcript from the start of the meeting up to t_sec."""
    return {
        "transcript": [
            {"speaker": u.speaker, "text": u.text} for u in utterances if u.t_sec <= t_sec
        ]
    }
