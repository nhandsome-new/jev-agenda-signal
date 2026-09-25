"""Evaluation metrics. Pure functions over tick records and ground truth."""

from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence

from .models import SIGNALS, GroundTruth

CHECKPOINTS = tuple(range(300, 1201, 300))
EMOJI = {"red": "🔴", "yellow": "🟡", "green": "🟢"}

Pair = tuple[str, str]  # (ground truth, prediction)


# --- Lookups ----------------------------------------------------------------


def group_by_version(ticks: Sequence[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in ticks:
        grouped[record["version"]].append(record)
    return {v: sorted(rs, key=lambda r: r["t_sec"]) for v, rs in grouped.items()}


def predicted_at(version_ticks: Sequence[dict], agenda: str, t_sec: float) -> str:
    """Prediction of the last tick at or before t_sec; red before the first tick."""
    signal = "red"
    for record in version_ticks:
        if record["t_sec"] > t_sec:
            break
        signal = record["predictions"][agenda]["choice"]
    return signal


# --- Classification metrics -------------------------------------------------


def accuracy(pairs: Sequence[Pair]) -> float:
    return sum(g == p for g, p in pairs) / len(pairs) if pairs else 0.0


def confusion(pairs: Sequence[Pair]) -> dict[str, dict[str, int]]:
    matrix = {g: {p: 0 for p in SIGNALS} for g in SIGNALS}
    for g, p in pairs:
        matrix[g][p] += 1
    return matrix


def macro_f1(pairs: Sequence[Pair]) -> float:
    """Unweighted mean F1 over classes that appear in either labels or predictions."""
    classes = {g for g, _ in pairs} | {p for _, p in pairs}
    scores = []
    for c in sorted(classes):
        tp = sum(g == c and p == c for g, p in pairs)
        fp = sum(g != c and p == c for g, p in pairs)
        fn = sum(g == c and p != c for g, p in pairs)
        scores.append(2 * tp / (2 * tp + fp + fn))
    return sum(scores) / len(scores) if scores else 0.0


# --- Timing -----------------------------------------------------------------


def signal_latencies(version_ticks: Sequence[dict], gt: GroundTruth) -> list[dict]:
    """For each GT event: seconds until the prediction first matches the new signal.

    The search stops at the next event for the same agenda; if the prediction
    never matches in that span, `delay_sec` is None (missed).
    """
    results = []
    for event in gt.events:
        next_t = min(
            (e.t_sec for e in gt.events if e.agenda == event.agenda and e.t_sec > event.t_sec),
            default=float("inf"),
        )
        delay = None
        for record in version_ticks:
            if event.t_sec <= record["t_sec"] < next_t:
                if record["predictions"][event.agenda]["choice"] == event.signal:
                    delay = record["t_sec"] - event.t_sec
                    break
        results.append({
            "version": gt.version, "agenda": event.agenda, "t_sec": event.t_sec,
            "signal": event.signal, "delay_sec": delay,
        })
    return results


def _p95(values: Sequence[float]) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))]


# --- Top level --------------------------------------------------------------


def evaluate(ticks: Sequence[dict], gts: Mapping[str, GroundTruth]) -> dict:
    by_version = group_by_version(ticks)
    versions = sorted(v for v in by_version if v in gts)
    ids = {v: list(by_version[v][0]["predictions"]) for v in versions}

    final_pairs = [
        (gts[v].final(a), predicted_at(by_version[v], a, float("inf")))
        for v in versions for a in ids[v]
    ]
    tick_pairs = [
        (gts[v].signal_at(a, r["t_sec"]), r["predictions"][a]["choice"])
        for v in versions for r in by_version[v] for a in ids[v]
    ]
    checkpoint_accuracy = {
        t: accuracy([
            (gts[v].signal_at(a, t), predicted_at(by_version[v], a, t))
            for v in versions for a in ids[v]
        ])
        for t in CHECKPOINTS
    }

    latencies = [x for v in versions for x in signal_latencies(by_version[v], gts[v])]
    delays = [x["delay_sec"] for x in latencies if x["delay_sec"] is not None]

    traps = [
        {
            "id": trap.id,
            "expected": trap.expected_final,
            "predicted": predicted_at(by_version[v], trap.agenda, float("inf")),
        }
        for v in versions for trap in gts[v].traps
    ]
    for trap in traps:
        trap["passed"] = trap["expected"] == trap["predicted"]

    timeline = {
        v: [
            {
                "t_sec": r["t_sec"],
                "predicted": {a: r["predictions"][a]["choice"] for a in ids[v]},
                "expected": {a: gts[v].signal_at(a, r["t_sec"]) for a in ids[v]},
            }
            for r in by_version[v]
        ]
        for v in versions
    }

    call_ms = [r["latency_ms"] for r in ticks]
    return {
        "versions": versions,
        "final": {
            "n": len(final_pairs),
            "accuracy": accuracy(final_pairs),
            "macro_f1": macro_f1(final_pairs),
            "confusion": confusion(final_pairs),
        },
        "tick": {"n": len(tick_pairs), "accuracy": accuracy(tick_pairs)},
        "checkpoint_accuracy": checkpoint_accuracy,
        "latency": {
            "events": len(latencies),
            "missed": len(latencies) - len(delays),
            "median_sec": statistics.median(delays) if delays else None,
            "max_sec": max(delays) if delays else None,
            "detail": latencies,
        },
        "traps": traps,
        "cost": {
            "calls": len(ticks),
            "input_tokens": sum(r["input_tokens"] for r in ticks),
            "latency_ms_mean": statistics.fmean(call_ms) if call_ms else None,
            "latency_ms_p95": _p95(call_ms) if call_ms else None,
        },
        "models": sorted({r["model"] for r in ticks}),
        "timeline": timeline,
    }


