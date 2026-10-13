# Uninstalling StrainScope, completely and safely

[← README](../README.md) · [Handbook](HANDBOOK.md) · [Phase 8: packaging and release](09-packaging.md) · [Glossary](GLOSSARY.md)

**Prerequisites:** none. If you only want to stop using StrainScope for a while, you don't need this page: close the app (Ctrl+C in its terminal) and leave the folder where it is.
**Learning goal:** know every place StrainScope can leave something behind, on your computer and online, and remove each one in an order that never loses anything you meant to keep.

Almost everything lives **inside the project folder**: the code, the Python toolbox (`.venv/`), the data and the database (`data/`, with your datasets), your keys (`.env`). Deleting that one folder removes it all. A few things live elsewhere: the R packages themselves (renv keeps them in a cache shared by all your R projects, and `renv/library/` in the folder only points at them), and, only if you set them up yourself, an AI assistant app's connection to the MCP server, a language model, a container image, browsers for the optional checks, and the copies you published online.

![Everything StrainScope puts on a computer and online, and how each piece is removed](../figures/footprint.png)

**The order matters.** Do part 1 first: some of those steps use the project's own commands, which disappear with the folder. Then the folder (part 2), then whatever you put online (part 3).

All commands run in a terminal opened in the project folder, with the toolbox switched on (`source .venv/bin/activate`; Windows PowerShell: `.\.venv\Scripts\Activate.ps1`), unless a step says otherwise.

---

## 0. Before you delete: what you can't get back

- **Work you haven't pushed.** `git status` lists changed files; `git log --branches --not --remotes --oneline` lists commits that exist only on this computer. Push them first (the commit ritual in the [Handbook, Stage 2](HANDBOOK.md#stage-2-version-control-and-the-safety-gate)), or they go with the folder.
- **Real data you fetched.** The synthetic library comes back identical from its seed, but the public databases change over time, so a later fetch may not return today's records ([`docs/02b-real-data-ingestion.md`](02b-real-data-ingestion.md)). If an analysis depended on them, copy `data/raw/real/` somewhere first.
- **Your datasets** (Phase 9). Each one is a folder in `data/processed/datasets/`, never on GitHub, and a dataset of your own can't be rebuilt from a seed. To keep one, copy its folder somewhere else first, or download its tables on the Workflow page (*Download every table*). `python src/strainscope/datasets.py list` shows them all ([`docs/10-workflow-and-your-data.md` §14](10-workflow-and-your-data.md#14-removing-a-dataset)).
- **Your keys.** `.env` holds them, and it's never on GitHub. If you'll need a key again, note it somewhere safe; if not, delete it at the provider (part 3).

Nothing else is lost: the code, the documents and the committed results are on GitHub, and an uploaded strain file was never stored by the app in the first place.

---

## 1. Outside the project folder (only what you set up)

### Claude Desktop's connection to the MCP server

If you connected Claude Desktop in [Phase 7b](08b-mcp-server.md#9-step-5-connect-an-assistant-app), take the entry out of its settings file:

```bash
python src/strainscope/mcp_server.py config --remove
```

**You should see** the file's place on your computer, then (with your own date and time in the backup's name):

```
  ── Claude Desktop's settings file: remove the strainscope entry ──
  /Users/<you>/Library/Application Support/Claude/claude_desktop_config.json

  backup → claude_desktop_config.backup-20261012-211623.json (next to it)
  ✓ strainscope entry removed; other settings kept: preferences

  Quit Claude Desktop completely and start it again: it reads the file only when it starts.
```

