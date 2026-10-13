"""
tools/check_accessibility.py: a keyboard and screen-reader check of the app (Phase 8).
======================================================================================

WHAT IT CHECKS
--------------
It starts the app, opens every page in a real browser (Chromium, driven by
Playwright), also opens the three Ask pages with a question answered, and on
each one checks three things:

  1. Automatic rules. axe-core, the open-source rule engine behind many
     accessibility checkers, tests the page against WCAG 2.1 levels A and AA
     (the international guidelines for accessible web pages) and its own best
     practices: contrast, names on buttons and fields, heading order, ...
  2. The keyboard. It presses Tab again and again, the way someone who can't
     use a mouse moves through a page, and records where the focus goes. Every
     control on the page must be reached, the focus must be visible (the
     picture of the control changes when it has the focus), and the focus must
     come out at the end (no "keyboard trap").
  3. What a screen reader reads. A screen reader (VoiceOver on a Mac, NVDA on
     Windows, Orca on Linux) reads a page from its accessibility tree, the
     browser's list of headings, paragraphs, buttons and fields with their
     names. The check reads the same tree and looks for one title per page,
     headings that don't skip a level, and buttons, links and fields with a name.

Some findings come from Streamlit's own parts of the page (the page list in
the sidebar, the page frame), which this project can't change. They're listed
separately, and only the app's own findings make the check fail.

WHAT IT NEEDS
-------------
A browser, which nothing else in StrainScope needs, so the packages aren't in
requirements.txt. Once per machine, with the toolbox switched on:

    python -m pip install playwright axe-playwright-python
    python -m playwright install chromium

(On Ubuntu or Debian, `python -m playwright install --with-deps chromium`
also installs the system libraries Chromium needs. Playwright can't do that
for other Linux systems such as RHEL 8, where Chromium may need a few more
packages; the automatic tests run this check on Ubuntu at every push. If your
Chromium lives somewhere unusual, point STRAINSCOPE_CHROMIUM at it.) Then,
with the database built, from the project folder:

    python tools/check_accessibility.py

It starts the app on port 8599, does the checks (a minute or two), stops the
app, prints a table and writes the details to
data/processed/accessibility_report.json. Exit code 0 when the app's own parts
pass, 1 when they don't. docs/09-packaging.md explains the results; a real
screen reader is still worth trying by hand (its section on accessibility).

The results depend on the Streamlit version, because Streamlit draws the
widgets. The reference is the online copy's version (app/requirements.txt),
which the automatic tests use (.github/workflows/ci.yml). With an older
Streamlit such as 1.57, five page views fail: dropdowns and tabs show no
visible focus, the Tab key skips a dropdown's "Clear all" button, and one
empty dropdown's placeholder is too faint.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "data" / "processed" / "accessibility_report.json"
PORT = 8599
BASE = f"http://localhost:{PORT}"
RULE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"]
MAX_TABS = 400           # Tab presses per page before giving up (a trap would never end)
STUCK = 60               # the same element focused this many times in a row counts as a trap

# (label, address, question to ask or None)
PAGES = [("Home", "", None), ("About this copy", "about", None), ("Ask StrainScope", "ask", None),
         ("Ask the data", "ask_data", None), ("Ask the graph", "ask_graph", None), ("Ranking", "ranking", None),
         ("Strain page", "strain?strain=STRAIN_0485", None), ("Knowledge graph", "knowledge_graph", None),
         ("Integration", "integration", None), ("Workflow", "workflow", None), ("Data", "data", None),
         ("SQL console", "sql_console", None),
         ("Ask StrainScope, answered", "ask", "What is a balanced error rate?"),
         ("Ask the data, answered", "ask_data", "Which strains are borderline?"),
         ("Ask the graph, answered", "ask_graph", "How does iturin suppress disease?")]

# Parts of the page that Streamlit draws by itself. A finding inside them is Streamlit's.
STREAMLIT_PARTS = ('[data-testid="stSidebarNav"]', '[data-testid="stSidebarHeader"]', '[data-testid="stHeader"]',
                   '[data-testid="stToolbar"]', '[data-testid="stDecoration"]', '[data-testid="stLogoLink"]',
                   '[data-testid*="ElementToolbar"]', '.stElementToolbar')
# "region" asks for all content to sit inside landmarks (such as <main>). Streamlit's
# page frame doesn't mark its main area that way, so this one is Streamlit's on every page.
STREAMLIT_RULES = {"region"}
EXPLAIN = {
    "aria-allowed-attr": "the sidebar element carries an attribute its role doesn't allow",
    "list": "the page list in the sidebar puts group titles inside a list",
    "listitem": "the same page list: its items sit in a list that also holds titles",
    "region": "content outside landmarks: Streamlit's main area isn't marked as the page's main part",
}

# Every element a keyboard user should be able to reach, as the browser sees it.
# Streamlit takes some parts of its widgets out of the Tab order on purpose
# (tabindex="-1"): the other tabs of a tab row (reached with the arrow keys), the
# "remove" cross on a chosen item (Backspace), a dropdown's arrow (the field
# itself opens it). Those aren't expected in the Tab order.
CONTROLS = ('button, a[href], input:not([type="hidden"]):not([type="file"]), textarea, select, summary, '
            '[role="button"], [role="tab"], [role="slider"], [role="switch"], [role="checkbox"], [role="radio"], '
            '[tabindex]')
# Toolbars Streamlit shows only when the mouse is near (tables, code blocks):
# their buttons still take the focus. Streamlit's, so listed apart.
HOVER_TOOLBARS = '[data-testid*="ElementToolbar"], .stElementToolbar'



def start_app() -> subprocess.Popen:
    """Start the app in the background and wait until it answers."""
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(ROOT / "app" / "streamlit_app.py"),
                             "--server.headless", "true", "--server.port", str(PORT)],
                            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            urllib.request.urlopen(f"{BASE}/_stcore/health", timeout=1)
            return proc
        except OSError:
            time.sleep(0.5)
    proc.terminate()
    sys.exit("The app didn't start within 30 seconds. Try: python -m streamlit run app/streamlit_app.py")


def settle(page, seconds: float = 4.0) -> None:
    page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=30000)
    page.wait_for_timeout(int(seconds * 1000))


# -----------------------------------------------------------------------------
# 1. axe-core
# -----------------------------------------------------------------------------

def run_axe(page, axe) -> tuple[list[dict], list[dict]]:
    """axe's findings, split into the app's own and Streamlit's."""
    result = axe.run(page, options={"runOnly": {"type": "tag", "values": RULE_TAGS}})
    ours, theirs = [], []
    for v in result.response["violations"]:
        targets = [n["target"][0] for n in v["nodes"]]
        inside = page.evaluate(
            """([targets, parts]) => targets.map(t => {
                 const e = document.querySelector(t);
                 return !!e && (e.matches('[data-testid="stSidebar"]') || parts.some(p => e.closest(p)));
               })""", [targets, list(STREAMLIT_PARTS)])
        mine = [t for t, s in zip(targets, inside) if not s]
        entry = {"rule": v["id"], "impact": v["impact"], "help": v["help"]}
        if v["id"] in STREAMLIT_RULES or not mine:
            theirs.append({**entry, "elements": len(targets)})
        else:
            ours.append({**entry, "elements": len(mine), "where": mine[:5]})
    return ours, theirs


