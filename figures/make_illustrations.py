"""
figures/make_illustrations.py: the project's logo and the Handbook's journey map.
=================================================================================
Writes small, crisp SVG pictures (vector graphics: they stay sharp at any
zoom, and they are plain text, so Git can track changes to them):

    docs/img/strainscope_logo.svg     the banner at the top of the README
    docs/img/strainscope_icon.svg     the square icon (app, social preview)
    docs/img/journey_map.svg          the day-0-to-product road, with status

The journey map reads its stage list from STAGES below. When a phase is
finished, flip its status here, re-run this script, and the picture in the
Handbook updates. (The same status lives in docs/HANDBOOK.md and
docs/ROADMAP.md; all three are updated in the same commit.)

Run (from the project root, venv active):
    python figures/make_illustrations.py
"""
from pathlib import Path
from xml.sax.saxutils import escape   # turns "&" into "&amp;" so the SVG stays valid XML

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "img"
IMG.mkdir(parents=True, exist_ok=True)

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
    ("10", "The app", "Phase 6", "🖥️", "next"),
    ("11", "Ask StrainScope", "Phase 6b", "💬", "later"),
    ("12", "Deploy + AI layer", "Phase 7", "☁️", "later"),
    ("13", "MCP server", "Phase 7b", "🔌", "later"),
    ("14", "Release 1.0", "Phase 8", "🚀", "later"),
    ("15", "The product", "beyond the repo", "🏭", "later"),
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


def journey_svg() -> str:
    """A winding road of stepping stones: two rows of eight, left to right then
    right to left, so the whole journey fits on one screen."""
    width, height = 1180, 470
    xs = [90 + i * 143 for i in range(8)]
    rows = [(150, xs), (345, list(reversed(xs)))]
    points = []
    for (y, row_xs) in rows:
        points += [(x, y) for x in row_xs]
    path = f"M {points[0][0]} {points[0][1]} " + " ".join(
        f"L {x} {y}" for x, y in points[1:8])
    path += f" C {points[7][0] + 90} {points[7][1]}, {points[8][0] + 90} {points[8][1]}, {points[8][0]} {points[8][1]} "
    path += " ".join(f"L {x} {y}" for x, y in points[9:])
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


if __name__ == "__main__":
    for name, svg in [("strainscope_logo.svg", logo_svg()), ("strainscope_icon.svg", icon_svg()),
                      ("journey_map.svg", journey_svg())]:
        (IMG / name).write_text(svg, encoding="utf-8")
        print(f"  drew docs/img/{name}")
