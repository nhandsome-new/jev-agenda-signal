from agenda_signal.judge import FakeJudge
from agenda_signal.runner import TICKS_FILE, create_run, execute, load_ticks


def test_fake_run_writes_one_line_per_tick_and_resumes(data_dir, tmp_path):
    run_dir = create_run(tmp_path / "runs", data_dir, "ko", ["sample"], "fake", "fake")

    assert execute(run_dir, data_dir, FakeJudge()) == 3   # ticks at 60, 120, 180
    ticks = load_ticks(run_dir)
    assert [t["t_sec"] for t in ticks] == [60, 120, 180]
    assert set(ticks[0]["predictions"]) == {"A1", "A2", "A3", "A4", "A5"}

    # Drop the last line to simulate a crash, then resume.
    lines = (run_dir / TICKS_FILE).read_text().splitlines(keepends=True)
    (run_dir / TICKS_FILE).write_text("".join(lines[:-1]))
    assert execute(run_dir, data_dir, FakeJudge()) == 1
    assert len(load_ticks(run_dir)) == 3
