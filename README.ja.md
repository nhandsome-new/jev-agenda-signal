# Agenda Signal

**[Jev](https://docs.typesafe.ai/) で会議中のアジェンダをリアルタイムに管理します。**

[English](README.md) · [한국어](README.ko.md)

会議の進行に合わせて、アジェンダごとの信号が会話に応じて変わります。

| 信号 | 意味 |
|---|---|
| 🔴 | まだ話していない |
| 🟡 | 話はしたが、まだ明確な結論がない（先送り・結論の撤回を含む） |
| 🟢 | 明確な結論が出て、その結論が有効 |

会議が終わる前に、どのアジェンダがまだ扱われていないか、どれがまだ決まっていないかを
進行役が確認できます。

![デモ：会議の進行に合わせてアジェンダの信号が変わる](docs/demo.gif)

*16倍速。左：会議画面と Jev が判定したアジェンダの信号。右：ローカル音声認識と Jev 呼び出しが
実際に処理される様子。*

## 仕組み

1分（または30秒）ごとに、それまでの会議テキストを Jev に **1回のリクエスト** で送ります。
アジェンダごとに **Choice 質問を1つ** 付けると、Jev がすべての質問を並列に判定し、
信号と確率を返します。

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

ループと流れはコードが受け持ち、Jev は狭い判断だけを行います。コードは `src/agenda_signal/judge.py`。

## 結果

20分の架空の会議5本を韓国語・英語・日本語で用意し、信号が変わるタイミングを人手で
ラベル付けしました。Jev（`jev-1.13.0`）で1分ごとに判定 → 台本5本 × 20回 × アジェンダ5つ =
言語ごとに500判定。

| 指標 | 韓国語 | 英語 | 日本語 |
|---|---|---|---|
| 各判定時点での信号の正解 | 489 / 500 (97.8%) | 491 / 500 (98.2%) | 492 / 500 (98.4%) |
| 最終信号の正解 | 23 / 25 | 25 / 25 | 25 / 25 |
| トラップ通過 | 13 / 14 | 14 / 14 | 14 / 14 |
| 信号の切り替わり検出 | 30 / 31 | 30 / 31 | 30 / 31 |
| 切り替わり後の反映まで（中央値） | 36秒 | 37秒 | 36秒 |

- 3言語すべてで同じ信号になった判定：490 / 500。
- Jev 呼び出し1回あたり約0.27秒。コストは **20分の会議1本あたり約 $0.003**。
- トラップは実際の会議でよくある場面です：アジェンダのキーワードなしで結論を出す、同じ単語が
  別の文脈で出る、名前だけ出して先送りする、結論の撤回、1文で2つの決定、最後の1分で初めて出た
  アジェンダ。
- 前段にローカル ASR（Whisper large-v3 turbo）を付けた場合、音声30秒分を2秒以内に
  処理し（ASR + Jev）、判定の正解は 97 / 100（韓国語）、112 / 115（英語）でした。

## クイックスタート：サンプル会議の再生

ここでは音声も音声認識も使いません。サンプル会議はテキストの台本で、`run` が台本を
1分ずつリアルタイムの会議のように Jev に入れ、正解と比較します。

Python 3.11 以上と [uv](https://docs.astral.sh/uv/) が必要です。

```bash
uv sync
uv run pytest                                        # オフラインテスト
uv run agenda-signal validate                        # データセットの検査

# API キーなしで全体の流れを確認（フェイク判定器は常に 🔴 と答えます）
uv run agenda-signal run --lang en --version good --judge fake

# Jev で実行
cp .env.example .env                                 # TYPESAFE_API_KEY を設定
uv run agenda-signal run --lang en --version good    # 20回呼び出し、約 $0.003
uv run agenda-signal eval runs/<run_id>              # 指標 + 1分ごとのタイムライン
```

`run` は台本を1分ずつ再生しながら判定し、`runs/<run_id>/ticks.jsonl` に記録します。
`--version` を省くと台本5本すべてを実行し、`--lang` は `ko`、`en`、`ja` のいずれかです。
途中で止まった場合は `run --resume runs/<run_id>` で続きから実行できます。

## 自分の ASR とつなぐ

音声認識は含まれていないので、お好みのものをつないでください。下の `my_asr()` に入れます。
文が確定するたびに `(会議開始からの秒数, テキスト)` を返せばよく、それ以外はそのままで動きます。

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
    """ここに自分の音声認識が入ります。

    確定した文ごとに (t_sec, text) を yield してください。例：Whisper、クラウドの音声認識 API、
    会議ツールのリアルタイム字幕。
    """
    raise NotImplementedError("ここに自分の音声認識をつないでください")


last_check = 0.0
for t_sec, text in my_asr():                          # <- 自分の ASR から届く文
    transcript.append(Utterance(t_sec, "unknown", text))
    if t_sec - last_check >= 30:                       # 30秒ごとに判定
        result = judge.evaluate(build_state(transcript, t_sec), questions)
        signals = {agenda_id: p.choice for agenda_id, p in result.predictions.items()}
        print(signals)                                 # 例：{'A1': 'green', 'A2': 'yellow'}
        last_check = t_sec
```

デモで得たヒント：

- 音声を区切って文字起こしする場合、各区切りの最後の文は確定せず、次の区切りで
  もう一度文字起こししてください。文の途中で切れていることが多いためです。
- 話者の区別はなくても構いません。デモではすべての文を `"unknown"` として送りました。
- アジェンダの説明はわかりやすい1文で書いてください。Jev は指示文を文字どおりに読みます。

## デモの作り方（ローカル Mac）

リアルタイムのデモは、Jev API の呼び出しを除いてすべて Mac 1台で動かしました。
デモ用のツールはこのリポジトリには含めていません。使った構成は以下のとおりです。

| 段階 | 使ったもの | 内容 |
|---|---|---|
| 音声認識 | [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) 0.4.3、モデル `mlx-community/whisper-large-v3-turbo` | 30秒ごとに新しく入った音声を文字起こしし、最後の文は次の回にもう一度文字起こし |
| アジェンダの信号 | Jev `jev-1.13.0` | 30秒ごとに、それまでの会議テキスト全体で判定（このリポジトリと同じ方式） |

30秒ごとの処理時間（実測）：ASR 最大1.1秒、Jev 最大0.7秒。

## データセット

| 台本 | 会議 | 最終信号（A1–A5） |
|---|---|---|
| `good` | ワークショップ準備、うまく進んだ会議 | 🟢🟢🟢🟢🟡 |
| `normal` | ワークショップ準備、時間が足りなくなった会議 | 🟢🟡🟡🔴🔴 |
| `bad` | ワークショップ準備、脱線と決定の撤回 | 🟡🔴🔴🟡🔴 |
| `office_move` | オフィス移転 | 🟢🟢🟡🟢🟡 |
| `onboarding` | 新入社員の入社準備 | 🟢🟢🟡🔴🔴 |

```
data/
├── scripts.json                     台本 → テーマ + 最終信号の正解
├── agendas/<topic>.json             テーマごとのアジェンダ5つ
├── transcripts/{ko,en,ja}/<script>.jsonl
├── gt/<script>.json                 正解：信号が変わるタイミング
└── outlines/<script>.md             人が読むための要約、トラップ、想定される信号
```

台本の1行：`{"t_sec": 0, "speaker": "lead", "text": "..."}`。
正解イベント：`{"t_sec": 272, "agenda": "A1", "signal": "green"}`。ある時点の信号は、
その時点以前の最後のイベントです（なければ 🔴）。英語・日本語は発話時刻を保ったままの翻訳なので、
正解を共有します。

## 制限

- 20分の会議でのみ検証しました。毎回会議テキスト全体を送るため、会議が長くなるほど入力が
  大きくなります（今回の台本では1分あたり約235トークン）。Jev の入力上限（3.2万トークン）、
  長い入力での精度、呼び出しあたりのコスト増加は検証していません。
- 架空の会議であり、正解は1人がラベル付けしました。
- 実行ごとに結果が少し変わります（500判定中 ±1〜2）。

### 参考：直近の区間だけを送る方式

直近3分の会話と直前の信号だけを送る方式も試しました。正解率は82%（全体送信は98%）で、
結論が3分の外に出ると 🟢 が 🔴 に戻る誤りが最も多くなりました。

- **有利になりうる場合：** 1時間以上の長い会議。全体送信は入力上限・精度・コストの負担になります。
- **改善の方向：** 信号はコードで保持し、Jev は直近の区間で変わったことだけを判定。未実装です。