# -----------------------------------------------------------------------------
# 2. The keyboard
# -----------------------------------------------------------------------------

def walk_with_tab(page) -> dict:
    """Press Tab until the focus leaves the page; check reach, visibility and traps."""
    wanted = page.evaluate(
        """([controls, hover]) => {
             const all = [...document.querySelectorAll('[data-testid="stMain"] ' + controls.split(', ').join(
                 ', [data-testid="stMain"] '))].filter(e => e.getAttribute('tabindex') !== '-1'
                 && e.checkVisibility({opacityProperty: true, visibilityProperty: true})
                 && e.getBoundingClientRect().width > 0 && !e.disabled);
             all.forEach((e, i) => e.setAttribute('data-a11y', 'c' + i));
             return all.map(e => ({id: e.getAttribute('data-a11y'), hover: !!e.closest(hover),
                                   name: (e.getAttribute('aria-label') || e.innerText || e.value || e.tagName)
                                         .trim().split('\\n').pop().slice(0, 50)}));
           }""", [CONTROLS, HOVER_TOOLBARS])
    reached, stops, unseen_focus, hover_toolbar, last, same, trapped = set(), 0, [], [], None, 0, False
    # Start at the top: the first thing on the page is the logo's link. (After a
    # question was typed, the browser would otherwise carry on from the box.)
    page.evaluate("""() => { const first = document.querySelector('[data-testid="stLogoLink"]');
                             if (first) first.focus(); else if (document.activeElement) document.activeElement.blur(); }""")
    for _ in range(MAX_TABS):
        page.keyboard.press("Tab")
        info = page.evaluate(
            """() => { const e = document.activeElement;
                 if (!e || e === document.body) return null;
                 const r = e.getBoundingClientRect();
                 const tagged = e.closest('[data-a11y]');
                 return {id: tagged ? tagged.getAttribute('data-a11y') : null, tag: e.tagName,
                         grid: e.tagName === 'CANVAS', hover: !!e.closest('""" + HOVER_TOOLBARS + """'),
                         x: r.x, y: r.y, w: r.width, h: r.height,
                         name: (e.getAttribute('aria-label') || e.innerText || e.tagName).trim().slice(0, 40)}; }""")
        if info is None:
            break
        stops += 1
        key = (info["id"], info["tag"], round(info["x"]), round(info["y"]))
        same = same + 1 if key == last else 0
        last = key
        if same >= STUCK:
            trapped = True
            break
        if info["hover"]:
            hover_toolbar.append(info["name"])
        elif info["id"] and info["id"] not in reached:
            reached.add(info["id"])
            if not info["grid"] and not focus_shows(page, info):
                unseen_focus.append(info["name"])
    missing = [w["name"] for w in wanted if w["id"] not in reached and not w["hover"]]
    return {"stops": stops, "controls": len([w for w in wanted if not w["hover"]]), "not_reached": missing,
            "focus_not_visible": unseen_focus, "trapped": trapped, "streamlit_hover_toolbars": hover_toolbar}


