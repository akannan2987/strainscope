"""
figures/make_phase8_figures.py: the teaching figures for Phase 8 (packaging and release 1.0).
=============================================================================================
  Drawn from the project's own files, so they stay true when those change:
    figures/one_command.png         the one-command pipeline: the plans and their steps
                                    (from PIPELINES in src/strainscope/service.py), and compare
    figures/ci_matrix.png           every job the automatic tests run at each push
                                    (read from .github/workflows/ci.yml)
    figures/release_path.png        from a commit on develop to the v1.0.0 release: tests first,
                                    the tag only on a commit whose tests all passed
    figures/container_box.png       what a container is: the Dockerfile's recipe, the image, and
                                    the same box running on Windows, macOS and RHEL 8
    figures/accessibility_check.png the three ways each page of the app is checked, and what
                                    Phase 8 changed because of them
    figures/footprint.png           everything StrainScope puts on a computer and online, and how
                                    each piece is removed (docs/UNINSTALL.md)
    docs/interactive/release_explorer.html
                                    the pipeline's plans, the automatic tests' jobs and the product
                                    checklist of docs/ROADMAP.md, to click through

Run (from the project root, venv active):
    python figures/make_phase8_figures.py

The drawing helpers are shared with figures/make_phase6_figures.py.
"""
import json
import re
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "figures"))

from make_phase6_figures import (BLUE, DARK_GREEN, GOLD, GREY, INK, PURPLE, RED, SOFT, TEAL,  # noqa: E402
                                 arrow, box, canvas, save, tint)
from strainscope import service as sv  # noqa: E402

INT = ROOT / "docs" / "interactive"
CI = ROOT / ".github" / "workflows" / "ci.yml"


# =============================================================================
# Reading the project's own files
# =============================================================================

def ci_jobs() -> list[dict]:
    """The jobs of .github/workflows/ci.yml: id, display name, where it runs and its step names.
    A small reader for this one file (no YAML package needed)."""
    text = CI.read_text(encoding="utf-8")
    body = text[text.index("\njobs:"):]
    jobs = []
    for m in re.finditer(r"^  ([a-z0-9-]+):\n(.*?)(?=^  [a-z0-9-]+:\n|\Z)", body, flags=re.M | re.S):
        block = m.group(2)
        name = re.search(r"^    name: (.+)$", block, flags=re.M).group(1).strip()
        image = re.search(r"^      image: (.+)$", block, flags=re.M)
        runner = re.search(r"^    runs-on: (.+)$", block, flags=re.M).group(1).strip()
        steps = re.findall(r"^      - name: (.+)$", block, flags=re.M)
        systems = re.search(r"system: \[(.*?)\]", block)
        pythons = re.search(r"python: \[(.*?)\]", block)
        if pythons:                                       # "Install Python ${{ matrix.python }}", readable
            steps = [s.replace("${{ matrix.python }}", " or ".join(p.strip(' "') for p in pythons.group(1).split(",")))
                     for s in steps]
        if systems:                                       # the matrix job's name and machines, spelled out
            names = [s.strip() for s in systems.group(1).split(",")]
            name = f"{', '.join(names[:-1])} and {names[-1]}, each with Python " + " and ".join(
                q.strip(' "') for q in pythons.group(1).split(","))
            runner = ", ".join(re.findall(r"runner: (\S+)", block))
        jobs.append({"id": m.group(1), "name": name, "runs_on": runner,
                     "container": image.group(1).strip() if image else "",
                     "steps": steps, "systems": [s.strip() for s in systems.group(1).split(",")] if systems else [],
                     "pythons": [p.strip(' "') for p in pythons.group(1).split(",")] if pythons else []})
    return jobs


def checklist() -> list[dict]:
    """The product checklist ("What finished means") of docs/ROADMAP.md."""
    text = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
    part = text[text.index("| A user can... |"):]
    rows = []
    for line in part.splitlines()[2:]:
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip("|").split("|")]
        plain = lambda s: re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)      # noqa: E731
        rows.append({"can": plain(cells[0]), "built_in": plain(cells[1]), "status": plain(cells[2])})
    return rows


