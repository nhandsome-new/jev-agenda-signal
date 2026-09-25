"""Streaming simulation: replay a transcript tick by tick and record judgments.

Results are appended to `ticks.jsonl` one line per tick, so an interrupted run
can be resumed without repeating paid calls.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator, Sequence
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .judge import Judge, build_questions, questions_hash
from .models import Utterance, load_script_agendas, load_transcript
from .state import build_state

TICK_SEC = 60
CONFIG_FILE = "config.json"
TICKS_FILE = "ticks.jsonl"


def tick_times(utterances: Sequence[Utterance], tick_sec: int = TICK_SEC) -> list[int]:
    """Tick times up to the first multiple of tick_sec that covers the last utterance."""
    end = utterances[-1].t_sec if utterances else 0
    last = max(tick_sec, -(-end // tick_sec) * tick_sec)
    return list(range(tick_sec, last + 1, tick_sec))


def run_version(
    judge: Judge,
    questions: dict[str, dict],
    utterances: Sequence[Utterance],
    version: str,
    done: dict[int, dict] | None = None,
) -> Iterator[dict]:
    """Yield one record per tick not already in `done` (keyed by t_sec)."""
    done = done or {}
    for t in tick_times(utterances):
        if t in done:
            continue
        judgment = judge.evaluate(build_state(utterances, t), questions)
        yield {
            "version": version,
            "t_sec": t,
            "predictions": {a: asdict(p) for a, p in judgment.predictions.items()},
            "model": judgment.model,
            "input_tokens": judgment.input_tokens,
            "latency_ms": round(judgment.latency_ms, 1),
        }


# --- Run directory ----------------------------------------------------------


def _git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def available_versions(data_dir: Path, lang: str) -> list[str]:
    return sorted(p.stem for p in (data_dir / "transcripts" / lang).glob("*.jsonl"))


def create_run(
    runs_dir: Path,
    data_dir: Path,
    lang: str,
    versions: list[str],
    judge_name: str,
    model: str,
) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = runs_dir / f"{stamp}_{lang}_{judge_name}"
    run_dir.mkdir(parents=True, exist_ok=False)
    config = {
        "lang": lang,
        "versions": versions,
        "judge": judge_name,
        "model": "fake" if judge_name == "fake" else model,
        "questions_hash": _questions_hash(data_dir, versions),
        "git_commit": _git_commit(),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    (run_dir / CONFIG_FILE).write_text(json.dumps(config, indent=2) + "\n")
    return run_dir


def _questions(data_dir: Path, version: str) -> dict[str, dict]:
    return build_questions(load_script_agendas(data_dir, version))


def _questions_hash(data_dir: Path, versions: list[str]) -> str:
    return questions_hash({v: _questions(data_dir, v) for v in versions})


def load_config(run_dir: Path) -> dict:
    return json.loads((run_dir / CONFIG_FILE).read_text())


def load_ticks(run_dir: Path) -> list[dict]:
    path = run_dir / TICKS_FILE
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def execute(run_dir: Path, data_dir: Path, judge: Judge) -> int:
    """Run (or resume) every version in the run's config. Returns new tick count."""
    config = load_config(run_dir)
    if _questions_hash(data_dir, config["versions"]) != config["questions_hash"]:
        raise RuntimeError(
            "Question criteria changed since this run started; start a new run."
        )

    existing = load_ticks(run_dir)
    written = 0
    with (run_dir / TICKS_FILE).open("a", encoding="utf-8") as out:
        for version in config["versions"]:
            path = data_dir / "transcripts" / config["lang"] / f"{version}.jsonl"
            done = {r["t_sec"]: r for r in existing if r["version"] == version}
            questions = _questions(data_dir, version)
            for record in run_version(judge, questions, load_transcript(path), version, done):
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                out.flush()
                written += 1
    return written