def focus_shows(page, box: dict) -> bool:
    """Does the control look different with the focus than without? Two small
    pictures of it, focused and not, compared pixel by pixel."""
    view = page.viewport_size
    x, y = max(0, box["x"] - 4), max(0, box["y"] - 4)
    w, h = min(box["w"] + 8, view["width"] - x), min(box["h"] + 8, view["height"] - y)
    if w < 2 or h < 2:
        return True                      # off screen: nothing to compare
    clip = {"x": x, "y": y, "width": w, "height": h}
    focused = page.screenshot(clip=clip)
    handle = page.evaluate_handle("document.activeElement")
    page.evaluate("e => e.blur()", handle)
    plain = page.screenshot(clip=clip)
    page.evaluate("e => e.focus({preventScroll: true})", handle)
    return focused != plain


# -----------------------------------------------------------------------------
# 3. What a screen reader reads
# -----------------------------------------------------------------------------

NAMED = re.compile(r"^\s*- '?(button|link|textbox|combobox|slider|checkbox|switch|radio|tab|spinbutton)\b(?! \")")


def read_like_a_screen_reader(page) -> dict:
    """Headings in order, one title, and a name on every control, from the accessibility tree."""
    tree = page.locator("[data-testid='stMain']").aria_snapshot()
    headings = [int(m.group(2)) for m in re.finditer(r"- '?heading \"(.*?)\" \[level=(\d)\]", tree)]
    skipped = [f"h{a} then h{b}" for a, b in zip(headings, headings[1:]) if b > a + 1]
    unnamed = [line.strip() for line in tree.splitlines() if NAMED.match(line)]
    return {"titles": headings.count(1), "headings": headings, "skipped": skipped,
            "unnamed": unnamed, "tree": tree}


# -----------------------------------------------------------------------------
# The run
# -----------------------------------------------------------------------------

def check_page(page, axe, label: str, address: str, question: str | None) -> dict:
    page.goto(f"{BASE}/{address}")
    settle(page)
    if question:
        box = page.get_by_role("textbox", name="Your question")
        box.fill(question)
        box.press("Enter")
        settle(page, 5)
    ours, theirs = run_axe(page, axe)
    reader = read_like_a_screen_reader(page)
    keys = walk_with_tab(page)
    ok = (not ours and not keys["not_reached"] and not keys["focus_not_visible"] and not keys["trapped"]
          and reader["titles"] == 1 and not reader["skipped"] and not reader["unnamed"])
    return {"page": label, "address": f"/{address}", "question": question, "ok": ok, "axe_app": ours,
            "axe_streamlit": theirs, "keyboard": keys, "screen_reader": reader}