def matrix_count(jobs: list[dict]) -> int:
    return sum(max(1, len(j["systems"]) * len(j["pythons"])) for j in jobs)


# =============================================================================
# 1. One command
# =============================================================================

WRITES = {"generate_data.py": "the simulated library\ndata/raw/",
          "harmonize.py": "the clean tables and\nthe database",
          "integrate.py": "Phase 3: the signature\nartifacts/integration/",
          "model.py": "Phase 4: the ranking\nartifacts/model/",
          "graph.py": "Phase 5: the graph\nartifacts/graph/"}


def draw_one_command():
    fig, ax = canvas(12, 6.2, "One command, five steps",
                     "python src/strainscope/pipeline.py runs the scripts of Phases 1 to 5 in order. The app's "
                     "buttons run the same lists.")
    plans = [("everything", "recomputes every result (5 to 10 minutes; about 4 without R)", DARK_GREEN, 8.0),
             ("database", "loads the committed results (about 15 seconds)", BLUE, 3.55)]
    for name, what, colour, y in plans:
        ax.text(0.3, y + 2.25, f"pipeline.py {name}", fontsize=10.2, fontweight="bold", color=INK,
                family="monospace")
        ax.text(7.4, y + 2.25, what, fontsize=8.6, color=SOFT)
        steps = sv.PIPELINES[name]["steps"]
        for i, step in enumerate(steps):
            x = 0.3 + i * 4.75
            label = step[0] + ("\n" + " ".join(step[1:]) if len(step) > 1 else "")
            box(ax, x, y + 0.75, 4.1, 1.2, colour, label, fs=8.5)
            ax.text(x + 2.05, y + 0.45, WRITES[step[0]], ha="center", va="top", fontsize=7.4, color=SOFT,
                    linespacing=1.25)
            if i < len(steps) - 1:
                arrow(ax, x + 4.15, y + 1.35, x + 4.7, y + 1.35, colour=colour)
    box(ax, 0.3, 0.35, 23.4, 1.6, GOLD, "python src/strainscope/pipeline.py compare:  every rebuilt number against "
        "the committed one, to within 0.001;\nlines that only describe the computer (package versions, run times) "
        "are left out", fs=8.6)
    save(fig, "one_command.png")


# =============================================================================
# 2. The automatic tests
# =============================================================================

def draw_ci_matrix():
    jobs = ci_jobs()
    total = matrix_count(jobs)
    fig, ax = canvas(12, 7.2, f"Every push to master: {total} jobs on fresh computers",
                     "GitHub's machines install StrainScope from scratch and test it. A green tick means "
                     "every job passed (.github/workflows/ci.yml).")
    grid = next(j for j in jobs if j["systems"])
    colours = {"Linux": DARK_GREEN, "Windows": BLUE, "macOS": GREY}
    ax.text(0.3, 12.0, grid["id"] + ":  the same steps on each system", fontsize=9.6, fontweight="bold", color=INK)
    for r, system in enumerate(grid["systems"]):
        for c, python in enumerate(grid["pythons"]):
            x, y = 0.3 + c * 5.6, 9.6 - r * 2.55
            box(ax, x, y, 5.2, 2.15, colours.get(system, TEAL), f"{system}\nPython {python}", fs=9.4, bold=True)
    steps = "\n".join(f"{i}. {s}" for i, s in enumerate(grid["steps"], start=1))
    ax.text(11.6, 11.4, "each one:", fontsize=8.8, color=SOFT, fontweight="bold")
    ax.text(11.6, 10.95, steps, fontsize=8.2, color=INK, va="top", linespacing=1.6)
    others = [j for j in jobs if not j["systems"]]
    palette = [RED, GOLD, PURPLE, TEAL, BLUE]
    for i, j in enumerate(others):
        x = 0.3 + i * 4.75
        where = "/".join(j["container"].split("/")[-2:]) if j["container"] else j["runs_on"]
        box(ax, x, 0.4, 4.4, 2.6, palette[i % len(palette)], "", fill=tint(palette[i % len(palette)], 0.85))
        ax.text(x + 2.2, 2.6, j["id"], ha="center", fontsize=9.2, fontweight="bold", color=INK)
        ax.text(x + 2.2, 2.15, textwrap.fill(j["name"].replace(", Python", ","), 26, break_on_hyphens=False),
                ha="center", va="top", fontsize=7.4, color=INK, linespacing=1.2)
        ax.text(x + 2.2, 0.6, where, ha="center", fontsize=7.0, color=SOFT, family="monospace")
    ax.text(0.3, 3.45, "and once each:", fontsize=9.6, fontweight="bold", color=INK)
    save(fig, "ci_matrix.png")


