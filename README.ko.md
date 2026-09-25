# Agenda Signal

**[Jev](https://docs.typesafe.ai/)로 회의 중 아젠다를 실시간으로 관리합니다.**

[English](README.md) · [日本語](README.ja.md)

회의가 진행되는 동안 아젠다마다 신호가 대화에 따라 바뀝니다.

| 신호 | 뜻 |
|---|---|
| 🔴 | 아직 이야기하지 않음 |
| 🟡 | 이야기는 했지만 명확한 결론이 없음 (미룸·번복 포함) |
| 🟢 | 명확한 결론이 났고 유효함 |

![데모: 회의가 진행되며 아젠다 신호가 바뀝니다](docs/demo.gif)

*16배속. 왼쪽: 회의 화면과 Jev의 아젠다 신호. 오른쪽: 로컬 음성인식과 Jev 호출이 처리되는 과정.*

## 동작 방식

30~60초마다 지금까지의 회의 텍스트를 Jev에 한 번의 요청으로 보냅니다. 아젠다마다 Choice 질문을
하나씩 붙이면 Jev가 병렬로 판정합니다.

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

## 결과

20분짜리 가상 회의 5개를 한국어·영어·일본어로 준비해 `jev-1.13.0`으로 1분마다 판정했습니다
(언어당 500판정).

| | 한국어 | 영어 | 일본어 |
|---|---|---|---|
| 매 판정 시점 정답 | 97.8% | 98.2% | 98.4% |
| 최종 신호 정답 | 23 / 25 | 25 / 25 | 25 / 25 |
| 함정 통과 | 13 / 14 | 14 / 14 | 14 / 14 |

- 함정: 키워드 없는 결론, 다른 맥락의 같은 단어, 미루거나 번복한 아젠다, 막판 1분에 처음 나온 아젠다.
- 호출당 약 0.27초, **20분 회의 1개당 약 $0.003**. 신호 변화는 약 36초 뒤(중간값)에 반영됩니다.
- 앞단에 로컬 ASR을 붙이면 음성 30초 분량을 2초 안에 처리했습니다.

## 빠른 시작: 샘플 회의 재생

음성도 음성인식도 쓰지 않습니다. `run`이 텍스트 대본을 1분씩 실시간처럼 Jev에 넣고 정답과 비교합니다.

```bash
uv sync                                              # Python 3.11 이상, uv 필요
uv run pytest                                        # 오프라인 테스트
uv run agenda-signal run --lang en --version good --judge fake   # API 키 없이 실행

cp .env.example .env                                 # TYPESAFE_API_KEY 입력
uv run agenda-signal run --lang en --version good    # 20회 호출, 약 $0.003
uv run agenda-signal eval runs/<run_id>              # 지표 + 분 단위 타임라인
```

`--lang`은 `ko`, `en`, `ja` 중 하나이고, `--version`을 빼면 회의 5개를 모두 돌립니다.

## 내 ASR과 연결하기

음성인식은 포함돼 있지 않습니다. `my_asr()`에 넣고, 확정된 문장마다 `(시작부터 지난 초, 텍스트)`를
내보내면 됩니다.

```python
from agenda_signal.judge import JevJudge, build_questions
from agenda_signal.models import Agenda, Utterance
from agenda_signal.state import build_state

agendas = [
    Agenda("A1", "Date", "When the workshop will be held."),
    Agenda("A2", "Budget", "How much money can be spent on the workshop."),
    # ...
]
judge = JevJudge()                     # TYPESAFE_API_KEY를 읽습니다
questions = build_questions(agendas)
transcript: list[Utterance] = []


def my_asr():
    """여기에 내 음성인식이 들어갑니다: 확정된 문장마다 (t_sec, text)를 yield."""
    raise NotImplementedError("여기에 내 음성인식을 연결하세요")


last_check = 0.0
for t_sec, text in my_asr():                          # <- 내 ASR이 보내는 문장
    transcript.append(Utterance(t_sec, "unknown", text))
    if t_sec - last_check >= 30:                       # 30초마다 판정
        result = judge.evaluate(build_state(transcript, t_sec), questions)
        print({a: p.choice for a, p in result.predictions.items()})   # {'A1': 'green', ...}
        last_check = t_sec
```

- 조각 단위로 받아쓴다면 각 조각의 마지막 문장은 다음 조각에서 다시 받아쓰세요. 잘려 있는 경우가 많습니다.
- 아젠다 설명은 쉬운 한 문장으로 쓰세요. Jev는 지시문을 글자 그대로 읽습니다.

데모는 Mac에서 [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper)
(`whisper-large-v3-turbo`)로 30초마다 판정했고, 한 번에 ASR 최대 1.1초, Jev 최대 0.7초가 걸렸습니다.

## 데이터셋

| 회의 | 최종 신호 (A1–A5) |
|---|---|
| `good` · 워크숍 준비, 잘 진행됨 | 🟢🟢🟢🟢🟡 |
| `normal` · 워크숍 준비, 시간 부족 | 🟢🟡🟡🔴🔴 |
| `bad` · 워크숍 준비, 잡담과 결정 번복 | 🟡🔴🔴🟡🔴 |
| `office_move` · 사무실 이전 | 🟢🟢🟡🟢🟡 |
| `onboarding` · 신입사원 입사 준비 | 🟢🟢🟡🔴🔴 |

```
data/
├── scripts.json            회의 → 주제 + 최종 정답 신호
├── agendas/<topic>.json    주제별 아젠다 5개
├── transcripts/{ko,en,ja}/<meeting>.jsonl    한 줄에 {"t_sec", "speaker", "text"}
├── gt/<meeting>.json       신호가 바뀌는 시점: {"t_sec", "agenda", "signal"}
└── outlines/<meeting>.md   읽기용 요약과 함정
```

세 언어는 발화 시각과 정답을 공유합니다.

## 한계

- 20분 회의에서만 검증했습니다. 회의가 길수록 호출마다 입력이 커집니다.
- 가상 회의이며 정답은 한 사람이 라벨링했습니다.
- 실행마다 결과가 조금씩 다릅니다 (500판정 중 ±1~2).

### 참고: 최근 구간만 보내는 방식

최근 3분과 직전 신호만 보내면 정답률이 82%(전체 전송 98%)였습니다. 결론이 3분 밖으로 밀려나면
🟢가 🔴로 되돌아갔습니다.

- **유리할 수 있는 경우:** 1시간 이상의 긴 회의. 전체 전송은 입력 한도·정확도·비용에 부담이 됩니다.
- **개선 방향:** 신호는 코드가 유지하고, Jev는 최근 구간에서 바뀐 것만 판정. 구현하지 않았습니다.
