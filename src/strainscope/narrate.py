"""
src/strainscope/narrate.py (StrainScope Phase 7): results in plain words.
=========================================================================

WHAT IT DOES
------------
It turns numbers the earlier phases computed into a short paragraph that
someone without a statistics background can read:

  * strain()      why one strain ranks where it does (its chance, what that
                  band means, its strongest mechanism paths from the
                  knowledge graph, anything to treat with care, and, for the
                  simulated library, what the trial said);
  * shortlist()   what testing the N best-ranked strains would bring.

The app shows them on the Strain and Ranking pages ("In plain words"), and
the service layer offers them to other programs (service.explain_in_words).
From a terminal:

    python src/strainscope/narrate.py STRAIN_0485      # one strain
    python src/strainscope/narrate.py --top 50         # testing the 50 best-ranked strains

HOW, AND WHY NO LANGUAGE MODEL
------------------------------
Every sentence is a template filled in with numbers and names that are
already in the results: the ranking (artifacts/model/predictions.csv), the
model card and the explanations of Phase 5 (artifacts/graph/explanations.csv,
or the ones made for an upload). Nothing is guessed, so every number in the
text can be found in those files, and a test checks that for all 600
strains. A language model could make the wording smoother, but it would
need to see a strain's measurements to do so, and StrainScope never sends
data to a model (docs/08-deployment-ai.md, section 3). The rules are easy
to read and easy to test; that was the deciding point.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

# Make `strainscope` importable no matter where the script is run from.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strainscope.ontology import MODES_OF_ACTION  # noqa: E402

EFFECTIVE_LINE = 65            # "effective" = disease suppressed by at least this many % in the trial
BANDS = (30, 70)               # the borderline band, in % (the same as service.BORDERLINE)
KINGDOM_WORD = {"Bacteria": "bacterial", "Fungi": "fungal", "Yeast": "yeast", "Oomycete": "oomycete"}


@dataclass
class Story:
    """A short text in paragraphs, and the numbers it was allowed to use."""
    paragraphs: list[str] = field(default_factory=list)
    numbers: set[str] = field(default_factory=set)

    @property
    def text(self) -> str:
        return "\n\n".join(p for p in self.paragraphs if p)


def percent(p: float) -> str:
    """A chance as a reader would say it: '73 %', 'over 99 %', 'under 1 %'.
    A rounded '100 %' would claim a certainty the model doesn't have."""
    if p >= 0.995:
        return "over 99 %"
    if p < 0.005:
        return "under 1 %"
    return f"{p * 100:.0f} %"


def band_of(p: float) -> str:
    low, high = BANDS
    return "likely" if p * 100 > high else "borderline" if p * 100 >= low else "unlikely"


def _reason(text: str, first: bool) -> str:
    """One explanation line of Phase 5 as part of a sentence:
    'carries fenA and produces fengycin (7.6x the usual level): lipopeptide membrane attack'
    becomes 'carries fenA and produces fengycin at 7.6 times the usual level, which works
    by lipopeptide membrane attack' (or '... (lipopeptide membrane attack)' when it isn't the first)."""
    text = re.sub(r"\(([\d.]+)x the usual level\)", r"at \1 times the usual level", text)
    body, _, mode = text.rpartition(": ")
    if not body:
        return text
    return f"{body}, which works by {mode}" if first else f"{body} ({mode})"


def _kingdom(kingdom: str) -> str:
    word = KINGDOM_WORD.get(str(kingdom))
    return f"a {word} strain" if word else "a strain of a kingdom the model hasn't seen"