# =============================================================================
# 3. From develop to a release
# =============================================================================

def draw_release_path():
    total = matrix_count(ci_jobs())
    fig, ax = canvas(12, 5.6, "From a commit on develop to the v1.0.0 release",
                     "The tag goes on a commit only after every automatic test has passed on it.")
    steps = [(0.3, "on your computer:\npytest -q, the gate,\ngit commit", BLUE),
             (5.0, "git push origin\ndevelop develop:beta\ndevelop:master", BLUE),
             (9.7, f"GitHub runs the\n{total} jobs\n(the Actions tab)", PURPLE)]
    for x, text, colour in steps:
        box(ax, x, 6.0, 4.1, 2.4, colour, text, fs=8.4)
    arrow(ax, 4.45, 7.2, 4.95, 7.2, colour=BLUE)
    arrow(ax, 9.15, 7.2, 9.65, 7.2, colour=BLUE)
    box(ax, 14.4, 6.0, 3.0, 2.4, GOLD, "all\ngreen?", fs=9.6, bold=True)
    arrow(ax, 13.85, 7.2, 14.35, 7.2, colour=PURPLE)
    box(ax, 18.6, 6.0, 4.9, 2.4, DARK_GREEN, "git tag -a v1.0.0\ngit push origin develop\n... --tags", fs=8.4)
    arrow(ax, 17.45, 7.2, 18.55, 7.2, colour=DARK_GREEN, text="yes")
    box(ax, 18.6, 2.3, 4.9, 2.6, DARK_GREEN, "a GitHub release\nwith the changelog;\nCite this repository", fs=8.4)
    arrow(ax, 21.05, 5.95, 21.05, 4.95, colour=DARK_GREEN)
    box(ax, 9.7, 2.3, 7.7, 2.6, RED, "no: open the red job, read its log,\nfix it on develop, push again\n"
        "(the tests run again)", fs=8.4, dashed=True)
    arrow(ax, 15.9, 5.95, 14.8, 4.95, colour=RED)
    arrow(ax, 9.65, 3.6, 7.0, 5.95, colour=RED, rad=-0.2)
    ax.text(0.3, 4.4, "every push to master also:", fontsize=8.6, color=SOFT, fontweight="bold")
    ax.text(0.3, 3.85, "updates the online copy\n(strainscope.streamlit.app)\nand the GitHub Pages site", fontsize=8.2,
            color=SOFT, va="top", linespacing=1.4)
    ax.text(0.3, 0.6, "Version numbers: the first number changes when something you rely on stops working the old way, "
            "the second when something new arrives, the third for fixes.", fontsize=8.2, color=SOFT)
    save(fig, "release_path.png")


# =============================================================================
# 4. A container
# =============================================================================

