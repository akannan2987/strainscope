"""
figures/make_illustrations.py: the project's logo and the Handbook's journey map.
=================================================================================
Writes small, crisp SVG pictures (vector graphics: they stay sharp at any
zoom, and they are plain text, so Git can track changes to them):

    docs/img/strainscope_logo.svg     the banner at the top of the README
    docs/img/strainscope_icon.svg     the square icon (app, social preview)
    docs/img/strainscope_wordmark.svg the icon and the name side by side (the app's sidebar)
    docs/img/journey_map.svg          the day-0-to-product road, with status

and one interactive page:

    docs/interactive/journey.html     the same journey, clickable: each stage's What, Why,
                                      Checkpoint and commit, read from docs/HANDBOOK.md

The journey map reads its stage list from STAGES below. When a phase is
finished, flip its status here, re-run this script, and the picture in the
Handbook updates. (The same status lives in docs/HANDBOOK.md and
docs/ROADMAP.md; all three are updated in the same commit.) The interactive
page takes its text from the Handbook itself, so it can't drift from it.

Run (from the project root, venv active):
    python figures/make_illustrations.py
"""
import html
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape   # turns "&" into "&amp;" so the SVG stays valid XML

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "img"
IMG.mkdir(parents=True, exist_ok=True)
INTERACTIVE = ROOT / "docs" / "interactive"
HANDBOOK = ROOT / "docs" / "HANDBOOK.md"
GITHUB = "https://github.com/akannan2987/strainscope/blob/master"

BLUE, GREEN, GOLD, GREY, PURPLE, RED = ("#5B8DEF", "#4CAF7D", "#C9A227",
                                        "#8A94A6", "#9C6ADE", "#D9634C")
INK = "#1F2933"

# (stage, short label, phase tag, symbol, status); status is done / next / later
STAGES = [
    ("0", "Understand", "why & what", "🧭", "done"),
    ("1", "Set up", "once per machine", "🧰", "done"),
    ("2", "Version control", "Git + safety gate", "🔒", "done"),
    ("3", "Synthetic data", "Phase 1", "🧪", "done"),
    ("4", "Real data", "Phase 1b", "🌍", "done"),
    ("5", "More sources", "Phase 1c", "🔑", "done"),
    ("6", "Clean + database", "Phase 2", "🧹", "done"),
    ("7", "Integrate", "Phase 3", "🔗", "done"),
    ("8", "Predict", "Phase 4", "🎯", "done"),
    ("9", "Knowledge graph", "Phase 5", "🕸️", "done"),
    ("10", "The app", "Phase 6", "🖥️", "done"),
    ("11", "Ask StrainScope", "Phase 6b", "💬", "done"),
    ("12", "Deploy + AI layer", "Phase 7", "☁️", "done"),
    ("13", "MCP server", "Phase 7b", "🔌", "done"),
    ("14", "Release 1.0", "Phase 8", "🚀", "done"),
    ("15", "Your own data", "Phase 9", "📥", "done"),
    ("16", "The product", "beyond the repo", "🏭", "next"),
]
STATUS_STYLE = {"done": (GREEN, "#E6F4EA", "built ✓"),
                "next": (GOLD, "#FFF3CD", "next"),
                "later": (GREY, "#F5F5F5", "planned")}


