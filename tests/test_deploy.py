"""
tests/test_deploy.py: what the online copy relies on (Phase 7).
===============================================================
What they protect, in plain words:
  * the online copy's packing list (app/requirements.txt) has the same
    packages as the project's own (requirements.txt), apart from pytest and
    mcp (the MCP server of Phase 7b runs on your own computer, never on the
    online copy), every one at an exact version, and scikit-learn at the
    version the saved model was built with;
  * the secrets template holds no secret and switches shared mode on;
  * a real secrets file can never be committed;
  * the GitHub Pages front page links only to files that exist;
  * the version shown on About this copy comes from CHANGELOG.md.

Run:  pytest -q tests/test_deploy.py
"""
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from strainscope import service as sv  # noqa: E402


def packages(path: Path) -> dict[str, str]:
    """{name: exact version or ''} from a requirements file (comments
    skipped; a range such as mcp>=2,<3 counts as no exact version)."""
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if line:
            name = re.split(r"[<>=!~;\[ ]", line, maxsplit=1)[0]
            _, _, version = line.partition("==")
            out[name.strip().lower()] = version.strip()
    return out


NOT_ONLINE = {"pytest", "mcp"}      # the tests, and the MCP server of Phase 7b, run on your own computer only


def test_the_online_copy_installs_the_same_packages_at_exact_versions():
    local, online = packages(ROOT / "requirements.txt"), packages(ROOT / "app" / "requirements.txt")
    assert "mcp" in local and not NOT_ONLINE & set(online)
    assert set(online) == set(local) - NOT_ONLINE
    assert all(re.fullmatch(r"\d+(\.\d+)+", v) for v in online.values()), online


def test_scikit_learn_matches_the_saved_model():
    online = packages(ROOT / "app" / "requirements.txt")
    assert online["scikit-learn"] == sv.model_card()["versions"]["scikit-learn"]


def test_the_secrets_template_holds_no_secret():
    text = (ROOT / ".streamlit" / "secrets.toml.example").read_text(encoding="utf-8")
    values = tomllib.loads(text)
    assert values == {"STRAINSCOPE_MODE": "public"}                  # everything else is commented out
    assert "your-key" in text and not re.search(r"\b(sk|gsk|AIza)[-_A-Za-z0-9]{16,}", text)


def test_a_real_secrets_file_is_ignored_by_git():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".streamlit/secrets.toml" in ignored and ".env" in ignored


def test_the_pages_front_page_links_to_files_that_exist():
    html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    local = [h for h in re.findall(r'(?:href|src)="([^"]+)"', html) if not h.startswith(("http", "#"))]
    assert local and all((ROOT / "docs" / h).is_file() for h in local), local
    assert (ROOT / "docs" / ".nojekyll").is_file()


def test_the_version_comes_from_the_changelog(tmp_path):
    log = tmp_path / "CHANGELOG.md"
    log.write_text("# Changelog\n\n## [Unreleased]\n\nNothing yet.\n\n## [0.3.0] - 2026-10-12: usable by anyone\n",
                   encoding="utf-8")
    assert sv.release_info(log) == {"version": "0.3.0", "date": "2026-10-12", "title": "usable by anyone",
                                    "unreleased": False}
    log.write_text(log.read_text().replace("Nothing yet.", "### Added\n- something"), encoding="utf-8")
    assert sv.release_info(log)["unreleased"] is True
    assert sv.release_info(ROOT / "CHANGELOG.md")["version"] != "unknown"
