from agenda_signal.models import Utterance
from agenda_signal.state import build_state

UTTS = [Utterance(t, "lead", f"line {t}") for t in (0, 60, 120, 200)]


def test_state_includes_everything_up_to_t():
    state = build_state(UTTS, 120)
    assert [x["text"] for x in state["transcript"]] == ["line 0", "line 60", "line 120"]