Only the `strainscope` entry goes; the app's other settings stay (the last line names yours, so it may list other things than `preferences`). The backups `config --write` and `config --remove` left next to the file (`claude_desktop_config.backup-....json`) can be deleted once Claude Desktop works without StrainScope. On Windows, if you had also added the entry to the Store version's second settings file ([Phase 7b §9](08b-mcp-server.md#a-claude-desktop-macos-and-windows)), run the command again with `--file` and that file's path. To do it by hand instead, open the file as in Phase 7b §9 and delete the `"strainscope": { ... }` part, with the comma before it (or after it, if it's the first entry).

### Claude Code's connection

If you added the server to Claude Code, remove it with the same scope you added it with (Phase 7b used `--scope user`):

```bash
claude mcp remove strainscope --scope user
claude mcp list
```

`claude mcp list` should no longer show a line for `strainscope`.

### The language model (Ollama)

If you downloaded a model only for StrainScope ([`docs/LANGUAGE_MODEL.md`](LANGUAGE_MODEL.md) setup A), remove it; that frees about 2 GB:

```bash
ollama rm llama3.2:3b
```

Ollama itself is a separate program that other projects may use. To remove it as well, follow the *Uninstall* part of its own page for your system: [macOS](https://docs.ollama.com/macos), [Windows](https://docs.ollama.com/windows) (it registers an uninstaller under *Add or remove programs*) or [Linux](https://docs.ollama.com/linux).

### The container image (Phase 8)

If you built the container ([`docs/09-packaging.md` §11](09-packaging.md#11-step-7-optional-run-the-app-in-a-container)), stop any copy that's still running (Ctrl+C in its terminal), then delete the image:

```bash
docker rmi strainscope            # with Podman: podman rmi strainscope
```

If Docker answers that the image is in use, `docker ps -a --filter ancestor=strainscope` lists the containers made from it, and `docker rm <the container's id>` removes one. The base image it started from stays in Docker's store, where other projects may use it; if none do, remove it too: `docker rmi python:3.14-slim` (Podman: `podman rmi docker.io/library/python:3.14-slim`).

### Browsers for the screenshots and the accessibility check

Only if you installed Playwright for `figures/take_app_screenshots.py` or `tools/check_accessibility.py`. With the toolbox switched on, and **before** you delete the folder (the command lives in the toolbox):

```bash
python -m playwright uninstall
```

The browsers live outside the folder, in `~/Library/Caches/ms-playwright` (macOS), `~/.cache/ms-playwright` (Linux) or `%USERPROFILE%\AppData\Local\ms-playwright` (Windows). If the folder is already gone, delete that folder directly instead: `rm -rf ~/Library/Caches/ms-playwright` (macOS), `rm -rf ~/.cache/ms-playwright` (Linux), or in Windows PowerShell `Remove-Item -Recurse -Force "$env:LOCALAPPDATA\ms-playwright"`.

### Package caches (optional, shared with other projects)

pip keeps a copy of every package it downloaded, so the next install is quicker. renv keeps the R packages themselves in its cache, installed once and shared by every R project that uses renv. Both caches serve every project on the computer, so clear them only if you're done with Python or R work in general:

- pip: `python -m pip cache purge`
- renv: delete its folder, `rm -rf ~/Library/Caches/org.R-project.R/R/renv` (macOS), `rm -rf ~/.cache/R/renv` (Linux), or in Windows PowerShell `Remove-Item -Recurse -Force "$env:LOCALAPPDATA\R\cache\R\renv"`

### The pre-push hook

Nothing to do. If you switched on the hook ([`docs/09-packaging.md` §9](09-packaging.md#9-step-5-optional-let-git-run-the-safety-gate-before-every-push)), the setting is stored in `.git/config`, inside the folder.

---

## 2. The project folder

Switch the toolbox off, step out of the folder, and delete it. On Windows, close any editor or terminal that still has the folder open, or Windows refuses to delete it.

```bash
deactivate
cd ..
rm -rf strainscope                # Windows PowerShell: Remove-Item -Recurse -Force strainscope
```

That removes the code and documents, `.venv/` (the Python toolbox), `renv/library/` (the links to the R packages in renv's cache), `data/` (the database, the real data, your datasets, the MCP call log, the accessibility report), `.env` and `.streamlit/secrets.toml` (your keys, if you made them) and the hook setting.

---

## 3. Online (only if you published it)

Each of these is public until you remove it, and each has its own button.

1. **The online copy.** At [share.streamlit.io](https://share.streamlit.io), click the three-dot menu next to the app, then **Delete**, type the confirmation it asks for and click **Delete** again. The app's address stops working, and with it go any visitors' datasets still on the host (they're deleted an hour after their last use anyway); the GitHub repository isn't touched.
2. **The interactive figures (GitHub Pages).** On the repository's page: **Settings**, then **Pages**; next to *Your site is live at*, click the three-dot menu and choose **Unpublish site**.
3. **The repository itself.** Only if the public copy should go too: **Settings**, then at the bottom of the *General* page, in the *Danger Zone*, **Delete this repository**. GitHub asks you to confirm and to type the repository's full name (`<your user name>/strainscope`). This also removes its releases, its Pages site and its issues; forks other people made stay theirs. With the folder (part 2) and the repository both gone, no copy is left, though GitHub can restore a deleted repository for 90 days (your profile's **Settings**, **Repositories**, **Deleted repositories**).
4. **Keys at the providers.** An NCBI key ([`docs/02c-more-real-sources.md`](02c-more-real-sources.md)) or a hosted language model's key ([`docs/LANGUAGE_MODEL.md`](LANGUAGE_MODEL.md)) still works after the folder is gone. Delete each one on the page where you created it.

---

## 4. The tools you installed in setup

Python, Git, R, VS Code, and (if you used them) Docker Desktop or Podman, Node.js and Ollama were installed for the whole computer in [`docs/01-setup.md`](01-setup.md) and the optional steps. Other projects may use them. Remove one only if nothing else needs it, the way your system removes any program (macOS: drag it from *Applications* to the Trash; Windows 11: *Settings*, *Apps*, *Installed apps*, or on Windows 10 *Apps & features*; RHEL 8: `sudo dnf remove` and the package name).

---

## 5. Check that it's gone

```bash
ls ~/projects/strainscope         # Windows PowerShell: Test-Path $HOME\projects\strainscope
```

**You should see** `No such file or directory` (PowerShell: `False`). Use the path where your folder was, if it wasn't `~/projects/strainscope`. In Claude Desktop, *Manage connectors* no longer lists strainscope; `claude mcp list` doesn't show it; `docker images strainscope` shows no image.

## Coming back later

Everything can be rebuilt from GitHub: the [Handbook](HANDBOOK.md#only-want-to-use-the-app) shows the six commands that bring the app back, and `python src/strainscope/pipeline.py` rebuilds every result ([`docs/09-packaging.md`](09-packaging.md)).