def draw_container_box():
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    base = re.search(r"^FROM (\S+)", docker, flags=re.M).group(1).split("/")[-1]
    fig, ax = canvas(12, 5.8, "A container: the app and everything it needs, in one box",
                     "The Dockerfile is the recipe, the image is the sealed box, a container is the box "
                     "running. Docker and Podman both read it.")
    ax.text(0.3, 9.6, "Dockerfile (the recipe)", fontsize=9.4, fontweight="bold", color=INK)
    recipe = [f"start from {base}", "install app/requirements.txt", "copy the project", "build the database",
              "switch to an ordinary user", "start the app on port 8501"]
    for i, line in enumerate(recipe):
        box(ax, 0.3, 8.2 - i * 1.35, 6.4, 1.05, GREY, f"{i + 1}. {line}", fs=8.2, fill="white")
    arrow(ax, 6.8, 5.6, 7.9, 5.6, colour=INK, text="docker build")
    box(ax, 8.0, 2.6, 5.4, 6.4, PURPLE, "", fill=tint(PURPLE, 0.88))
    ax.text(10.7, 8.3, "the image", ha="center", fontsize=9.6, fontweight="bold", color=INK)
    for i, layer in enumerate(["Linux (Debian, small)", "Python 3.14", "the online copy's packages",
                               "StrainScope and its database"]):
        box(ax, 8.4, 6.9 - i * 1.15, 4.6, 0.9, PURPLE, layer, fs=8.0, fill="white")
    arrow(ax, 13.5, 5.6, 14.6, 5.6, colour=INK, text="docker run")
    for i, system in enumerate(["Windows (Docker Desktop)", "macOS (Docker Desktop)", "RHEL 8 (Podman)"]):
        y = 7.6 - i * 2.2
        box(ax, 14.7, y, 4.6, 1.7, TEAL, f"a running container\non {system}", fs=8.0)
        arrow(ax, 19.35, y + 0.85, 20.3, 5.6 + (1 - i) * 0.4, colour=TEAL)
    box(ax, 20.4, 4.6, 3.3, 2.2, BLUE, "your browser:\nlocalhost:8501", fs=8.4)
    ax.text(0.3, 0.6, "-p 8501:8501 connects the box's port 8501 to the same port on your computer. "
            "Nothing you do inside the box changes your computer.", fontsize=8.3, color=SOFT)
    save(fig, "container_box.png")


# =============================================================================
# 5. The keyboard and screen-reader check
# =============================================================================

def draw_accessibility_check():
    fig, ax = canvas(12, 7.0, "Three ways each page of the app is checked",
                     "python tools/check_accessibility.py: every page, and the three Ask pages with an answer "
                     "showing.")
    columns = [("automatic rules", "axe-core, against WCAG 2.1\nlevels A and AA",
                ["contrast of text against\nits background", "a name on every button,\nlink and field",
                 "headings in order", "pictures with a description"], BLUE),
               ("the keyboard", "Tab, again and again,\nas without a mouse",
                ["every control is reached", "you can see where\nthe focus is", "the focus comes out\nat the end "
                 "(no trap)"], GOLD),
               ("a screen reader's view", "the page as VoiceOver, NVDA\nor Orca read it",
                ["one title per page", "no heading level skipped", "every control has a name"], PURPLE)]
    for i, (title, how, checks, colour) in enumerate(columns):
        x = 0.3 + i * 8.0
        box(ax, x, 3.9, 7.4, 8.0, colour, "", fill=tint(colour, 0.88))
        ax.text(x + 3.7, 11.35, title, ha="center", fontsize=10.2, fontweight="bold", color=INK)
        ax.text(x + 3.7, 10.8, how, ha="center", va="top", fontsize=8.1, color=SOFT, linespacing=1.3)
        for k, check in enumerate(checks):
            box(ax, x + 0.4, 8.45 - k * 1.4, 6.6, 1.15, colour, "✓  " + check, fs=8.0, fill="white")
    ax.text(0.3, 3.2, "What Phase 8 changed because of it:", fontsize=9.2, fontweight="bold", color=INK)
    ax.text(0.3, 2.65, "darker small text (captions, code, notes) · one heading level after the title · the numbers "
            "behind each chart as a table\nthe chart toolbar always shown (its hidden buttons took the focus) · "
            "a description on every picture in an answer", fontsize=8.3, color=INK, va="top", linespacing=1.5)
    ax.text(0.3, 0.55, "Listed apart, as Streamlit's own: the page list in the sidebar, the page frame's landmarks, "
            "and the hover toolbars of tables and code blocks.", fontsize=8.2, color=SOFT)
    save(fig, "accessibility_check.png")


# =============================================================================
# 6. Where StrainScope keeps things
# =============================================================================

