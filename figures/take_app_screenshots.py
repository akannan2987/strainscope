"""
figures/take_app_screenshots.py: pictures of the running app (optional).
========================================================================
Takes the screenshots used in README.md, docs/07-app.md, docs/07b-docs-assistant.md,
docs/08-deployment-ai.md and docs/HANDBOOK.md, plus a short animated tour:

    docs/img/app_home.png         the front page
    docs/img/app_ask.png          Ask StrainScope answering a question from the documents
    docs/img/app_ask_data.png     Ask the data: a recipe found, its query and its table (Phase 7)
    docs/img/app_ask_graph.png    Ask the graph: the route and the numbered facts (Phase 7)
    docs/img/app_about.png        About this copy: version, health, AI features (Phase 7)
    docs/img/app_ranking.png      the ranking and the "test N strains" question
    docs/img/app_plain_words.png  one strain in plain words (Phase 7)
    docs/img/app_strain.png       one strain: its reasons and its corner of the graph
    docs/img/app_graph.png        the path finder (the decoy accE has only a statistic)
    docs/img/app_sql.png          a cookbook recipe run in the SQL console
    docs/img/app_upload.png       twelve uploaded strains, checked and scored
    docs/img/app_tour.gif         the same pages as a slideshow

You only need this when the app's look changes; the pictures are committed.
It drives a real browser, so it needs Playwright, which isn't in
requirements.txt because nothing else uses it. Once per machine:

    pip install playwright
    python -m playwright install chromium

Then, from the project root, with the venv active and the database built:

    python figures/take_app_screenshots.py

It starts the app on port 8599, takes the pictures, and stops the app again.
(If your Chromium lives somewhere unusual, point STRAINSCOPE_CHROMIUM at it.)
"""
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "img"
PORT = 8599
BASE = f"http://localhost:{PORT}"
sys.path.insert(0, str(ROOT / "src"))


def start_app() -> subprocess.Popen:
    """Start the app in the background and wait until it answers."""
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(ROOT / "app" / "streamlit_app.py"),
                             "--server.headless", "true", "--server.port", str(PORT)],
                            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            urllib.request.urlopen(BASE, timeout=1)
            return proc
        except OSError:
            time.sleep(0.5)
    proc.terminate()
    sys.exit("The app didn't start within 30 seconds. Try: python -m streamlit run app/streamlit_app.py")


def settle(page, seconds: float = 3.5) -> None:
    """Give Streamlit time to rerun and draw (charts arrive a moment after the text)."""
    page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=30000)
    page.wait_for_timeout(int(seconds * 1000))


def choose(page, label: str, value: str) -> None:
    """Pick `value` in the dropdown whose label is `label` (type to search, then Enter)."""
    box = page.locator("[data-testid='stSelectbox']").filter(has=page.get_by_text(label, exact=True))
    box.locator("input").click()
    page.keyboard.type(value)
    page.keyboard.press("Enter")


def main() -> None:
    from playwright.sync_api import sync_playwright
    from strainscope import service as sv
    if not sv.DB_PATH.exists():
        sys.exit("Build the database first (Data page, or python src/strainscope/harmonize.py).")
    example = Path(tempfile.mkdtemp()) / "strainscope_example.csv"
    sv.example_upload().to_csv(example, index=False)
    frames: list[Path] = []
    proc = start_app()
    try:
        with sync_playwright() as p:
            chromium = os.environ.get("STRAINSCOPE_CHROMIUM")
            browser = p.chromium.launch(executable_path=chromium) if chromium else p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 860})

            def shot(name: str, frame: bool = True) -> None:
                path = IMG / name
                page.screenshot(path=str(path))
                print(f"  took docs/img/{name}")
                if frame:
                    frames.append(path)

            page.goto(BASE)
            settle(page)
            shot("app_home.png")

            page.goto(f"{BASE}/ask")
            settle(page)
            box = page.get_by_role("textbox", name="Your question")
            box.fill("What is a balanced error rate?")
            box.press("Enter")
            settle(page, 4)
            shot("app_ask.png")

            page.goto(f"{BASE}/ask_data")
            settle(page)
            box = page.get_by_role("textbox", name="Your question")
            box.fill("Which strains are borderline?")
            box.press("Enter")
            settle(page, 4)
            shot("app_ask_data.png")

            page.goto(f"{BASE}/ask_graph")
            settle(page)
            box = page.get_by_role("textbox", name="Your question")
            box.fill("How does iturin suppress disease?")
            box.press("Enter")
            settle(page, 4)
            shot("app_ask_graph.png")

            page.goto(f"{BASE}/about")
            settle(page)
            shot("app_about.png", frame=False)

            page.goto(f"{BASE}/ranking")
            settle(page)
            page.get_by_role("heading", name="If you can test N strains, how many would work?").scroll_into_view_if_needed()
            settle(page, 1.5)
            shot("app_ranking.png")

            page.goto(f"{BASE}/strain?strain=STRAIN_0485")
            settle(page, 5)
            page.get_by_text("In plain words", exact=True).scroll_into_view_if_needed()
            settle(page, 1.5)
            shot("app_plain_words.png")
            page.get_by_role("heading", name="Why it ranks here").scroll_into_view_if_needed()
            settle(page, 1.5)
            shot("app_strain.png")
            page.get_by_role("heading", name="Its corner of the knowledge graph").scroll_into_view_if_needed()
            settle(page, 1.5)
            frames.append(IMG / "_frame_strain_graph.png")
            page.screenshot(path=str(frames[-1]))

            page.goto(f"{BASE}/knowledge_graph")
            settle(page, 4)
            page.get_by_role("tab", name="Find a path").click()
            settle(page, 1.5)
            choose(page, "From", "accE")
            settle(page, 3)
            shot("app_graph.png")

            page.goto(f"{BASE}/sql_console")
            settle(page)
            choose(page, "Section", "10. The knowledge graph")
            settle(page, 2)
            page.get_by_role("button", name="Put this recipe in the editor").click()
            settle(page, 2)
            page.get_by_role("button", name="Run", exact=True).click()
            settle(page, 3)
            shot("app_sql.png")

            page.goto(f"{BASE}/data")
            settle(page)
            page.get_by_role("tab", name="Upload your strains").click()
            settle(page, 1.5)
            page.locator("input[type='file']").set_input_files(str(example))
            settle(page, 8)
            page.get_by_text("4. The result.").scroll_into_view_if_needed()
            settle(page, 1.5)
            shot("app_upload.png")
            browser.close()
    finally:
        proc.terminate()
        proc.wait(timeout=20)

    from PIL import Image
    pictures = [Image.open(f).convert("RGB") for f in frames]
    small = [im.resize((960, round(im.height * 960 / im.width)), Image.LANCZOS) for im in pictures]
    small = [im.quantize(colors=96, method=Image.MEDIANCUT) for im in small]
    small[0].save(IMG / "app_tour.gif", save_all=True, append_images=small[1:], duration=2600, loop=0,
                  optimize=True)
    print("  made docs/img/app_tour.gif")
    for f in frames:
        if f.name.startswith("_frame"):
            f.unlink()


if __name__ == "__main__":
    main()