def print_report(rows: list[dict], axe_version: str) -> None:
    print(f"  ── StrainScope: keyboard and screen-reader check ({len(rows)} page views) ──")
    print(f"  axe-core {axe_version} in Chromium; rules: WCAG 2.1 A and AA, and axe's best practices\n")
    print(f"  {'page':<28} {'axe':>4} {'Tab stops':>10} {'reached':>9} {'focus seen':>11} {'headings':<14} {'unnamed':>7}")
    for r in rows:
        k, s = r["keyboard"], r["screen_reader"]
        reached = f"{k['controls'] - len(k['not_reached'])}/{k['controls']}"
        seen = f"{len(k['focus_not_visible'])} hidden" if k["focus_not_visible"] else "all"
        heads = " ".join(f"h{h}" for h in sorted(set(s["headings"])))
        mark = "✓" if r["ok"] else "✗"
        print(f"  {mark} {r['page']:<26} {len(r['axe_app']):>4} {k['stops']:>10} {reached:>9} {seen:>11} "
              f"{heads:<14} {len(s['unnamed']):>7}")
    problems = [r for r in rows if not r["ok"]]
    for r in problems:
        print(f"\n  ✗ {r['page']}:")
        for v in r["axe_app"]:
            print(f"      axe {v['rule']} ({v['impact']}): {v['help']}; {v['elements']} element(s)")
        k, s = r["keyboard"], r["screen_reader"]
        for what, items in (("not reached with Tab", k["not_reached"]), ("focus not visible", k["focus_not_visible"]),
                            ("headings skip a level", s["skipped"]), ("no name", s["unnamed"])):
            if items:
                print(f"      {what}: {', '.join(map(str, items[:6]))}")
        if k["trapped"]:
            print("      the focus got stuck (a keyboard trap)")
        if s["titles"] != 1:
            print(f"      {s['titles']} page titles (h1), one expected")
    theirs: dict[str, int] = {}
    for r in rows:
        for v in r["axe_streamlit"]:
            theirs[v["rule"]] = theirs.get(v["rule"], 0) + 1
    hover = [r for r in rows if r["keyboard"]["streamlit_hover_toolbars"]]
    if theirs or hover:
        print("\n  Streamlit's own parts of the page (not something this project can change):")
        for rule, n in sorted(theirs.items()):
            print(f"    · {rule:<18} on {n} of {len(rows)} page views: {EXPLAIN.get(rule, 'see the report')}")
        if hover:
            print(f"    · {'hover toolbars':<18} on {len(hover)} of {len(rows)} page views: the toolbar of a table or "
                  "code block appears only when the mouse is near, yet its buttons take the Tab focus")
    print("\n  Charts are pictures to a screen reader. Each chart's numbers are also on its page, as text or in "
          "a table\n  underneath; the picture of the whole knowledge graph is explored in words on its other tabs.")
    where = REPORT.relative_to(ROOT).as_posix()
    print(f"  Details, including each page's accessibility tree: {where}")
    print("\n  " + (f"{len(problems)} page view(s) need a fix." if problems else
                    "The app's own parts pass on every page."))


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if (stream.encoding or "").lower() not in ("utf-8", "utf8"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    try:
        from axe_playwright_python.sync_playwright import Axe
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  This check needs a browser. Once per machine:\n"
              "    python -m pip install playwright axe-playwright-python\n"
              "    python -m playwright install chromium")
        return 1
    sys.path.insert(0, str(ROOT / "src"))
    from strainscope import service as sv
    if not sv.DB_PATH.exists():
        print("  Build the database first: python src/strainscope/pipeline.py database")
        return 1
    axe = Axe()
    version = re.search(r"axe v([\d.]+)", Path(sys.modules[Axe.__module__].__file__).with_name("axe.min.js")
                        .read_text(encoding="utf-8")[:200])
    proc = start_app()
    rows = []
    try:
        with sync_playwright() as p:
            chromium = os.environ.get("STRAINSCOPE_CHROMIUM")
            browser = p.chromium.launch(executable_path=chromium) if chromium else p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            for label, address, question in PAGES:
                rows.append(check_page(page, axe, label, address, question))
            browser.close()
    finally:
        proc.terminate()
        proc.wait(timeout=20)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print_report(rows, version.group(1) if version else "?")
    return 0 if all(r["ok"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
