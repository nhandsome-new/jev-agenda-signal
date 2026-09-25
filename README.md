# Agenda Signal

**Track meeting agendas in real time with [Jev](https://docs.typesafe.ai/).**

[한국어](README.ko.md) · [日本語](README.ja.md)

During a meeting, each agenda item gets a signal that updates as people talk:

| Signal | Meaning |
|---|---|
| 🔴 | Not talked about yet |
| 🟡 | Talked about, no clear conclusion yet (incl. put off or taken back) |
| 🟢 | Clearly concluded, and still stands |

![Demo: agenda signals change as the meeting goes on](docs/demo.gif)

*16× speed. Left: the meeting and Jev's agenda signals. Right: local speech-to-text and Jev calls as they happen.*

## How it works

Every 30–60 seconds, the transcript so far goes to Jev in one request, with one
Choice question per agenda item. Jev answers them in parallel.

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

## Results

Five fictional 20-minute meetings in Korean, English and Japanese, checked
once per minute with `jev-1.13.0` (500 judgments per language).

| | Korean | English | Japanese |
|---|---|---|---|
| Correct at every check | 97.8% | 98.2% | 98.4% |
| Final signal correct | 23 / 25 | 25 / 25 | 25 / 25 |
| Traps passed | 13 / 14 | 14 / 14 | 14 / 14 |

- Traps: decisions without the keyword, the keyword used about something else, items put off or taken back, items raised in the last minute.
- About 0.27 s per call and **$0.003 per 20-minute meeting**. A change shows up about 36 s later (median).
- With a local ASR in front, 30 s of audio took under 2 s to process end to end.

## Quick start: replay the sample meetings

No audio or speech recognition: `run` feeds the text transcripts to Jev minute
by minute, as if live, and compares the signals with the ground truth.

```bash
uv sync                                              # Python ≥ 3.11, uv
uv run pytest                                        # offline tests
uv run agenda-signal run --lang en --version good --judge fake   # no API key needed

cp .env.example .env                                 # set TYPESAFE_API_KEY
uv run agenda-signal run --lang en --version good    # 20 calls, about $0.003
uv run agenda-signal eval runs/<run_id>              # metrics + minute-by-minute timeline
```

`--lang` is `ko`, `en` or `ja`; omit `--version` to run all five meetings.

## Use it with your own ASR

Speech recognition is not included. Put yours in `my_asr()`, yielding
`(seconds since start, text)` for each finished sentence:

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


def my_asr():
    """YOUR SPEECH RECOGNITION GOES HERE: yield (t_sec, text) per finished sentence."""
    raise NotImplementedError("connect your speech recognition here")


last_check = 0.0
for t_sec, text in my_asr():                          # <- sentences from your ASR
    transcript.append(Utterance(t_sec, "unknown", text))
    if t_sec - last_check >= 30:                       # check every 30 seconds
        result = judge.evaluate(build_state(transcript, t_sec), questions)
        print({a: p.choice for a, p in result.predictions.items()})   # {'A1': 'green', ...}
        last_check = t_sec
```

- Transcribing in chunks? Re-transcribe each chunk's last sentence with the next chunk; it is often cut off.
- Describe each agenda in one plain sentence. Jev reads instructions literally.

Our demo used [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper)
(`whisper-large-v3-turbo`) on a Mac, checking every 30 s: ASR up to 1.1 s and
Jev up to 0.7 s per step.

## Dataset

| Meeting | Final signals (A1–A5) |
|---|---|
| `good` · workshop planning, run well | 🟢🟢🟢🟢🟡 |
| `normal` · workshop planning, runs out of time | 🟢🟡🟡🔴🔴 |
| `bad` · workshop planning, detours and a reversed decision | 🟡🔴🔴🟡🔴 |
| `office_move` · moving to a new office | 🟢🟢🟡🟢🟡 |
| `onboarding` · preparing for a new hire | 🟢🟢🟡🔴🔴 |

```
data/
├── scripts.json            meeting → topic + expected final signals
├── agendas/<topic>.json    five agendas per topic
├── transcripts/{ko,en,ja}/<meeting>.jsonl    {"t_sec", "speaker", "text"} per line
├── gt/<meeting>.json       when each signal changes: {"t_sec", "agenda", "signal"}
└── outlines/<meeting>.md   readable summary and traps
```

The three languages share timing and ground truth.

## Limits

- Tested on 20-minute meetings only; longer meetings mean larger inputs every call.
- Fictional meetings, ground truth labeled by one person.
- Results vary slightly between runs (±1–2 of 500).

### Note: a sliding-window variant

Sending only the last 3 minutes plus the previous signals scored 82% (vs. 98%):
settled items fell back to 🔴 once their conclusion left the window.

- **Could help:** long meetings (about an hour or more), where the whole transcript strains the context limit, accuracy, or cost.
- **To make it work:** keep the signals in code; let Jev judge only what changed in the window. Not implemented.
