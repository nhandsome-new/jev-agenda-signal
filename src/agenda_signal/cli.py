"""Command line entry point: `agenda-signal validate | run | eval`."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .judge import DEFAULT_MODEL, make_judge
from .metrics import agreement, evaluate, to_markdown
from .models import load_gt
from .runner import available_versions, create_run, execute, load_config, load_ticks
from .validate import validate


def load_dotenv(path: Path = Path(".env")) -> None:
    """Minimal .env loader. Existing environment variables win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def cmd_validate(args: argparse.Namespace) -> int:
    errors = validate(args.data)
    for e in errors:
        print(f"ERROR {e}")
    print("OK" if not errors else f"{len(errors)} error(s)")
    return 1 if errors else 0


def cmd_run(args: argparse.Namespace) -> int:
    if args.resume:
        run_dir = args.resume
        config = load_config(run_dir)
        judge_name, model = config["judge"], config["model"]
    else:
        versions = args.version or available_versions(args.data, args.lang)
        if not versions:
            print(f"No transcripts in {args.data / 'transcripts' / args.lang}")
            return 1
        run_dir = create_run(
            args.runs, args.data, args.lang, versions, args.judge, args.model
        )
        judge_name, model = args.judge, args.model

    print(f"Run: {run_dir}")
    written = execute(run_dir, args.data, make_judge(judge_name, model))
    print(f"Wrote {written} tick(s)")
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    gts = {p.stem: load_gt(p) for p in sorted((args.data / "gt").glob("*.json"))}

    for run_dir in args.run_dirs:
        metrics = evaluate(load_ticks(run_dir), gts)
        (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
        report = to_markdown(metrics)
        (run_dir / "metrics.md").write_text(report)
        print(f"## {run_dir.name}\n\n{report}")

    if len(args.run_dirs) > 1:
        result = agreement({d.name: load_ticks(d) for d in args.run_dirs})
        print(f"Agreement across runs: {result['agree']}/{result['n']} ({result['rate']:.1%})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agenda-signal")
    parser.add_argument("--data", type=Path, default=Path("data"), help="data directory")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="check all data files").set_defaults(func=cmd_validate)

    run = sub.add_parser("run", help="replay transcripts and record judgments")
    run.add_argument("--lang", default="ko")
    run.add_argument("--version", action="append", help="e.g. good; repeatable; default all")
    run.add_argument("--judge", choices=("jev", "fake"), default="jev")
    run.add_argument("--model", default=DEFAULT_MODEL)
    run.add_argument("--runs", type=Path, default=Path("runs"), help="output root")
    run.add_argument("--resume", type=Path, help="continue an existing run directory")
    run.set_defaults(func=cmd_run)

    ev = sub.add_parser("eval", help="compute metrics for one or more runs")
    ev.add_argument("run_dirs", type=Path, nargs="+")
    ev.set_defaults(func=cmd_eval)
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