def draw_footprint():
    fig, ax = canvas(12, 7.0, "Everything StrainScope puts on a computer, and how it goes",
                     "docs/UNINSTALL.md takes them in this order: outside the folder first (they need the "
                     "project's commands), then the folder, then what's online.")
    columns = [("1. elsewhere on your computer", "only if you set them up", [
                   ("Claude Desktop's settings", "mcp_server.py config --remove"),
                   ("Claude Code's server list", "claude mcp remove strainscope"),
                   ("the language model (Ollama)", "ollama rm llama3.2:3b"),
                   ("the container image", "docker rmi strainscope"),
                   ("Playwright's browsers", "playwright uninstall"),
                   ("pip's cache, renv's R packages", "pip cache purge; renv's folder")], GOLD),
               ("2. the project folder", "everything else is in here", [
                   ("the code, documents, results", "safe on GitHub"),
                   (".venv/ (the Python toolbox)", "rebuilt from requirements.txt"),
                   ("renv/library/ (links into renv)", "rebuilt from renv.lock"),
                   ("data/ (database, call log)", "rebuilt by the pipeline"),
                   (".env (your keys)", "revoke keys at the provider"),
                   ("the pre-push hook setting", "lives in .git/config")], DARK_GREEN),
               ("3. online", "only if you published them", [
                   ("the online copy", "share.streamlit.io, Delete"),
                   ("the GitHub Pages site", "Settings, Pages"),
                   ("the GitHub repository", "Settings, Danger Zone"),
                   ("API keys at providers", "on the provider's page")], BLUE)]
    for i, (title, note, items, colour) in enumerate(columns):
        x = 0.3 + i * 8.0
        box(ax, x, 0.4, 7.4, 11.4, colour, "", fill=tint(colour, 0.88))
        ax.text(x + 3.7, 11.25, title, ha="center", fontsize=10, fontweight="bold", color=INK)
        ax.text(x + 3.7, 10.7, note, ha="center", fontsize=8.1, color=SOFT, style="italic")
        for k, (what, how) in enumerate(items):
            y = 9.0 - k * 1.48
            box(ax, x + 0.35, y, 6.7, 1.2, colour, "", fill="white")
            ax.text(x + 0.6, y + 0.82, what, fontsize=8.2, color=INK, va="center")
            ax.text(x + 0.6, y + 0.36, how, fontsize=7.4, color=SOFT, va="center", family="monospace")
    save(fig, "footprint.png")


# =============================================================================
# 7. The interactive page
# =============================================================================

