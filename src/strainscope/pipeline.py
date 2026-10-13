"""
src/strainscope/pipeline.py (StrainScope Phase 8): the whole build in one command.
==================================================================================

WHAT IT DOES
------------
Runs the scripts of Phases 1 to 5 in the right order, each in a fresh Python
process, shows what they print as they go, stops at the first step that
fails, and ends with a summary and the same health check the app uses.

The steps come from PIPELINES in src/strainscope/service.py, the lists the
app's build buttons run too, so the terminal and the app can never drift
apart. A recipe card works the same way: one card, whoever does the cooking.

THE PLANS
---------
  everything  (the default) regenerate the library, clean it into a fresh
              database, and recompute every result: integration (DIABLO too,
              when R is installed), the models and the knowledge graph.
              5 to 10 minutes (about 4 without R).
  database    the quick one: regenerate, clean, and load the committed results
              of Phases 3, 4 and 5 into the database. About 15 seconds.
  real        fetch the five public databases, then rebuild with their tables
              (needs the internet; a few minutes).
  probe       ask the public databases what a fetch would bring (downloads nothing).

and two for a dataset of Phase 9 (src/strainscope/datasets.py), chosen for
you by --dataset:

  simulate    a simulated dataset: generate it with its own seed and size,
              then every phase, all inside the dataset's folder.
  workflow    your own data: clean it, then every phase, inside its folder.

and one check, which builds nothing:

  compare     compare the results in artifacts/ with the committed ones (Git's
              last commit): every number to within 0.001, every word exactly.
              With --dataset NAME: that dataset's results against the
              library's committed ones, the check that a simulated dataset
              with seed 42 and 600 strains rebuilds the library (Phase 9).
              Run it after `everything` to see that a rebuild from scratch
              gives the same results on your computer. On an ARM processor
              (a Mac with an M chip, for example), the random forest's numbers
              are listed apart: see ARM_SENSITIVE below.

USAGE
-----
    python src/strainscope/pipeline.py                 everything
    python src/strainscope/pipeline.py database        the quick one
    python src/strainscope/pipeline.py compare         rebuilt results vs committed ones
    python src/strainscope/pipeline.py compare --all   the same, with every difference listed
    python src/strainscope/pipeline.py --list          the plans and their steps; runs nothing
    python src/strainscope/pipeline.py --from 4        start at step 4 (after fixing a failed step)
    python src/strainscope/pipeline.py --quiet         only the steps and the summary
    python src/strainscope/pipeline.py --dataset trial every phase on the dataset "trial" (Phase 9)
    python src/strainscope/pipeline.py --dataset trial --from 3   ... starting at its step 3
    python src/strainscope/pipeline.py compare --dataset seed42   a dataset's results vs the library's

The exit code is 0 when everything finished (or matched), 1 when a step
failed (or a result differs) and 130 when you pressed Ctrl+C, so continuous
integration (.github/workflows/ci.yml) can tell the three apart.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

# Make `strainscope` importable no matter where the script is run from.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strainscope import paths  # noqa: E402
from strainscope import service as sv  # noqa: E402

ROOT = sv.ROOT
ARTIFACTS = sv.ARTIFACTS
TOLERANCE = 0.001        # numbers closer than this count as the same (rounding, package versions)
SHOW_ON_FAILURE = 30     # with --quiet, the last lines of a step that failed are still shown

# Lines and files that describe the computer a result was made on, not the
# result itself. `compare` leaves them out and says so.
COMPUTER_LINES = {
    "model/model_summary.csv": {"scikit_learn_version", "model_file_kb"},
    "integration/diablo_summary.csv": {"mixomics_version", "r_version", "runtime_seconds"},
}
NOT_COMPARED = {
    "model/strainscope_model.joblib": "the saved model, whose bytes depend on the package versions; "
                                      "its results are in the tables",
    "graph/knowledge_layer.graphml": "the same nodes and edges as nodes.csv and edges.csv, in another format",
}
# These four also hold the real reference data (BacDive strains, KEGG pathways,
# RefMet classes). They can only match when the database has the real tables.
REAL_DATA_TABLES = ("graph/nodes.csv", "graph/edges.csv", "graph/hubs.csv", "graph/graph_summary.csv")
# Files that exist only when DIABLO (R) has run (besides integration/diablo_*.csv),
# and files that hold some of DIABLO's results. A dataset that ran without R
# can't match these; compare --dataset says so instead of counting them (Phase 9).
DIABLO_FILES = ("integration/language_agreement.csv", "model/phase3_agreement.csv")
DIABLO_DEPENDENT = ("integration/signature_report_card.csv", "model/feature_importance.csv",
                    "graph/knowledge_vs_data.csv", "graph/nodes.csv", "graph/edges.csv", "graph/hubs.csv",
                    "graph/graph_summary.csv")
ID_COLUMNS = ("strain_id", "node_id", "feature", "key", "approach", "model_key")   # names a row in a message

# ARM processors (Apple's M chips, and some Linux servers) can do a
# multiplication and an addition in one step and round once, where the usual
# Intel and AMD processors round twice. Inside scikit-learn's tree code that
# changes which of two almost equal splits a tree takes, so the random forest
# (one of the models Phase 4 compares, not the one behind the ranking) comes
# out slightly different on them. On such a computer, `compare` lists these
# numbers apart instead of counting them as a difference. Everything else must
# still match. (Found by the automatic tests on GitHub's ARM Macs, Phase 8.)
ARM = platform.machine().lower() in ("arm64", "aarch64")
ARM_SENSITIVE = {
    "model/oof_predictions.csv": {"columns": {"p_random_forest", "p_random_forest_sd",
                                              "correct_share_random_forest"}},
    "model/scoreboard.csv": {"rows": {"random_forest"}},
    "model/hard_strains.csv": {"columns": {"missed_by_all_models"}},   # missed by every model, the forest too
}


# =============================================================================
# 1. RUNNING A PLAN
# =============================================================================

def _duration(seconds: float) -> str:
    seconds = round(seconds)
    return f"{seconds // 60} min {seconds % 60} s" if seconds >= 60 else f"{seconds} s"


def print_plans() -> None:
    """--list: every plan and its steps, exactly as they'd be typed."""
    print("  ── StrainScope pipeline: the plans ─────────────────────────────")
    for name, spec in sv.PIPELINES.items():
        default = " (the default)" if name == "everything" else ""
        print(f"\n  {name}{default}: {spec['title']}, {spec['takes']}")
        for number, step in enumerate(spec["steps"], start=1):
            print(f"      {number}. {sv.step_label(step)}")
    print("\n  compare: the results in artifacts/ against the committed ones (builds nothing)")
    print("\n  Run one with: python src/strainscope/pipeline.py <plan>")
    print("  On a dataset (simulate or workflow, chosen for you): python src/strainscope/pipeline.py --dataset NAME")


