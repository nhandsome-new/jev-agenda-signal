# Agenda Signal

**[Jev](https://docs.typesafe.ai/) で会議中のアジェンダをリアルタイムに管理します。**

[English](README.md) · [한국어](README.ko.md)

会議の進行に合わせて、アジェンダごとの信号が会話に応じて変わります。

| 信号 | 意味 |
|---|---|
| 🔴 | まだ話していない |
| 🟡 | 話はしたが明確な結論がない（先送り・撤回を含む） |
| 🟢 | 明確な結論が出ていて有効 |

![デモ：会議の進行に合わせてアジェンダの信号が変わる](docs/demo.gif)

*16倍速。左：会議画面と Jev のアジェンダ信号。右：ローカル音声認識と Jev 呼び出しが処理される様子。*

## 仕組み

30〜60秒ごとに、それまでの会議テキストを Jev に1回のリクエストで送ります。アジェンダごとに
Choice 質問を1つ付けると、Jev が並列に判定します。

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

## 結果

20分の架空の会議5本を韓国語・英語・日本語で用意し、`jev-1.13.0` で1分ごとに判定しました
（言語ごとに500判定）。

| | 韓国語 | 英語 | 日本語 |
|---|---|---|---|
| 各判定時点の正解 | 97.8% | 98.2% | 98.4% |
| 最終信号の正解 | 23 / 25 | 25 / 25 | 25 / 25 |
| トラップ通過 | 13 / 14 | 14 / 14 | 14 / 14 |

- トラップ：キーワードなしの結論、別の文脈での同じ単語、先送り・撤回されたアジェンダ、最後の1分で初めて出たアジェンダ。
- 呼び出し1回約0.27秒、**20分の会議1本あたり約 $0.003**。信号の変化は約36秒後（中央値）に反映されます。
- 前段にローカル ASR を付けると、音声30秒分を2秒以内に処理しました。

## クイックスタート：サンプル会議の再生

音声も音声認識も使いません。`run` がテキストの台本を1分ずつリアルタイムのように Jev に入れ、正解と比較します。

```bash
uv sync                                              # Python 3.11 以上、uv が必要
uv run pytest                                        # オフラインテスト
uv run agenda-signal run --lang en --version good --judge fake   # API キーなしで実行

cp .env.example .env                                 # TYPESAFE_API_KEY を設定
uv run agenda-signal run --lang en --version good    # 20回呼び出し、約 $0.003
uv run agenda-signal eval runs/<run_id>              # 指標 + 1分ごとのタイムライン
```

`--lang` は `ko`、`en`、`ja` のいずれかで、`--version` を省くと会議5本すべてを実行します。

## 自分の ASR とつなぐ

音声認識は含まれていません。`my_asr()` に入れて、確定した文ごとに `(開始からの秒数, テキスト)` を
返してください。

```python
from agenda_signal.judge import JevJudge, build_questions
from agenda_signal.models import Agenda, Utterance
from agenda_signal.state import build_state

agendas = [
    Agenda("A1", "Date", "When the workshop will be held."),
    Agenda("A2", "Budget", "How much money can be spent on the workshop."),
    # ...
]
judge = JevJudge()                     # TYPESAFE_API_KEY を読み込みます
questions = build_questions(agendas)
transcript: list[Utterance] = []


def my_asr():
    """ここに自分の音声認識が入ります：確定した文ごとに (t_sec, text) を yield。"""
    raise NotImplementedError("ここに自分の音声認識をつないでください")


last_check = 0.0
for t_sec, text in my_asr():                          # <- 自分の ASR から届く文
    transcript.append(Utterance(t_sec, "unknown", text))
    if t_sec - last_check >= 30:                       # 30秒ごとに判定
        result = judge.evaluate(build_state(transcript, t_sec), questions)
        print({a: p.choice for a, p in result.predictions.items()})   # {'A1': 'green', ...}
        last_check = t_sec
```

- 区切って文字起こしする場合、各区切りの最後の文は次の区切りでもう一度文字起こししてください。途中で切れていることが多いためです。
- アジェンダの説明はわかりやすい1文で書いてください。Jev は指示文を文字どおりに読みます。

デモは Mac で [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper)
（`whisper-large-v3-turbo`）を使い、30秒ごとに判定しました。1回あたり ASR 最大1.1秒、Jev 最大0.7秒でした。

## データセット

| 会議 | 最終信号（A1–A5） |
|---|---|
| `good` · ワークショップ準備、順調 | 🟢🟢🟢🟢🟡 |
| `normal` · ワークショップ準備、時間切れ | 🟢🟡🟡🔴🔴 |
| `bad` · ワークショップ準備、脱線と決定の撤回 | 🟡🔴🔴🟡🔴 |
| `office_move` · オフィス移転 | 🟢🟢🟡🟢🟡 |
| `onboarding` · 新入社員の入社準備 | 🟢🟢🟡🔴🔴 |

```
data/
├── scripts.json            会議 → テーマ + 最終信号の正解
├── agendas/<topic>.json    テーマごとのアジェンダ5つ
├── transcripts/{ko,en,ja}/<meeting>.jsonl    1行に {"t_sec", "speaker", "text"}
├── gt/<meeting>.json       信号が変わるタイミング：{"t_sec", "agenda", "signal"}
└── outlines/<meeting>.md   読みやすい要約とトラップ
```

3言語は発話時刻と正解を共有します。

## 制限

- 20分の会議でのみ検証しました。会議が長いほど、呼び出しごとの入力が大きくなります。
- 架空の会議で、正解は1人がラベル付けしました。
- 実行ごとに結果が少し変わります（500判定中 ±1〜2）。

### 参考：直近の区間だけを送る方式

直近3分と直前の信号だけを送ると、正解率は82%（全体送信は98%）でした。結論が3分の外に出ると
🟢 が 🔴 に戻りました。

- **有利になりうる場合：** 1時間以上の長い会議。全体送信は入力上限・精度・コストの負担になります。
- **改善の方向：** 信号はコードで保持し、Jev は直近の区間で変わったことだけを判定。未実装です。
