"""
src/strainscope/paths.py (StrainScope Phase 9): where every script reads and writes.
====================================================================================

WHAT THIS FILE IS
-----------------
One small place that says where the data and the results live, so every
script of Phases 1 to 5, the service layer behind the app and the tests agree
on it. There are two kinds of place:

  * THE BUILT-IN LIBRARY, the simulated 600 strains this repository is built
    around. Its files are where they have always been:
        data/raw/                        the three raw tables (Phase 1)
        data/processed/                  the clean tables and strainscope.duckdb (Phase 2)
        artifacts/integration/, model/, graph/   the committed results (Phases 3 to 5)

  * A DATASET (Phase 9): your own strains, or a fresh simulated library with a
    seed and size of your choice. Each one gets a folder of its own, laid out
    the same way, so the scripts don't care which one they're working on:
        data/processed/datasets/<name>/dataset.json      what it is (datasets.py writes it)
        data/processed/datasets/<name>/raw/              its three raw tables
        data/processed/datasets/<name>/processed/        its clean tables and database
        data/processed/datasets/<name>/artifacts/        its results (integration/, model/, graph/)
        data/processed/datasets/<name>/figures/          DIABLO's pictures, when R is installed

Think of a kitchen with one recipe book and several labelled boxes of
ingredients. The recipes (the scripts) never change; you point them at a box,
and what they cook goes back into the same box. The committed library is one
box that is never touched by a dataset run.

HOW A SCRIPT IS POINTED AT A DATASET
------------------------------------
With the environment variable STRAINSCOPE_DATASET: a dataset's name (a folder
in data/processed/datasets/) or the full path of its folder. Unset or empty
means the built-in library, so everything from Phases 1 to 8 works as before.
You rarely set it yourself: `python src/strainscope/pipeline.py --dataset NAME`
and the app's Workflow page set it for the scripts they start.

Everything under data/ stays on your computer: Git ignores it (.gitignore) and
so does the container build (.dockerignore).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATASETS = ROOT / "data" / "processed" / "datasets"
REAL = ROOT / "data" / "processed" / "real"         # the public reference tables (Phase 1b), shared by every dataset
ENV = "STRAINSCOPE_DATASET"
INFO_FILE = "dataset.json"


@dataclass(frozen=True)
class Folders:
    """Every folder and file a pipeline run reads or writes, for one place."""
    home: Path | None          # the dataset's folder; None for the built-in library
    raw: Path                  # the three raw tables
    processed: Path            # the clean tables and the database
    db: Path                   # the database file
    blocks: Path               # the integration blocks (Phase 3's prepare)
    artifacts: Path            # the results: integration/, model/, graph/
    figures: Path              # pictures a run draws (DIABLO's, from R)

    @property
    def integration(self) -> Path:
        return self.artifacts / "integration"

    @property
    def model(self) -> Path:
        return self.artifacts / "model"

    @property
    def graph(self) -> Path:
        return self.artifacts / "graph"

    @property
    def builtin(self) -> bool:
        return self.home is None


def locate(dataset: str | Path | None = None) -> Path | None:
    """The folder of a dataset, or None for the built-in library.

    `dataset` may be a name ("trial_2026", a folder in data/processed/datasets/)
    or a path. Without one, the STRAINSCOPE_DATASET environment variable
    decides; unset or empty means the library."""
    value = str(dataset) if dataset is not None else os.environ.get(ENV, "")
    value = value.strip()
    if not value:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute() and len(path.parts) == 1:
        path = DATASETS / value                      # a plain name
    return path.resolve()


def folders(dataset: str | Path | None = None) -> Folders:
    """Every path for one place: the library (no argument and no environment
    variable) or a dataset."""
    home = locate(dataset)
    if home is None:
        processed = ROOT / "data" / "processed"
        return Folders(home=None, raw=ROOT / "data" / "raw", processed=processed,
                       db=processed / "strainscope.duckdb", blocks=processed / "integration",
                       artifacts=ROOT / "artifacts", figures=ROOT / "figures")
    processed = home / "processed"
    return Folders(home=home, raw=home / "raw", processed=processed, db=processed / "strainscope.duckdb",
                   blocks=processed / "integration", artifacts=home / "artifacts", figures=home / "figures")


LIBRARY_INFO = {
    "name": "library", "label": "the simulated library", "kind": "library", "answer_key": True,
    "source": "src/strainscope/generate_data.py, seed 42, 600 strains (committed results)",
    "seed": 42, "strains": 600, "effective_at": 65.0, "repeats": 10,
}


def info(dataset: str | Path | None = None) -> dict:
    """What a place is: its name, a label for sentences, its kind ('library',
    'simulated' or 'yours'), whether the simulation's answer key applies, and
    its settings. Read from the dataset's dataset.json (datasets.py writes it)."""
    home = locate(dataset)
    if home is None:
        return dict(LIBRARY_INFO)
    path = home / INFO_FILE
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    data.setdefault("name", home.name)
    data.setdefault("kind", "yours")
    data.setdefault("answer_key", data["kind"] == "simulated")
    data.setdefault("label", f"dataset {data['name']}")
    data.setdefault("effective_at", 65.0)
    data.setdefault("repeats", 10)
    return data


def setting(key: str, default, dataset: str | Path | None = None):
    """One setting of the current place (for example the number of
    cross-validation repeats), with a default when it isn't recorded."""
    value = info(dataset).get(key)
    return default if value is None else value


def rel(path: Path) -> str:
    """A path as you'd type it from the project folder when it's inside it
    (artifacts/model), else in full. Used in printed messages."""
    path = Path(path)
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def child_environment(dataset: str | Path | None = None, **extra: str) -> dict:
    """The environment for a script started from Python: everything this
    program has, plus STRAINSCOPE_DATASET set to the dataset's full path (or
    emptied for the library), so the script and anything it starts (the R
    step) work on the same place. Windows needs UTF-8 printing switched on."""
    home = locate(dataset)
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", ENV: str(home) if home else ""}
    env.update({k: str(v) for k, v in extra.items()})
    return env


# The place the current program works on, chosen once when it starts.
HERE = folders()
