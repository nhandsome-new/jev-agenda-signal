from agenda_signal.metrics import agreement, evaluate, macro_f1, signal_latencies
from agenda_signal.models import Event, GroundTruth, Trap

GT = GroundTruth(
    "V1",
    events=(Event(20, "A1", "yellow"), Event(95, "A1", "green"), Event(175, "A1", "yellow")),
    traps=(Trap("reversal", "A1", "yellow"),),
)


def tick(t, a1, a2="red"):
    return {
        "version": "V1", "t_sec": t, "model": "fake", "input_tokens": 10, "latency_ms": 5.0,
        "predictions": {"A1": {"choice": a1}, "A2": {"choice": a2}},
    }


TICKS = [tick(60, "yellow"), tick(120, "yellow"), tick(180, "green")]


def test_signal_at_follows_events():
    assert GT.signal_at("A1", 10) == "red"
    assert GT.signal_at("A1", 100) == "green"
    assert GT.final("A1") == "yellow"
    assert GT.final("A2") == "red"


def test_latency_and_misses():
    result = {r["t_sec"]: r["delay_sec"] for r in signal_latencies(TICKS, GT)}
    assert result[20] == 40      # yellow at 20, first seen at tick 60
    assert result[95] is None    # green never seen before the next event at 175
    assert result[175] is None   # model still says green at 180


def test_evaluate_final_and_traps():
    m = evaluate(TICKS, {"V1": GT})
    assert m["final"]["n"] == 2
    assert m["final"]["accuracy"] == 0.5          # A1 wrong (green vs yellow), A2 right
    assert m["traps"] == [{"id": "reversal", "expected": "yellow", "predicted": "green", "passed": False}]
    assert m["cost"]["input_tokens"] == 30
    # A1 is right at 60 s only; A2 is right at every tick.
    assert (m["tick"]["n"], m["tick"]["accuracy"]) == (6, 4 / 6)


def test_macro_f1_perfect_and_empty():
    assert macro_f1([("red", "red"), ("green", "green")]) == 1.0
    assert macro_f1([]) == 0.0


def test_agreement():
    other = [tick(60, "yellow"), tick(120, "green"), tick(180, "green")]
    result = agreement({"ko": TICKS, "en": other})
    assert (result["agree"], result["n"]) == (5, 6)
