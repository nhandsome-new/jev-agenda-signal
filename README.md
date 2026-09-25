# Agenda Signal

**Track meeting agendas in real time with [Jev](https://docs.typesafe.ai/).**

[한국어](README.ko.md)

During a meeting, every agenda item gets a traffic-light signal that updates
as people talk:

| Signal | Meaning |
|---|---|
| 🔴 | Not talked about yet |
| 🟡 | Talked about, but no clear conclusion yet (including put off, or a conclusion taken back) |
| 🟢 | A clear conclusion was reached, and it still stands |

So before the meeting ends, the host can see which items have not been
covered and which are still open.

## How it works

Every minute (or every 30 seconds), the transcript so far is sent to Jev in
**one request**, with **one Choice question per agenda item**. Jev answers
all questions in parallel and returns the chosen signal with probabilities.

```python
Choice(
    instructions={
        "agenda": {"id": "A2", "title": "Budget", "description": "How much money can be spent on the workshop."},
        "question": "What is the status of `agenda` in `transcript`?",
    },
    criteria={
        "red": "Not talked about yet. The same words used about something else do not count.",
        "yellow": "Talked about, but there is no clear conclusion yet. This includes putting it off, "
                  "or taking back an earlier conclusion.",
        "green": "A clear conclusion was reached, and it still stands.",
    },
)
```

The code keeps the loop; Jev only makes the narrow judgment. See
`src/agenda_signal/judge.py`.

## Results

Five fictional 20-minute meetings, each in Korean, English and Japanese,
with hand-labeled ground truth (when each signal changes). Jev `jev-1.13.0`,
checked once per minute: 5 scripts × 20 checks × 5 agendas = 500 judgments
per language.

| Metric | Korean | English | Japanese |
|---|---|---|---|
| Signal correct at every check | 489 / 500 (97.8%) | 491 / 500 (98.2%) | 492 / 500 (98.4%) |
| Final signal correct | 23 / 25 | 25 / 25 | 25 / 25 |
| Traps passed | 13 / 14 | 14 / 14 | 14 / 14 |
| Signal changes detected | 30 / 31 | 30 / 31 | 30 / 31 |
| Delay after a change (median) | 36 s | 37 s | 36 s |

- Same signal in all three languages: 490 / 500.
- Jev call: about 0.27 s. Cost: about **$0.003 per 20-minute meeting**.
- Traps are ordinary meeting moments: a decision made without the agenda's
  keyword, the keyword used about something else, an item only named and put
  off, a decision taken back, two decisions in one sentence, an item first
  raised in the last minute.
- With a local ASR in front (Whisper large-v3 turbo), processing 30 seconds of
  audio took under 2 s (ASR + Jev), and the signal matched the ground truth on
  97 / 100 (Korean) and 112 / 115 (English) checks.

## Quick start

Requires Python ≥ 3.11 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest                                        # offline tests
uv run agenda-signal validate                        # check the dataset

# Full pipeline without an API key (the fake judge always answers 🔴)
uv run agenda-signal run --lang en --version good --judge fake

# With Jev
cp .env.example .env                                 # set TYPESAFE_API_KEY
uv run agenda-signal run --lang en --version good    # 20 calls, about $0.003
uv run agenda-signal eval runs/<run_id>              # metrics + minute-by-minute timeline
```

`run` replays a transcript minute by minute and writes `runs/<run_id>/ticks.jsonl`.
Omit `--version` to run all five scripts; `--lang` is `ko`, `en` or `ja`.
An interrupted run continues with `run --resume runs/<run_id>`.

## Use it with your own ASR

Set up any speech-to-text you like. Append each finished segment to the
transcript, and check the signals every 30–60 seconds:

```python
from agenda_signal.judge import JevJudge, build_questions
from agenda_signal.models import Agenda, Utterance
from agenda_signal.state import build_state

agendas = [
    Agenda("A1", "Date", "When the workshop will be held."),
    Agenda("A2", "Budget", "How much money can be spent on the workshop."),
    # ...
]
judge = JevJudge()                     # reads TYPESAFE_API_KEY
questions = build_questions(agendas)
transcript: list[Utterance] = []


def on_asr_segment(t_sec: float, text: str, speaker: str = "unknown") -> None:
    transcript.append(Utterance(t_sec, speaker, text))


def check_signals(now_sec: float) -> dict[str, str]:
    result = judge.evaluate(build_state(transcript, now_sec), questions)
    return {agenda_id: p.choice for agenda_id, p in result.predictions.items()}
```

Tips from the demo:

- If you transcribe in chunks, keep the last segment of each chunk
  uncommitted and transcribe it again with the next chunk; it is often cut
  mid-sentence.
- Speaker labels are optional. The demo sent `"unknown"` for every segment.
- Describe each agenda item in one plain sentence. Jev reads instructions
  literally.

## Dataset

| Script | Meeting | Final signals (A1–A5) |
|---|---|---|
| `good` | Workshop planning, run well | 🟢🟢🟢🟢🟡 |
| `normal` | Workshop planning, runs out of time | 🟢🟡🟡🔴🔴 |
| `bad` | Workshop planning, detours and a reversed decision | 🟡🔴🔴🟡🔴 |
| `office_move` | Moving to a new office | 🟢🟢🟡🟢🟡 |
| `onboarding` | Preparing for a new hire | 🟢🟢🟡🔴🔴 |

```
data/
├── scripts.json                     script → topic + expected final signals
├── agendas/<topic>.json             five agendas per topic
├── transcripts/{ko,en,ja}/<script>.jsonl
├── gt/<script>.json                 ground truth: when each signal changes
└── outlines/<script>.md             human-readable summary, traps, expected signals
```

Transcript line: `{"t_sec": 0, "speaker": "lead", "text": "..."}`.
Ground-truth event: `{"t_sec": 272, "agenda": "A1", "signal": "green"}`; the
signal at any time is the last event at or before it (🔴 if none). English and
Japanese are line-by-line translations with the same timing, so they share the
ground truth.

## Limits

- Tested on 20-minute meetings only. The whole transcript is sent on every
  check, so longer meetings mean larger inputs (about 235 tokens per minute
  here). Jev's context limit (32k tokens), accuracy on long inputs, and the
  growing cost per call were not evaluated.
- The meetings are fictional and the ground truth was labeled by one person.
- Results vary slightly between runs (±1–2 of 500).