def write_explorer():
    plans = [{"name": name, "title": spec["title"], "takes": spec["takes"], "what": spec["what"],
              "steps": [sv.step_label(s) for s in spec["steps"]]} for name, spec in sv.PIPELINES.items()]
    data = json.dumps({"plans": plans, "jobs": ci_jobs(), "checklist": checklist()}, ensure_ascii=False)
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>StrainScope: release 1.0</title>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;color:#1F2933;background:#FFFFFF}}
h1{{font-size:22px}} h2{{font-size:16px;margin:18px 0 6px}} p{{color:#4B5563;line-height:1.5}}
.tabs button{{margin:0 6px 8px 0;padding:8px 12px;border:1px solid #DCE6F5;border-radius:8px;background:#F5F9FF;font-size:14px;cursor:pointer;color:#1F2933}}
.tabs button[aria-selected="true"]{{background:#E6F4EA;border-color:#2E7D5B;font-weight:600}}
.wrap{{display:flex;gap:18px;flex-wrap:wrap}} .list{{flex:0 0 240px}} .detail{{flex:1 1 560px;min-width:0}}
.list button{{display:block;width:100%;text-align:left;margin:0 0 6px;padding:8px 10px;border:1px solid #DCE6F5;border-radius:8px;background:#F5F9FF;font-size:14px;cursor:pointer;color:#1F2933}}
.list button.on{{background:#E8DDF8;border-color:#9C6ADE}}
button:focus-visible{{outline:3px solid #1A5FA6;outline-offset:2px}}
ol li, ul li{{margin:4px 0}} code{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px}}
table{{border-collapse:collapse;width:100%}} td,th{{border-bottom:1px solid #E3E6EA;padding:6px 8px;text-align:left;vertical-align:top;font-size:14px}}
</style></head><body>
<h1>StrainScope: release 1.0</h1>
<p>Phase 8 in three views, built from the project's own files: the one-command pipeline's plans
(<code>src/strainscope/service.py</code>), the jobs the automatic tests run at every push
(<code>.github/workflows/ci.yml</code>), and the product checklist of <code>docs/ROADMAP.md</code>.
The guide is <code>docs/09-packaging.md</code>. The data is simulated.</p>
<div class="tabs" role="tablist">
<button role="tab" id="t-plans" aria-selected="true" onclick="tab('plans')">The pipeline</button>
<button role="tab" id="t-jobs" aria-selected="false" onclick="tab('jobs')">The automatic tests</button>
<button role="tab" id="t-check" aria-selected="false" onclick="tab('check')">Finished?</button>
</div>
<div class="wrap" id="view"><div class="list" id="list"></div><div class="detail" id="detail"></div></div>
<script>
const DATA = {data};
const esc = s => String(s).replace(/[&<>]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;'}})[c]);
function pick(items, render) {{
  const list = document.getElementById('list'); list.innerHTML = '';
  items.forEach((it, i) => {{
    const b = document.createElement('button'); b.textContent = it.label;
    b.onclick = () => {{ list.querySelectorAll('button').forEach((x, k) => x.className = k === i ? 'on' : '');
                         document.getElementById('detail').innerHTML = render(it); }};
    list.appendChild(b);
  }});
  list.querySelector('button').click();
}}
function tab(name) {{
  ['plans', 'jobs', 'check'].forEach(t => document.getElementById('t-' + t).setAttribute('aria-selected', t === name));
  if (name === 'plans') pick(DATA.plans.map(p => ({{...p, label: p.name}})), p =>
    '<h2>' + esc(p.title) + '</h2><p>It ' + esc(p.what) + '. It takes ' + esc(p.takes) + '.</p>' +
    '<p><code>python src/strainscope/pipeline.py ' + esc(p.name) + '</code> runs, in order:</p><ol>' +
    p.steps.map(s => '<li><code>' + esc(s) + '</code></li>').join('') + '</ol>');
  if (name === 'jobs') pick(DATA.jobs.map(j => ({{...j, label: j.id}})), j =>
    '<h2>' + esc(j.name) + '</h2><p>Runs on <code>' + esc(j.runs_on) + '</code>' +
    (j.container ? ', inside <code>' + esc(j.container) + '</code>' : '') +
    (j.systems.length ? ', once for each of ' + j.systems.length * j.pythons.length + ' combinations: ' +
      esc(j.systems.join(', ')) + ' with Python ' + esc(j.pythons.join(' and ')) : '') + '.</p><ol>' +
    j.steps.map(s => '<li>' + esc(s) + '</li>').join('') + '</ol>');
  if (name === 'check') {{
    document.getElementById('list').innerHTML = '';
    document.getElementById('detail').innerHTML = '<h2>What "finished" means</h2><table><tr><th>A user can...</th>' +
      '<th>Built in</th><th>Status</th></tr>' + DATA.checklist.map(r => '<tr><td>' + esc(r.can) + '</td><td>' +
      esc(r.built_in) + '</td><td>' + esc(r.status) + '</td></tr>').join('') + '</table>';
  }}
}}
tab('plans');
</script></body></html>
"""
    (INT / "release_explorer.html").write_text(page, encoding="utf-8")
    print(f"  drew docs/interactive/release_explorer.html (interactive, {len(plans)} plans, "
          f"{len(ci_jobs())} CI jobs (GitHub runs them as {matrix_count(ci_jobs())}), {len(checklist())} checklist rows)")


if __name__ == "__main__":
    print("Phase 8 figures:")
    draw_one_command()
    draw_ci_matrix()
    draw_release_path()
    draw_container_box()
    draw_accessibility_check()
    draw_footprint()
    write_explorer()
