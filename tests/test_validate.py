import json

from agenda_signal.validate import Limits, validate

SMALL = Limits(min_duration_sec=0, max_duration_sec=10_000, min_chars=0, max_chars=10_000)


def test_fixture_is_valid(data_dir):
    assert validate(data_dir, SMALL) == []


def test_default_limits_reject_short_transcript(data_dir):
    errors = validate(data_dir)
    assert any("duration" in e for e in errors)
    assert any("chars" in e for e in errors)


def test_gt_must_match_matrix(data_dir):
    scripts = json.loads((data_dir / "scripts.json").read_text())
    scripts["sample"]["final"]["A1"] = "green"
    (data_dir / "scripts.json").write_text(json.dumps(scripts))
    assert any("scripts.json says green" in e for e in validate(data_dir, SMALL))


def test_translation_must_keep_timing(data_dir):
    src = (data_dir / "transcripts" / "ko" / "sample.jsonl").read_text().splitlines()
    (data_dir / "transcripts" / "en").mkdir()
    (data_dir / "transcripts" / "en" / "sample.jsonl").write_text("\n".join(src[:-1]))
    assert any("timing differs" in e for e in validate(data_dir, SMALL))