def strain(row: dict, reasons: pd.DataFrame, total: int, card: dict | None = None,
           uploaded: bool = False) -> Story:
    """One strain's rank and reasons in plain words.

    row      the strain's line of the ranking: strain_id, kingdom, rank,
             probability, and when known genus, is_effective (the library's
             answer key), library_rank (an upload's place among the 600)
    reasons  its rows of artifacts/graph/explanations.csv (or an upload's)
    total    how many strains are ranked (600, or the strains in an upload)
    card     the model card (for the top-50 check), when there is one"""
    story = Story()
    p = float(row["probability"])
    rank, sid = int(row["rank"]), row["strain_id"]
    genus = row.get("genus")
    genus = f" ({genus})" if isinstance(genus, str) and genus and genus != "unknown" else ""
    band = band_of(p)
    where = f"of the {total} strains in your file" if uploaded else f"of {total}"
    first = [f"{sid} is {_kingdom(row.get('kingdom'))}{genus} at rank {rank} {where}.",
             f"The model puts its chance of being effective at {percent(p)} (effective means suppressing disease "
             f"by at least {EFFECTIVE_LINE} % in a trial)."]
    if band == "likely":
        first.append(f"That counts as likely (above {BANDS[1]} %).")
    elif band == "unlikely":
        first.append(f"That counts as unlikely (below {BANDS[0]} %).")
    else:
        first.append(f"That counts as borderline (from {BANDS[0]} % to {BANDS[1]} %): strains just either side of "
                     f"the {EFFECTIVE_LINE} % line are much alike, so read it as a maybe.")
    check = (card or {}).get("top_n_check")
    if not uploaded and check and rank <= int(check["n"]):
        first.append(f"It's in the top {check['n']}, and {check['truly_effective']} of those {check['n']} strains "
                     "were effective in the simulated trial.")
    if uploaded and pd.notna(row.get("library_rank")):
        lr = int(row["library_rank"])
        first.append(f"Among the library's 600 strains it would rank {lr}." if lr <= 600
                     else "It would rank below all 600 strains of the library.")
    story.paragraphs.append(" ".join(first))

    columns = ["kind", "text", "feature", "mode", "mechanism_paths"]
    rows = reasons if reasons is not None and len(reasons) else pd.DataFrame(columns=columns)
    mech = rows[rows["kind"] == "mechanism"]
    data_only = rows[rows["kind"] == "data only"]
    missing = rows[rows["kind"] == "missing"]
    paths = int(rows["mechanism_paths"].iloc[0]) if len(rows) else 0
    second = []
    if len(mech):
        top = mech.iloc[0]
        lead = "Its strongest reason" if band == "likely" else "Its strongest route to disease suppression"
        line = f"{lead}: it {_reason(top['text'], first=True)}"
        mode = top.get("mode")
        if isinstance(mode, str) and mode in MODES_OF_ACTION:
            line += f" ({MODES_OF_ACTION[mode][0]})"
        second.append(line + ".")
        others = [_reason(t, first=False) for t in mech["text"].iloc[1:]]
        if others:
            second.append("It also " + "; and ".join(others) + ".")
        if paths > len(mech):
            second.append(f"In all, the knowledge graph finds {paths} routes like these from it to disease suppression.")
        elif paths == 1:
            second.append("That's its only route to disease suppression in the knowledge graph.")
        if band == "unlikely":
            second.append("A route isn't enough on its own: the model weighs all of a strain's genes and compounds "
                          "together.")
    else:
        second.append("The knowledge graph finds no route from it to disease suppression: none of the weapons it "
                      "carries or makes is linked to one.")
    for f in data_only["feature"]:
        second.append(f"The model also leans a little on {f}, but no known mechanism links it to disease "
                      "suppression, so read that as a statistical hint rather than a reason.")
    for i, t in enumerate(missing["text"]):
        m = re.match(r"lacks (.+), which (\d+)% of (.+) carry$", t)
        if not m:
            second.append("It " + t + ".")
        elif i == 0:
            second.append(f"It lacks {m[1]}, which {m[2]} % of {m[3]} carry.")
        else:
            second.append(f"Nor does it carry {m[1]} ({m[2]} % of {m[3]} do).")
    story.paragraphs.append(" ".join(second))

    truth = row.get("is_effective")
    if not uploaded and truth is not None and pd.notna(truth):
        worked = int(truth) == 1
        said = "it was effective" if worked else "it wasn't effective"
        if band == "borderline":
            verdict = "; for a borderline strain either result was plausible."
        elif (band == "likely") == worked:
            verdict = ", as the model expected."
        elif worked:
            verdict = ", so this is one the model missed."
        else:
            verdict = ", so the model was wrong about this one."
        story.paragraphs.append(f"In the simulated trial {said}{verdict} (The trial result is known only because "
                                "the data is simulated.)")

    story.numbers = _allowed(row, rows, total, card, p)
    return story