def run(name: str, start: int = 1, quiet: bool = False, dataset: str | None = None) -> int:
    """Run one plan and print it; return the exit code (0, 1 or 130)."""
    spec = sv.PIPELINES[name]
    steps = spec["steps"]
    print(f"  ── StrainScope pipeline: {name} ({len(steps)} steps, {spec['takes']}) ──")
    print(f"  It {spec['what']}.")
    if dataset:
        print(f"  Dataset: {dataset}, in {paths.rel(paths.locate(dataset))}/ (the library isn't touched).")
    if start > 1:
        print(f"  Starting at step {start}, as asked (--from {start}).")
    finished: list[tuple[int, str, float]] = []
    recent: list[str] = []
    started = time.time()
    outcome = None
    events = sv.pipeline_events(name, ROOT, start, dataset)
    try:
        for e in events:
            if e["event"] == "start":
                recent = []
                print(f"\n  [{e['step']}/{len(steps)}] {e['label']}", flush=True)
            elif e["event"] == "line":
                recent = (recent + [e["text"]])[-SHOW_ON_FAILURE:]
                if not quiet:
                    print(e["text"], flush=True)
            elif e["event"] == "end":
                finished.append((e["step"], e["label"], e["seconds"]))
                print(f"  ✓ step {e['step']} done in {_duration(e['seconds'])}", flush=True)
            else:
                outcome = e
    except KeyboardInterrupt:
        events.close()                               # stops the running step and frees the lock
        stopped = len(finished) + start
        again = f"--dataset {dataset}" if dataset else name
        print(f"\n  Stopped by you during step {stopped}. The steps before it finished; to carry on "
              f"from there: python src/strainscope/pipeline.py {again} --from {stopped}")
        return 130

    print("\n  ── Summary ─────────────────────────────────────────────────────")
    for number, label, seconds in finished:
        print(f"  ✓ {number}. {label:<52} {_duration(seconds):>12}")
    if outcome is None or outcome["event"] == "failed":
        if quiet and recent and outcome and outcome.get("step"):
            print(f"\n  The last lines step {outcome['step']} printed:")
            for line in recent:
                print(f"    {line}")
        print(f"  ✗ {outcome['text'] if outcome else 'The pipeline stopped.'}")
        if outcome and outcome.get("step"):
            again = f"--dataset {dataset}" if dataset else name
            print(f"  Fix what the step says, then carry on from there: "
                  f"python src/strainscope/pipeline.py {again} --from {outcome['step']}")
        return 1
    print(f"  {outcome['text'].rstrip('.')} in {_duration(time.time() - started)}.")
    if dataset:
        f = paths.folders(dataset)
        print()
        sv._print_status(f.db, f.artifacts)
        print(f"\n  See it in the app: choose {dataset} under Dataset in the sidebar. "
              f"Step by step: python src/strainscope/datasets.py show {dataset}")
        return 0
    if name != "probe":
        print()
        sv._print_status()
    if name in ("everything", "real"):
        print("\n  Compare the rebuilt results with the committed ones: python src/strainscope/pipeline.py compare")
    return 0


