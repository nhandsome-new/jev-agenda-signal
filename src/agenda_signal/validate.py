"""Data checks. Every problem is returned as one readable line."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import SIGNALS, SPEAKERS, load_gt, load_script_agendas, load_scripts, load_transcript

SOURCE_LANG = "ko"


@dataclass(frozen=True)
class Limits:
    """Size bounds for source-language transcripts (about 20-minute meetings)."""

    min_duration_sec: int = 1100
    max_duration_sec: int = 1200
    min_chars: int = 3000
    max_chars: int = 6000


def _check_transcript(path: Path, errors: list[str]) -> list | None:
    try:
        utterances = load_transcript(path)
    except (ValueError, TypeError) as exc:
        errors.append(f"{path}: cannot parse ({exc})")
        return None
    if not utterances:
        errors.append(f"{path}: empty")
        return None

    for i, u in enumerate(utterances, 1):
        if not isinstance(u.t_sec, int) or u.t_sec < 0:
            errors.append(f"{path}:{i}: t_sec must be a non-negative int")
        if u.speaker not in SPEAKERS:
            errors.append(f"{path}:{i}: unknown speaker '{u.speaker}'")
        if not u.text.strip():
            errors.append(f"{path}:{i}: empty text")
    times = [u.t_sec for u in utterances]
    if times != sorted(times):
        errors.append(f"{path}: t_sec is not in order")
    return utterances


def validate(data_dir: Path, limits: Limits = Limits()) -> list[str]:
    errors: list[str] = []

    try:
        scripts = load_scripts(data_dir)
    except (OSError, ValueError) as exc:
        return [f"cannot load scripts.json: {exc}"]

    # Source-language transcripts and ground truth.
    source: dict[str, list] = {}
    for version, script in scripts.items():
        try:
            agenda_ids = [a.id for a in load_script_agendas(data_dir, version)]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(f"{version}: cannot load agendas ({exc})")
            continue
        if len(set(agenda_ids)) != len(agenda_ids):
            errors.append(f"{version}: duplicate agenda ids")
        expected = script["final"]
        path = data_dir / "transcripts" / SOURCE_LANG / f"{version}.jsonl"
        if not path.exists():
            errors.append(f"{path}: missing")
        elif (utterances := _check_transcript(path, errors)) is not None:
            source[version] = utterances
            duration = utterances[-1].t_sec
            chars = sum(len(u.text) for u in utterances)
            if not limits.min_duration_sec <= duration <= limits.max_duration_sec:
                errors.append(f"{path}: duration {duration}s out of range")
            if not limits.min_chars <= chars <= limits.max_chars:
                errors.append(f"{path}: {chars} chars out of range")

        gt_path = data_dir / "gt" / f"{version}.json"
        if not gt_path.exists():
            errors.append(f"{gt_path}: missing")
            continue
        try:
            gt = load_gt(gt_path)
        except (ValueError, TypeError, KeyError) as exc:
            errors.append(f"{gt_path}: cannot parse ({exc})")
            continue

        if gt.version != version:
            errors.append(f"{gt_path}: version field is '{gt.version}'")
        for e in gt.events:
            if e.agenda not in agenda_ids:
                errors.append(f"{gt_path}: event for unknown agenda '{e.agenda}'")
            if e.signal not in SIGNALS:
                errors.append(f"{gt_path}: invalid signal '{e.signal}'")
            if version in source and e.t_sec > source[version][-1].t_sec:
                errors.append(f"{gt_path}: event at {e.t_sec}s is after the transcript ends")
        for t in gt.traps:
            if t.agenda not in agenda_ids or t.expected_final not in SIGNALS:
                errors.append(f"{gt_path}: invalid trap '{t.id}'")
            elif gt.final(t.agenda) != t.expected_final:
                errors.append(f"{gt_path}: trap '{t.id}' disagrees with events")
        for agenda_id in agenda_ids:
            want = expected.get(agenda_id)
            if gt.final(agenda_id) != want:
                errors.append(
                    f"{gt_path}: final {agenda_id} is {gt.final(agenda_id)}, scripts.json says {want}"
                )

    # Translations must keep the source timing so ground truth can be reused.
    transcripts_dir = data_dir / "transcripts"
    lang_dirs = (
        sorted(p for p in transcripts_dir.iterdir() if p.is_dir() and p.name != SOURCE_LANG)
        if transcripts_dir.exists()
        else []
    )
    for lang_dir in lang_dirs:
        for version, src in source.items():
            path = lang_dir / f"{version}.jsonl"
            if not path.exists():
                errors.append(f"{path}: missing")
                continue
            translated = _check_transcript(path, errors)
            if translated is not None and [u.t_sec for u in translated] != [u.t_sec for u in src]:
                errors.append(f"{path}: utterance timing differs from {SOURCE_LANG}")

    return errors
