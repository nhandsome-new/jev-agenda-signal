"""Data types and loaders for agendas, transcripts, and ground truth."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

SIGNALS = ("red", "yellow", "green")
SPEAKERS = ("lead", "member_a", "member_b", "member_c")


@dataclass(frozen=True)
class Agenda:
    id: str
    title: str
    description: str


@dataclass(frozen=True)
class Utterance:
    t_sec: int
    speaker: str
    text: str


@dataclass(frozen=True)
class Event:
    """The moment an agenda's ground-truth signal changes."""

    t_sec: int
    agenda: str
    signal: str
    note: str = ""


@dataclass(frozen=True)
class Trap:
    id: str
    agenda: str
    expected_final: str
    description: str = ""


@dataclass(frozen=True)
class GroundTruth:
    version: str
    events: tuple[Event, ...]
    traps: tuple[Trap, ...] = ()

    def signal_at(self, agenda: str, t_sec: int) -> str:
        """Signal of the last event at or before t_sec; red if none."""
        signal = "red"
        for e in self.events:
            if e.agenda == agenda and e.t_sec <= t_sec:
                signal = e.signal
        return signal

    def final(self, agenda: str) -> str:
        return self.signal_at(agenda, float("inf"))


@dataclass(frozen=True)
class Prediction:
    choice: str
    probabilities: dict[str, float] = field(default_factory=dict)
    confidence: float | None = None


# --- Loaders ----------------------------------------------------------------


def load_agendas(path: Path) -> list[Agenda]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Agenda(**a) for a in data["agendas"]]


def load_transcript(path: Path) -> list[Utterance]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [Utterance(**json.loads(line)) for line in lines if line.strip()]


def load_gt(path: Path) -> GroundTruth:
    data = json.loads(path.read_text(encoding="utf-8"))
    events = sorted((Event(**e) for e in data["events"]), key=lambda e: e.t_sec)
    traps = tuple(Trap(**t) for t in data.get("traps", []))
    return GroundTruth(version=data["version"], events=tuple(events), traps=traps)


def load_scripts(data_dir: Path) -> dict[str, dict]:
    """Script manifest: {version: {"topic": str, "final": {agenda_id: signal}}}."""
    return json.loads((data_dir / "scripts.json").read_text(encoding="utf-8"))


def load_script_agendas(data_dir: Path, version: str) -> list[Agenda]:
    """Agendas of the topic a script belongs to."""
    topic = load_scripts(data_dir)[version]["topic"]
    return load_agendas(data_dir / "agendas" / f"{topic}.json")