# =============================================================================
# 2. COMPARE: the rebuilt results against the committed ones
# =============================================================================

def git_ready(root: Path = ROOT) -> bool:
    """True when Git is installed and this folder is a Git repository."""
    try:
        out = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=root, capture_output=True)
    except FileNotFoundError:
        return False
    return out.returncode == 0


def committed(path: Path, root: Path = ROOT) -> str | None:
    """The file as it was in the last commit, or None when Git doesn't know it."""
    rel = path.relative_to(root).as_posix()
    out = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=root, capture_output=True)
    return out.stdout.decode("utf-8") if out.returncode == 0 else None


def _number(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None


def same_cell(old: str, new: str) -> bool:
    """Two cells match when they're the same words, or numbers within TOLERANCE."""
    if old == new:
        return True
    a, b = _number(old), _number(new)
    if a is None or b is None:
        return False
    if a != a and b != b:            # both "nan"
        return True
    return abs(a - b) <= TOLERANCE


def table_differences(old_text: str, new_text: str, skip_keys: set[str] = frozenset()) -> tuple[list, list]:
    """The differences between two CSV texts: (cells, problems). `cells` holds
    one (row number, row name, column, committed, now) per cell that differs;
    `problems` the differences in shape (columns, number of rows). Rows whose
    first cell is in skip_keys are left out (a key,value table's lines about
    the computer)."""
    old = [r for r in csv.reader(io.StringIO(old_text)) if not (r and r[0] in skip_keys)]
    new = [r for r in csv.reader(io.StringIO(new_text)) if not (r and r[0] in skip_keys)]
    if not old or not new:
        return [], ["one of the two is empty"]
    if old[0] != new[0]:
        return [], [f"the columns differ: {', '.join(old[0])} committed, {', '.join(new[0])} now"]
    if len(old) != len(new):
        return [], [f"{len(old) - 1} rows committed, {len(new) - 1} now"]
    names = [c for c in ID_COLUMNS if c in old[0]]
    who = old[0].index(names[0]) if names else 0      # the column that names a row in messages
    cells = [(row_number, a[who], column, x, y)
             for row_number, (a, b) in enumerate(zip(old[1:], new[1:]), start=1)
             for column, x, y in zip(old[0], a, b) if not same_cell(x, y)]
    return cells, []


def _sentence(cell: tuple) -> str:
    row_number, name, column, x, y = cell
    return f"row {row_number} ({name}), {column}: {x} committed, {y} now"


def compare_tables(old_text: str, new_text: str, skip_keys: set[str] = frozenset()) -> list[str]:
    """Differences between two CSV texts, as sentences (empty when they match)."""
    cells, problems = table_differences(old_text, new_text, skip_keys)
    return problems + [_sentence(c) for c in cells]


def arm_expected(rel: str, cell: tuple) -> bool:
    """True when this cell is one of the random forest's numbers that an ARM
    processor is expected to change (ARM_SENSITIVE)."""
    rule = ARM_SENSITIVE.get(rel, {})
    return cell[2] in rule.get("columns", ()) or cell[1] in rule.get("rows", ())


def compare_json(old_text: str, new_text: str, skip: tuple[str, ...] = ("versions",)) -> list[str]:
    """The model card, without the part that records package versions."""
    old, new = json.loads(old_text), json.loads(new_text)
    problems = []

    def walk(a, b, where):
        if isinstance(a, dict) and isinstance(b, dict):
            for k in sorted(set(a) | set(b)):
                if where == "" and k in skip:
                    continue
                walk(a.get(k), b.get(k), f"{where}.{k}" if where else k)
        elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
            if abs(a - b) > TOLERANCE:
                problems.append(f"{where}: {a} committed, {b} now")
        elif a != b:
            problems.append(f"{where}: {json.dumps(a)} committed, {json.dumps(b)} now")
    walk(old, new, "")
    return problems


def has_real_tables(db_path: Path = sv.DB_PATH) -> bool:
    return any(t.startswith("real_") for t in sv.database_tables(db_path)["table"])


def compare(root: Path = ROOT, db_path: Path = sv.DB_PATH, dataset: str | Path | None = None) -> dict:
    """Compare every committed result file in artifacts/ with the one on disk.
    Returns {"matched": [...], "differ": {path: [sentences]}, "skipped": {path: reason},
    "expected": {path: [sentences]}}; the last holds, on an ARM processor only,
    files whose only differences are the random forest's numbers (ARM_SENSITIVE).

    With `dataset` (Phase 9), the files on disk are that dataset's results, so
    a simulated dataset with seed 42 and 600 strains can show that it rebuilds
    the library: the same recipe and the same data give the same results."""
    artifacts = root / "artifacts"
    here = artifacts if dataset is None else paths.folders(dataset).artifacts
    if dataset is not None:
        db_path = paths.folders(dataset).db
    real = has_real_tables(db_path)
    diablo = (here / "integration" / "diablo_signature.csv").exists()
    out = {"matched": [], "differ": {}, "skipped": {}, "expected": {}}
    for path in sorted(artifacts.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(artifacts).as_posix()
        if dataset is not None:
            if not diablo and rel in DIABLO_DEPENDENT:
                out["skipped"][rel] = ("they hold some of DIABLO's results too, and DIABLO didn't run for this "
                                       "dataset: R isn't installed here")
                continue
            if not (here / rel).exists():
                out["skipped"][rel] = ("not made for this dataset" + (
                    ": DIABLO runs only where R is installed" if "diablo" in rel or rel in DIABLO_FILES else ""))
                continue
            path = here / rel
        if rel in NOT_COMPARED:
            out["skipped"][rel] = NOT_COMPARED[rel]
            continue
        if rel in REAL_DATA_TABLES and not real:
            out["skipped"][rel] = ("they also hold the real reference data, and this database has no real "
                                   "tables; python src/strainscope/pipeline.py real fetches them")
            continue
        old = committed(artifacts / rel, root)
        if old is None:
            out["skipped"][rel] = "not in the last commit: a new file"
            continue
        new = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            # a dataset's model card names its own database file; everything else must match
            problems = [p for p in compare_json(old, new)
                        if dataset is None or not p.startswith("training_data.source:")]
        elif path.suffix == ".csv":
            cells, problems = table_differences(old, new, COMPUTER_LINES.get(rel, set()))
            if ARM and rel in ARM_SENSITIVE:
                expected = [c for c in cells if arm_expected(rel, c)]
                cells = [c for c in cells if not arm_expected(rel, c)]
                if expected and not cells and not problems:
                    out["expected"][rel] = [_sentence(c) for c in expected]
                    continue
            problems = problems + [_sentence(c) for c in cells]
        else:
            problems = [] if old == new else ["the text differs"]
        if problems:
            out["differ"][rel] = problems
        else:
            out["matched"].append(rel)
    return out


def print_compare(result: dict, show_all: bool = False, dataset: str | None = None) -> int:
    if dataset:
        print(f"  ── StrainScope: dataset {dataset}'s results against the library's committed ones ──")
    else:
        print("  ── StrainScope: the results in artifacts/ against the committed ones ──")
    print(f"  Committed means Git's last commit. Numbers count as the same within {TOLERANCE}.")
    shown = None if show_all else 3
    by_folder: dict[str, int] = {}
    for rel in result["matched"]:
        by_folder[rel.split("/")[0]] = by_folder.get(rel.split("/")[0], 0) + 1
    for folder, n in sorted(by_folder.items()):
        print(f"  ✓ artifacts/{folder}/: {n} file(s) match")
    for rel, problems in result["differ"].items():
        print(f"  ✗ artifacts/{rel}:")
        for p in problems[:shown]:
            print(f"      {p}")
        if len(problems) > len(problems[:shown]):
            print(f"      ... and {len(problems) - 3} more (--all lists them)")
    expected = result.get("expected", {})
    for rel, cells in expected.items():
        print(f"  · as expected on this ARM processor: artifacts/{rel}, {len(cells)} of the random forest's numbers")
        for p in cells[:None if show_all else 1]:
            print(f"      {p}")
    if expected:
        print("      (ARM processors round some sums inside the tree code differently; "
              "docs/09-packaging.md, notes from the build)")
    reasons: dict[str, list[str]] = {}
    for rel, why in result["skipped"].items():
        reasons.setdefault(why, []).append(f"artifacts/{rel}")
    for why, files in reasons.items():
        print(f"  · not compared: {', '.join(files)}")
        print(f"      ({why})")
    lines = ", ".join(f"{p.split('/')[-1]} ({', '.join(sorted(keys))})" for p, keys in COMPUTER_LINES.items())
    print(f"  · lines about the computer, left out: {lines}; and the package versions in model_card.json")
    if result["differ"]:
        print(f"\n  {len(result['differ'])} file(s) differ from the committed results. If you changed the code "
              "on purpose, that's expected; otherwise docs/09-packaging.md (what could go wrong) helps.")
        return 1
    if expected:
        print(f"\n  All {len(result['matched'])} other compared files match the committed results.")
        return 0
    print(f"\n  All {len(result['matched'])} compared files match the committed results.")
    return 0


# =============================================================================
# 3. THE COMMAND LINE
# =============================================================================

def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):          # ✓ and ✗ must print even when the output goes to a file
        if (stream.encoding or "").lower() not in ("utf-8", "utf8"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    plans = [*sv.PIPELINES, "compare"]
    parser = argparse.ArgumentParser(
        description="StrainScope Phase 8: rebuild everything with one command (docs/09-packaging.md).")
    parser.add_argument("plan", nargs="?", default="everything", choices=plans,
                        help="what to run (default: everything); 'compare' checks the results instead")
    parser.add_argument("--list", action="store_true", help="show the plans and their steps, run nothing")
    parser.add_argument("--from", dest="start", type=int, default=1, metavar="N",
                        help="start at step N (after fixing a step that failed)")
    parser.add_argument("--quiet", action="store_true", help="only the steps and the summary")
    parser.add_argument("--all", dest="show_all", action="store_true",
                        help="with compare: list every difference, not only the first three of each file")
    parser.add_argument("--dataset", metavar="NAME",
                        help="run on a dataset of your own (python src/strainscope/datasets.py list); "
                             "its plan is chosen for you. With compare: its results against the library's")
    args = parser.parse_args(argv)
    if args.list:
        print_plans()
        return 0
    leftover = os.environ.get(paths.ENV, "").strip()
    if leftover and not args.dataset:
        # Forgotten in a terminal (PowerShell keeps it until the window closes), it would send a
        # library plan into the dataset's folder, and the generator would write over its tables.
        again = "compare --dataset" if args.plan == "compare" else "--dataset"
        print(f"  {paths.ENV} is set (to {leftover}), so this would run in that dataset's folder, not the "
              "library's. Nothing was run. Choose one:")
        print(f"    the dataset: python src/strainscope/pipeline.py {again} {leftover}")
        print(f"    the library: remove the setting first (macOS and Linux: unset {paths.ENV}; "
              f"Windows PowerShell: Remove-Item Env:{paths.ENV}), then run the command again")
        return 1
    if args.plan in ("simulate", "workflow") and not args.dataset:
        parser.error(f"'{args.plan}' runs on a dataset: python src/strainscope/pipeline.py --dataset NAME "
                     "(see them all: python src/strainscope/datasets.py list)")
    if args.plan == "compare":
        if not git_ready():
            print("  compare needs Git and the project's Git history: it reads the committed results "
                  "from the last commit. A folder downloaded as a zip file has no history; clone it instead.")
            return 1
        if args.dataset:
            home = paths.locate(args.dataset)
            if home is None or not (home / paths.INFO_FILE).exists():
                print(f"  There's no dataset called {args.dataset}. See them all: python src/strainscope/datasets.py list")
                return 1
            return print_compare(compare(dataset=args.dataset), args.show_all, args.dataset)
        return print_compare(compare(), args.show_all)
    if args.dataset:
        home = paths.locate(args.dataset)
        if home is None or not (home / paths.INFO_FILE).exists():
            print(f"  There's no dataset called {args.dataset}. See them all: python src/strainscope/datasets.py list")
            return 1
        plan = sv.plan_for(args.dataset)
        if args.plan not in ("everything", plan):
            parser.error(f"a dataset runs its own plan ({plan}); leave the plan out")
        total = len(sv.PIPELINES[plan]["steps"])
        if not 1 <= args.start <= total:
            parser.error(f"--from must be a step of '{plan}': 1 to {total}")
        return run(plan, args.start, args.quiet, args.dataset)
    total = len(sv.PIPELINES[args.plan]["steps"])
    if not 1 <= args.start <= total:
        parser.error(f"--from must be a step of '{args.plan}': 1 to {total}")
    return run(args.plan, args.start, args.quiet)


if __name__ == "__main__":
    sys.exit(main())