def logo_svg() -> str:
    """Banner: a petri dish with four colonies (one per kingdom), a magnifying
    lens joining two of them with a small network (reading several
    fingerprints at once), and the wordmark."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="720" height="200" viewBox="0 0 720 200" role="img" aria-label="StrainScope logo">
  <title>StrainScope</title>
  <rect width="720" height="200" rx="18" fill="#F5F9FF"/>
  <!-- petri dish -->
  <circle cx="110" cy="100" r="72" fill="#FFFFFF" stroke="{BLUE}" stroke-width="5"/>
  <circle cx="110" cy="100" r="62" fill="none" stroke="#B9D2FF" stroke-width="2"/>
  <!-- colonies: bacteria, fungi, yeast, oomycete -->
  <circle cx="80" cy="78" r="14" fill="{BLUE}"/>
  <circle cx="132" cy="70" r="10" fill="{GREEN}"/>
  <circle cx="92" cy="128" r="9" fill="{GOLD}"/>
  <circle cx="140" cy="118" r="12" fill="{PURPLE}"/>
  <!-- the integration network linking the colonies -->
  <g stroke="{INK}" stroke-width="2" opacity="0.55">
    <line x1="80" y1="78" x2="132" y2="70"/><line x1="132" y1="70" x2="140" y2="118"/>
    <line x1="80" y1="78" x2="92" y2="128"/><line x1="92" y1="128" x2="140" y2="118"/>
  </g>
  <!-- magnifying lens -->
  <circle cx="150" cy="118" r="30" fill="none" stroke="{INK}" stroke-width="6"/>
  <line x1="172" y1="140" x2="200" y2="168" stroke="{INK}" stroke-width="10" stroke-linecap="round"/>
  <!-- wordmark -->
  <text x="235" y="105" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="58" font-weight="700" fill="{INK}">Strain<tspan fill="{GREEN}">Scope</tspan></text>
  <text x="238" y="142" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="19" fill="#5f6b7a">multi-omics · machine learning · beneficial microbes</text>
</svg>
"""


def icon_svg() -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256" role="img" aria-label="StrainScope icon">
  <title>StrainScope icon</title>
  <rect width="256" height="256" rx="48" fill="#F5F9FF"/>
  <circle cx="118" cy="118" r="82" fill="#FFFFFF" stroke="{BLUE}" stroke-width="7"/>
  <circle cx="86" cy="94" r="16" fill="{BLUE}"/><circle cx="142" cy="84" r="12" fill="{GREEN}"/>
  <circle cx="98" cy="150" r="11" fill="{GOLD}"/><circle cx="152" cy="140" r="14" fill="{PURPLE}"/>
  <g stroke="{INK}" stroke-width="3" opacity="0.55">
    <line x1="86" y1="94" x2="142" y2="84"/><line x1="142" y1="84" x2="152" y2="140"/>
    <line x1="86" y1="94" x2="98" y2="150"/><line x1="98" y1="150" x2="152" y2="140"/>
  </g>
  <circle cx="164" cy="142" r="34" fill="none" stroke="{INK}" stroke-width="8"/>
  <line x1="189" y1="167" x2="222" y2="200" stroke="{INK}" stroke-width="13" stroke-linecap="round"/>