def shortlist(pred: pd.DataFrame, n: int, uploaded: bool = False) -> Story:
    """What testing the n best-ranked strains would bring, in plain words.
    The model's chances are calibrated (Phase 4), so adding them up gives
    the number of effective strains it expects among the n."""
    story = Story()
    n = max(1, min(int(n), len(pred)))
    top = pred.nsmallest(n, "rank")
    expected = float(top["probability"].sum())
    bands = top["probability"].map(band_of).value_counts()
    a, b, c = (int(bands.get(k, 0)) for k in ("likely", "borderline", "unlikely"))
    whose = "your" if uploaded else "the"
    lines = [f"If you test {whose} {n} best-ranked strains, the model's chances for them add up to {expected:.1f}: "
             "that's how many it expects to be effective.",
             f"It rates {a} of them likely, {b} borderline and {c} unlikely."]
    if not uploaded and "is_effective" in pred:
        found, total = int(top["is_effective"].sum()), int(pred["is_effective"].sum())
        base = pred["is_effective"].mean()
        lines.append(f"In the simulated trial, {found} of the {n} were effective ({found / n * 100:.0f} %).")
        lines.append(f"Picking {n} at random would find about {n * base:.0f}, because {base * 100:.0f} % of the "
                     f"library is effective, and {total - found} of the {total} effective strains would be left untested.")
    story.paragraphs.append(" ".join(lines))
    story.numbers = numbers_of(*story.paragraphs)
    return story


def numbers_of(*texts: str) -> set[str]:
    from strainscope.llm import numbers
    out: set[str] = set()
    for t in texts:
        out |= numbers(str(t))
    return out


def _allowed(row: dict, reasons: pd.DataFrame, total: int, card: dict | None, p: float) -> set[str]:
    """Every number strain() may write, taken from its inputs (the test
    checks the text against this set)."""
    allowed = numbers_of(str(row.get("strain_id")), str(row.get("rank")), str(total), percent(p),
                         str(EFFECTIVE_LINE), *map(str, BANDS), "600", "99", "1")
    if pd.notna(row.get("library_rank", float("nan"))):
        allowed |= numbers_of(str(int(row["library_rank"])))
    check = (card or {}).get("top_n_check") or {}
    allowed |= numbers_of(str(check.get("n", "")), str(check.get("truly_effective", "")))
    if len(reasons):
        allowed |= numbers_of(*reasons["text"].astype(str), str(int(reasons["mechanism_paths"].iloc[0])))
    return allowed


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="StrainScope results in plain words.")
    parser.add_argument("strain", nargs="?", help="a library strain id, e.g. STRAIN_0485")
    parser.add_argument("--top", type=int, help="say what testing the N best-ranked strains would bring")
    args = parser.parse_args(argv)
    from strainscope import service as sv
    paragraphs = []
    if args.top:
        pred = sv.read_artifact("model/predictions.csv")
        if pred is None:
            sys.exit("The ranking is missing. Run: python src/strainscope/model.py all")
        paragraphs = shortlist(pred, args.top).paragraphs
    elif args.strain:
        try:
            paragraphs = sv.explain_in_words(args.strain.upper())["paragraphs"]
        except KeyError as err:
            sys.exit(f"  {err.args[0]} (strain ids look like STRAIN_0485)")
        except FileNotFoundError as err:
            sys.exit(f"  {err}")
    else:
        parser.print_help()
        return 0
    import textwrap
    print()
    for para in paragraphs:
        print(textwrap.fill(para, width=88, initial_indent="  ", subsequent_indent="  "))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
