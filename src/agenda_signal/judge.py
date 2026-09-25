"""Judges: the only place that talks to a model API."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Protocol

from .models import SIGNALS, Agenda, Prediction

DEFAULT_MODEL = "jev-1.13.0"

# The three signals, as the options of each agenda's Choice question.
# Changing any text here changes `questions_hash`, so runs stay comparable.
CRITERIA = {
    "red": "Not talked about yet. The same words used about something else do not count.",
    "yellow": (
        "Talked about, but there is no clear conclusion yet. "
        "This includes putting it off, or taking back an earlier conclusion."
    ),
    "green": "A clear conclusion was reached, and it still stands.",
}

QUESTION = "What is the status of `agenda` in `transcript`?"


def build_questions(agendas: list[Agenda]) -> dict[str, dict]:
    """One Choice question per agenda, as plain JSON-serializable dicts."""
    return {
        a.id: {
            "instructions": {
                "agenda": {"id": a.id, "title": a.title, "description": a.description},
                "question": QUESTION,
            },
            "criteria": CRITERIA,
        }
        for a in agendas
    }


def questions_hash(questions: dict[str, dict]) -> str:
    blob = json.dumps(questions, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True)
class Judgment:
    predictions: dict[str, Prediction]
    model: str
    input_tokens: int
    latency_ms: float


class Judge(Protocol):
    name: str

    def evaluate(self, state: dict, questions: dict[str, dict]) -> Judgment: ...


class FakeJudge:
    """Offline judge for tests and dry runs. Always answers `answer`."""

    name = "fake"

    def __init__(self, answer: str = "red"):
        assert answer in SIGNALS
        self.answer = answer

    def evaluate(self, state: dict, questions: dict[str, dict]) -> Judgment:
        probs = {s: float(s == self.answer) for s in SIGNALS}
        preds = {qid: Prediction(self.answer, probs, 1.0) for qid in questions}
        return Judgment(preds, model="fake", input_tokens=0, latency_ms=0.0)


class JevJudge:
    """Jev via the official SDK. Reads TYPESAFE_API_KEY from the environment.

    Retries on 429/529 are handled by the SDK's default retry policy.
    """

    name = "jev"

    def __init__(self, model: str = DEFAULT_MODEL):
        from typesafe_sdk import TypeSafeClient

        self.model = model
        self.client = TypeSafeClient(model=model)

    def evaluate(self, state: dict, questions: dict[str, dict]) -> Judgment:
        from typesafe_sdk import Choice

        started = time.perf_counter()
        response = self.client.system_one(
            state=state,
            questions={qid: Choice(**q) for qid, q in questions.items()},
        )
        latency_ms = (time.perf_counter() - started) * 1000

        preds = {
            qid: Prediction(
                a.choice, {s: a.probabilities.get(s, 0.0) for s in SIGNALS}, a.confidence
            )
            for qid, a in response.answers.items()
        }
        return Judgment(preds, response.model, response.usage.input_tokens, latency_ms)


def make_judge(name: str, model: str = DEFAULT_MODEL) -> Judge:
    if name == "fake":
        return FakeJudge()
    if name == "jev":
        return JevJudge(model)
    raise ValueError(f"unknown judge: {name}")