</svg>
"""


def wordmark_svg() -> str:
    """The icon and the name on one line, without the tagline: small spaces
    (the app's sidebar) need a short, wide picture that stays readable."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="400" height="96" viewBox="0 0 400 96" role="img" aria-label="StrainScope">
  <title>StrainScope</title>
  <g transform="translate(4,4) scale(0.34)">
    <circle cx="118" cy="118" r="82" fill="#FFFFFF" stroke="{BLUE}" stroke-width="9"/>
    <circle cx="86" cy="94" r="16" fill="{BLUE}"/><circle cx="142" cy="84" r="12" fill="{GREEN}"/>
    <circle cx="98" cy="150" r="11" fill="{GOLD}"/><circle cx="152" cy="140" r="14" fill="{PURPLE}"/>
    <g stroke="{INK}" stroke-width="4" opacity="0.55">
      <line x1="86" y1="94" x2="142" y2="84"/><line x1="142" y1="84" x2="152" y2="140"/>
      <line x1="86" y1="94" x2="98" y2="150"/><line x1="98" y1="150" x2="152" y2="140"/>
    </g>
    <circle cx="164" cy="142" r="34" fill="none" stroke="{INK}" stroke-width="10"/>
    <line x1="189" y1="167" x2="222" y2="200" stroke="{INK}" stroke-width="15" stroke-linecap="round"/>
  </g>
  <text x="96" y="62" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="44" font-weight="700" fill="{INK}">Strain<tspan fill="{GREEN}">Scope</tspan></text>
</svg>
"""


def journey_svg() -> str:
    """A winding road of stepping stones: two rows (the first one longer when
    the count is odd), left to right then right to left, so the whole journey
    fits on one screen."""
    width, height = 1180, 470
    per_row = (len(STAGES) + 1) // 2
    step = 1000 / (per_row - 1)
    xs = [round(90 + i * step) for i in range(per_row)]
    rows = [(150, xs), (345, list(reversed(xs))[:len(STAGES) - per_row])]
    points = []
    for (y, row_xs) in rows:
        points += [(x, y) for x in row_xs]
    last = per_row - 1
    path = f"M {points[0][0]} {points[0][1]} " + " ".join(
        f"L {x} {y}" for x, y in points[1:per_row])
    path += (f" C {points[last][0] + 90} {points[last][1]}, {points[per_row][0] + 90} {points[per_row][1]}, "
             f"{points[per_row][0]} {points[per_row][1]} ")
    path += " ".join(f"L {x} {y}" for x, y in points[per_row + 1:])
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}" role="img" aria-label="StrainScope journey map">',
           "<title>StrainScope: the journey from day 0 to the product</title>",
           f'<rect width="{width}" height="{height}" rx="18" fill="#FBFCFE"/>',
           f'<text x="{width / 2}" y="44" text-anchor="middle" font-family="Segoe UI, Helvetica, Arial, '
           f'sans-serif" font-size="22" font-weight="700" fill="{INK}">The StrainScope journey, '
           'from a blank laptop to a finished product</text>',
           f'<path d="{path}" fill="none" stroke="#D5DCE6" stroke-width="16" stroke-linecap="round" '
           'stroke-linejoin="round"/>']
    for (x, y), (num, label, tag, symbol, status) in zip(points, STAGES):
        edge, fill, word = STATUS_STYLE[status]
        label, tag = escape(label), escape(tag)
        # The stage NUMBER goes inside the stone (it renders everywhere); the
        # emoji symbols live in the Handbook's tables, where text fonts draw them.
        tick = "✓" if status == "done" else ("▶" if status == "next" else "")
        out += [f'<circle cx="{x}" cy="{y}" r="34" fill="{fill}" stroke="{edge}" stroke-width="4"/>',
                f'<text x="{x}" y="{y + 10}" text-anchor="middle" font-family="Segoe UI, Helvetica, '
                f'Arial, sans-serif" font-size="28" font-weight="700" fill="{edge}">{num}</text>',
                f'<text x="{x + 26}" y="{y - 24}" font-family="Segoe UI, Helvetica, Arial, sans-serif" '
                f'font-size="16" font-weight="700" fill="{edge}">{tick}</text>',
                f'<text x="{x}" y="{y + 56}" text-anchor="middle" font-family="Segoe UI, Helvetica, '
                f'Arial, sans-serif" font-size="13.5" font-weight="600" fill="{INK}">{label}</text>',
                f'<text x="{x}" y="{y + 73}" text-anchor="middle" font-family="Segoe UI, Helvetica, '
                f'Arial, sans-serif" font-size="11.5" fill="#5f6b7a">{tag}</text>']
    legend_y = height - 22
    for i, (status, (edge, fill, word)) in enumerate(STATUS_STYLE.items()):
        lx = 380 + i * 150
        out += [f'<circle cx="{lx}" cy="{legend_y - 4}" r="8" fill="{fill}" stroke="{edge}" stroke-width="3"/>',
                f'<text x="{lx + 16}" y="{legend_y}" font-family="Segoe UI, Helvetica, Arial, sans-serif" '
                f'font-size="13" fill="{INK}">{word}</text>']
    out.append("</svg>")
    return "\n".join(out) + "\n"


# =============================================================================
# The interactive journey, read from docs/HANDBOOK.md
# =============================================================================

def github_anchor(heading: str) -> str:
    """The link anchor GitHub gives a heading: lower case, punctuation
    dropped, spaces turned into hyphens ("Stage 7.1: Fix ..." -> "stage-71-fix-...")."""
    text = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return text.replace(" ", "-")


def md_inline(text: str, base: str = "docs") -> str:
    """The little Markdown the Handbook uses inside a paragraph, as HTML:
    **bold**, *italics*, `code` and [links](...). Relative links are turned
    into links to the same file on GitHub, so they work from a downloaded page."""
    def link(m):
        label, target = m.group(1), m.group(2)
        if target.startswith("#"):
            url = f"{GITHUB}/docs/HANDBOOK.md{target}"
        elif re.match(r"https?://", target):
            url = target
        else:
            path = (Path(base) / target.split("#")[0]).as_posix()
            parts = []
            for piece in path.split("/"):
                if piece == "..":
                    parts.pop()
                elif piece not in ("", "."):
                    parts.append(piece)
            url = f"{GITHUB}/{'/'.join(parts)}" + (f"#{target.split('#', 1)[1]}" if "#" in target else "")
        return f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener">{label}</a>'
    codes: list[str] = []

    def keep_code(m):                   # protect `code` from the other rules
        codes.append(f"<code>{html.escape(m.group(1) or m.group(2))}</code>")
        return f"\x00{len(codes) - 1}\x00"
    out = re.sub(r"``\s?(.+?)\s?``|`([^`]+)`", keep_code, text)
    out = html.escape(out, quote=False)
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, out)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"<em>\1</em>", out)
    return re.sub("\x00(\\d+)\x00", lambda m: codes[int(m.group(1))], out)


def handbook_stages(path: Path = HANDBOOK) -> list[dict]:
    """Each stage of the Handbook: its row in the stage table and its
    What, Why, Checkpoint and commit paragraphs."""
    text = path.read_text(encoding="utf-8")
    rows = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 6 and re.fullmatch(r"\d+(\.\d+)?", cells[0]):
            rows[cells[0]] = {"area": cells[1], "title": cells[2], "guide": cells[3], "time": cells[4],
                              "status": cells[5]}
    # Split the Handbook into sections at "## " headings, ignoring lines inside
    # code blocks (a "## --tags ..." comment in a command block isn't a heading).
    sections, heading, lines, in_code = [], None, [], False
    for line in text.splitlines():
        if line.startswith("```"):
            in_code = not in_code
        if line.startswith("## ") and not in_code:
            if heading:
                sections.append((heading, lines))
            heading, lines = line[3:].strip(), []
        elif heading:
            lines.append(line)
    if heading:
        sections.append((heading, lines))
    stages = []
    for heading, body in sections:
        m = re.match(r"Stage (\d+(?:\.\d+)?): ", heading)
        if not m:
            continue
        number = m.group(1)
        parts, current, in_code = {}, None, False
        for line in body:
            if line.startswith("```"):           # code blocks and diagrams stay in the Handbook
                in_code = not in_code
                continue
            if in_code:
                continue
            label = re.match(r"\*\*(What|Why|Checkpoint(?: \(planned\))?|Commit messages? used|Commit message)[.:]?\*\*[.:]?\s*(.*)", line)
            if label:
                current = label.group(1).split(" (")[0].replace("messages used", "message").replace("message used", "message")
                current = "Commit" if current.startswith("Commit") else current
                parts[current] = [label.group(2)]
            elif current and line.strip() and not line.startswith(("![", "|", ">", "    ")):
                parts[current].append(line.strip())
        def to_html(lines):
            out, items = [], []
            for ln in lines:
                if re.match(r"\d+\. ", ln):
                    items.append(md_inline(re.sub(r"^\d+\. ", "", ln)))
                else:
                    if items:
                        out.append("<ol>" + "".join(f"<li>{i}</li>" for i in items) + "</ol>")
                        items = []
                    if ln:
                        out.append(f"<p>{md_inline(ln)}</p>")
            if items:
                out.append("<ol>" + "".join(f"<li>{i}</li>" for i in items) + "</ol>")
            return "".join(out)
        row = rows.get(number, {})
        stages.append({"number": number, "heading": heading.split(": ", 1)[1],
                       "anchor": f"{GITHUB}/docs/HANDBOOK.md#{github_anchor(heading)}",
                       "area": row.get("area", ""), "time": row.get("time", ""),
                       "subtitle": row.get("title", "").split(": ", 1)[-1],
                       "guide": md_inline(row.get("guide", "")) if row.get("guide") else "",
                       **{k.lower(): to_html(v) for k, v in parts.items()}})
    status_of = {num: status for num, _, _, _, status in STAGES}
    for st in stages:
        st["status"] = status_of.get(st["number"], "done")
    return stages


def journey_html() -> str:
    """A small, self-contained page: no internet, no libraries."""
    stages = handbook_stages()
    words = {"done": "built", "next": "next", "later": "planned"}
    data = json.dumps(stages, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>StrainScope journey</title>
<style>
  :root {{ --ink:{INK}; --soft:#5f6b7a; --line:#D5DCE6; --bg:#FBFCFE; --done:{GREEN}; --next:{GOLD}; --later:{GREY}; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family: "Segoe UI", Helvetica, Arial, sans-serif; color:var(--ink); background:var(--bg); }}
  header {{ padding:24px 24px 8px; max-width:1100px; margin:0 auto; }}
  h1 {{ font-size:24px; margin:0 0 6px; }}
  header p {{ margin:4px 0; color:var(--soft); }}
  .filters {{ display:flex; gap:8px; flex-wrap:wrap; margin:12px 0 4px; }}
  .filters button {{ border:1px solid var(--line); background:#fff; border-radius:999px; padding:6px 14px; cursor:pointer; font:inherit; color:var(--ink); }}
  .filters button[aria-pressed="true"] {{ background:var(--ink); color:#fff; border-color:var(--ink); }}
  .road {{ display:grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap:12px; padding:12px 24px; max-width:1100px; margin:0 auto; }}
  .stone {{ border:2px solid var(--later); background:#fff; border-radius:14px; padding:10px 12px; text-align:left; cursor:pointer; font:inherit; color:var(--ink); }}
  .stone .num {{ display:inline-block; min-width:30px; height:30px; line-height:26px; text-align:center; border-radius:15px; border:2px solid var(--later); font-weight:700; margin-right:6px; }}
  .stone .what {{ font-weight:600; }}
  .stone .tag {{ display:block; font-size:12px; color:var(--soft); margin-top:4px; }}
  .stone.done, .stone.done .num {{ border-color:var(--done); }}
  .stone.next, .stone.next .num {{ border-color:var(--next); }}
  .stone.later {{ border-style:dashed; }}
  .stone[aria-selected="true"] {{ box-shadow:0 0 0 3px #B9D2FF; }}
  .stone:focus-visible {{ outline:3px solid #5B8DEF; outline-offset:2px; }}
  .detail {{ max-width:1100px; margin:8px auto 40px; padding:0 24px; }}
  .card {{ background:#fff; border:1px solid var(--line); border-radius:16px; padding:18px 22px; }}
  .card h2 {{ margin:0 0 4px; font-size:20px; }}
  .meta {{ color:var(--soft); font-size:14px; margin-bottom:10px; }}
  .badge {{ display:inline-block; padding:2px 10px; border-radius:999px; font-size:12px; font-weight:700; color:#fff; margin-right:6px; }}
  .badge.done {{ background:var(--done); }} .badge.next {{ background:var(--next); }} .badge.later {{ background:var(--later); }}
  .section h3 {{ font-size:13px; text-transform:uppercase; letter-spacing:.06em; color:var(--soft); margin:14px 0 4px; }}
  .section p, .section li {{ line-height:1.55; margin:4px 0; }}
  code {{ background:#F1F4F8; padding:1px 5px; border-radius:5px; font-size:90%; }}
  a {{ color:#2E5FC1; }}
  footer {{ text-align:center; color:var(--soft); font-size:12px; padding:0 0 30px; }}
</style></head>
<body>
<header>
  <h1>The StrainScope journey</h1>
  <p>From a blank laptop to a finished product. Pick a stage to see what you do, why, and how you know you're done.</p>
  <p>Green: {words["done"]} · gold: {words["next"]} · dashed grey: {words["later"]}. Every word below comes from <a href="{GITHUB}/docs/HANDBOOK.md" target="_blank" rel="noopener">docs/HANDBOOK.md</a>.</p>
  <div class="filters" role="group" aria-label="Show stages">
    <button data-filter="all" aria-pressed="true">All stages</button>
    <button data-filter="done" aria-pressed="false">Built</button>
    <button data-filter="next" aria-pressed="false">Next</button>
    <button data-filter="later" aria-pressed="false">Planned</button>
  </div>
</header>
<nav class="road" id="road" aria-label="Stages"></nav>
<main class="detail" id="detail" aria-live="polite"></main>
<footer>StrainScope: a learning project built in the open. The data is simulated and disclosed as such.</footer>
<script>
const STAGES = {data};
const WORDS = {json.dumps(words)};
const road = document.getElementById("road"), detail = document.getElementById("detail");
function show(i) {{
  const s = STAGES[i];
  document.querySelectorAll(".stone").forEach((b, j) => b.setAttribute("aria-selected", j === i));
  const block = (title, body) => body ? `<div class="section"><h3>${{title}}</h3>${{body}}</div>` : "";
  detail.innerHTML = `<article class="card">
    <h2>Stage ${{s.number}}: ${{s.heading}}</h2>
    <div class="meta"><span class="badge ${{s.status}}">${{WORDS[s.status]}}</span>${{s.area}}${{s.time ? " · " + s.time : ""}}${{s.guide ? " · guide: " + s.guide : ""}}</div>
    ${{block("What", s.what)}}${{block("Why", s.why)}}${{block("Checkpoint", s.checkpoint)}}${{block("Commit", s.commit)}}
    <p><a href="${{s.anchor}}" target="_blank" rel="noopener">Read this stage in the Handbook</a></p></article>`;
  history.replaceState(null, "", "#stage-" + s.number);
}}
STAGES.forEach((s, i) => {{
  const b = document.createElement("button");
  b.className = "stone " + s.status; b.dataset.status = s.status;
  b.innerHTML = `<span class="num">${{s.number}}</span><span class="what">${{s.heading.split(",")[0]}}</span><span class="tag">${{s.heading.includes(",") ? s.subtitle : s.area}} · ${{WORDS[s.status]}}</span>`;
  b.addEventListener("click", () => show(i));
  road.appendChild(b);
}});
document.querySelectorAll(".filters button").forEach(f => f.addEventListener("click", () => {{
  document.querySelectorAll(".filters button").forEach(x => x.setAttribute("aria-pressed", x === f));
  document.querySelectorAll(".stone").forEach(b => b.hidden = !(f.dataset.filter === "all" || b.dataset.status === f.dataset.filter));
}}));
const wanted = location.hash.replace("#stage-", "");
const start = STAGES.findIndex(s => s.number === wanted);
show(start >= 0 ? start : Math.max(0, STAGES.findIndex(s => s.status === "next")));
</script>
</body></html>
"""


if __name__ == "__main__":
    for name, svg in [("strainscope_logo.svg", logo_svg()), ("strainscope_icon.svg", icon_svg()),
                      ("strainscope_wordmark.svg", wordmark_svg()), ("journey_map.svg", journey_svg())]:
        (IMG / name).write_text(svg, encoding="utf-8")
        print(f"  drew docs/img/{name}")
    INTERACTIVE.mkdir(parents=True, exist_ok=True)
    (INTERACTIVE / "journey.html").write_text(journey_html(), encoding="utf-8")
    print(f"  wrote docs/interactive/journey.html ({len(handbook_stages())} stages, read from docs/HANDBOOK.md)")