def agreement(runs: Mapping[str, Sequence[dict]]) -> dict:
    """Share of (version, t_sec, agenda) predictions identical across all runs."""
    keyed = [
        {
            (r["version"], r["t_sec"], a): p["choice"]
            for r in ticks for a, p in r["predictions"].items()
        }
        for ticks in runs.values()
    ]
    common = set.intersection(*(set(k) for k in keyed)) if keyed else set()
    agree = sum(len({k_[key] for k_ in keyed}) == 1 for key in common)
    return {
        "runs": list(runs),
        "n": len(common),
        "agree": agree,
        "rate": agree / len(common) if common else 0.0,
    }


# --- Rendering --------------------------------------------------------------


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _ms(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.0f} ms"


def to_markdown(m: dict) -> str:
    f = m["final"]
    lines = [
        f"Versions: {', '.join(m['versions'])} · Models: {', '.join(m['models'])}",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Final accuracy | {_pct(f['accuracy'])} (n={f['n']}) |",
        f"| Final macro-F1 | {f['macro_f1']:.3f} |",
        f"| Tick accuracy (every tick) | {_pct(m['tick']['accuracy'])} (n={m['tick']['n']}) |",
        f"| Latency median / max | {m['latency']['median_sec']} s / {m['latency']['max_sec']} s |",
        f"| Events missed | {m['latency']['missed']} / {m['latency']['events']} |",
        f"| Traps passed | {sum(t['passed'] for t in m['traps'])} / {len(m['traps'])} |",
        f"| Calls / input tokens | {m['cost']['calls']} / {m['cost']['input_tokens']} |",
        f"| Call latency mean / p95 | {_ms(m['cost']['latency_ms_mean'])} / {_ms(m['cost']['latency_ms_p95'])} |",
        "",
        "Confusion (rows = ground truth, columns = prediction):",
        "",
        "| | " + " | ".join(SIGNALS) + " |",
        "|---|" + "---|" * len(SIGNALS),
    ]
    for g in SIGNALS:
        lines.append(f"| {g} | " + " | ".join(str(f["confusion"][g][p]) for p in SIGNALS) + " |")
    lines += ["", "| Checkpoint (s) | Accuracy |", "|---|---|"]
    lines += [f"| {t} | {_pct(a)} |" for t, a in m["checkpoint_accuracy"].items()]
    if m["traps"]:
        lines += ["", "| Trap | Expected | Predicted | Pass |", "|---|---|---|---|"]
        lines += [
            f"| {t['id']} | {t['expected']} | {t['predicted']} | {'✓' if t['passed'] else '✗'} |"
            for t in m["traps"]
        ]
    for version, rows in m["timeline"].items():
        agendas = list(rows[0]["predicted"]) if rows else []
        lines += [
            "", f"Timeline `{version}` (Jev / expected, ✗ = differs):", "",
            "| Time | Jev | Expected | |", "|---|---|---|---|",
        ]
        for row in rows:
            got = "".join(EMOJI[row["predicted"][a]] for a in agendas)
            want = "".join(EMOJI[row["expected"][a]] for a in agendas)
            t = row["t_sec"]
            lines.append(f"| {t // 60:02d}:{t % 60:02d} | {got} | {want} | {'' if got == want else '✗'} |")
    return "\n".join(lines) + "\n"
