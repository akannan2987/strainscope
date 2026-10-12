"""
tests/test_deploy.py: what the online copy and a release rely on (Phases 7 and 8).
==================================================================================
What they protect, in plain words:
  * the online copy's packing list (app/requirements.txt) has the same
    packages as the project's own (requirements.txt), apart from pytest and
    mcp (the MCP server of Phase 7b runs on your own computer, never on the
    online copy), every one at an exact version, and scikit-learn at the
    version the saved model was built with;
  * the secrets template holds no secret and switches shared mode on;
  * a real secrets file can never be committed;
  * the GitHub Pages front page links only to files that exist;
  * the version shown on About this copy comes from CHANGELOG.md;
  * a release says the same thing everywhere (Phase 8): the citation file has
    the newest release's version and date, the licence is MIT, the container
    installs the online copy's packing list on the online copy's Python, and
    the automatic tests run the Python versions the guides promise;
  * Dependabot never moves scikit-learn away from the saved model.

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


# =============================================================================
# Phase 8: the release files agree with each other
# =============================================================================

def _yaml_value(path: Path, key: str) -> str:
    """One top-level value from a simple YAML file (no YAML package needed)."""
    m = re.search(rf"^{key}:\s*\"?([^\"\n]+)\"?\s*$", path.read_text(encoding="utf-8"), flags=re.M)
    return m.group(1).strip() if m else ""


def test_the_citation_file_has_the_newest_release():
    release = sv.release_info(ROOT / "CHANGELOG.md")
    cff = ROOT / "CITATION.cff"
    assert _yaml_value(cff, "cff-version") == "1.2.0"
    assert _yaml_value(cff, "version") == release["version"]
    assert _yaml_value(cff, "date-released") == release["date"]
    assert _yaml_value(cff, "license") == "MIT"


def test_the_licence_is_mit_with_a_name_and_year():
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert text.startswith("MIT License") and re.search(r"Copyright \(c\) 20\d\d \w+", text)


def test_the_container_runs_the_online_copy():
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"^FROM docker\.io/library/python:3\.14-slim$", docker, flags=re.M)
    assert "pip install -r app/requirements.txt" in docker
    assert "src/strainscope/pipeline.py database" in docker and "\nUSER " in docker
    ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8").split()
    assert {".env", ".streamlit/secrets.toml", ".git/", ".venv/"} <= set(ignored)


def test_the_automatic_tests_cover_three_systems_rhel_8_and_the_online_copy():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "system: [Linux, Windows, macOS]" in ci and 'python: ["3.12", "3.14"]' in ci
    assert "registry.access.redhat.com/ubi8/python-312" in ci
    assert "pip install -r app/requirements.txt pytest" in ci and "docker build" in ci
    for step in ("pipeline.py database", "pytest -q", "pipeline.py everything", "pipeline.py compare",
                 "tools/check_accessibility.py"):
        assert step in ci, step


def test_dependabot_leaves_scikit_learn_alone_and_targets_develop():
    bot = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    assert 'dependency-name: "scikit-learn"' in bot
    assert bot.count('target-branch: "develop"') == bot.count("package-ecosystem:") == 2
