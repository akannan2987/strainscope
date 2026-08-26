# 01 · Setup Runbook — From a Blank Laptop to a Real Repository

[← Architecture](00-architecture.md) · [All docs in order](../README.md#the-tutorial-in-order) · [Glossary](GLOSSARY.md)

**Prerequisites:** a computer (Windows, macOS, or Linux), an internet connection, and about 60–90 minutes. No prior programming setup is assumed. If you have *nothing* installed, you are in exactly the right place.
**Learning goal:** by the end you will have every tool StrainScope needs, you'll understand *why* each one exists, and you'll have a real, version-controlled project pushed to GitHub with a `master` / `beta` / `develop` branch structure — ready to start building.
**Checkpoint (what "done" looks like):** running `python --version`, `git --version`, and `code --version` all print version numbers; your project folder exists with a virtual environment; and your empty repo is visible on GitHub with three branches. Every step below tells you the exact output to expect so you can confirm as you go.

> **How to read this page.** Do one numbered step at a time. After each command, I show you what you should see. If you see something different, check the **"If it goes wrong"** note under that step before moving on. Never paste two commands at once until you're comfortable — one action, one result, one check.

---

## Part A — What we're installing, and why (read first, 3 minutes)

We install five things. Here's the plain-language reason for each, so nothing feels like a mystery incantation:

1. **Python** — the programming language the project is mostly written in. This is the engine.
2. **VS Code** — a free text editor built for code (a "word processor for programs"). This is where you'll read and write files.
3. **Git** — a "save-game system" for your code: it snapshots your work so you can go back in time, and it's how your project gets to GitHub. 
4. **A GitHub account** — the online home where your project lives publicly and where others can see and clone it.
5. **R** *(needed later, at the integration phase)* — a second language used for one specialised step. You can install it now or when you reach that phase; I'll show you now and remind you later.

We'll also create a **virtual environment** (explained in Part F) — think of it as a clean, sealed toolbox that belongs to *this* project alone, so its tools never clash with anything else on your machine.

> **This project is cross-platform by design.** Everything here runs the same on **Windows**, **macOS**, and **Linux** (including enterprise **RHEL 8** / Rocky / Alma servers). Where a command differs by operating system, you'll see clearly-labelled tabs for each — do the one that matches your machine and ignore the rest. The two big Linux families you'll see are **Debian/Ubuntu** (which install software with a tool called `apt`) and **RHEL 8 / Rocky / Alma / Fedora** (which use a tool called `dnf`). Everyday analogy: `apt` and `dnf` are two different app stores that install the same apps — you just walk into whichever one your system ships with.
>
> **One-time setup, easy repeats.** Installing the tools below happens **once** per machine. After that, day-to-day work — editing code, committing, redeploying — is a handful of short commands you'll quickly memorise. The heavy lifting is front-loaded on purpose.

---

## Part B — Install Python

Python is the engine. We'll install a recent, stable version (3.12). Pick your operating system.

### Windows

1. Open your web browser and go to `https://www.python.org/downloads/`.
2. Click the yellow **"Download Python 3.12.x"** button (the exact last number doesn't matter, as long as it starts with 3.12).
3. Open the downloaded installer. **Before clicking Install, tick the box that says "Add python.exe to PATH"** at the bottom. This one checkbox saves you hours of pain later — it tells Windows where Python lives.
4. Click **"Install Now"** and wait for it to finish, then click **Close**.
5. Open a fresh terminal: press the Windows key, type `powershell`, and press Enter.
6. Type this and press Enter:
   ```powershell
   python --version
   ```
   **Expected output:**
   ```
   Python 3.12.x
   ```

**If it goes wrong:** if you see `Python was not found` or it opens the Microsoft Store, the PATH box wasn't ticked. Re-run the installer, choose **Modify**, ensure "Add to PATH" is on, finish, then **close and reopen** PowerShell and try again. (You must reopen the terminal for PATH changes to take effect.)

### macOS

1. Install Homebrew (a "tool that installs other tools" for the Mac). Open the **Terminal** app (press ⌘+Space, type `Terminal`, Enter) and paste:
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```
   Follow the prompts (it may ask for your password — typing shows nothing, that's normal). When it finishes, it may print two lines starting with `echo` to "add Homebrew to your PATH" — copy, paste, and run those if shown.
2. Install Python:
   ```bash
   brew install python@3.12
   ```
3. Verify:
   ```bash
   python3 --version
   ```
   **Expected output:**
   ```
   Python 3.12.x
   ```

> **Note on `python` vs `python3`:** on macOS/Linux, the command is usually `python3`. Everywhere this guide says `python`, use `python3` if `python` alone gives "command not found."

**If it goes wrong:** if `brew` isn't found after installing, close and reopen Terminal. If it still fails, run `echo $PATH` and confirm it contains `/opt/homebrew/bin` (Apple Silicon) or `/usr/local/bin` (Intel); if not, re-run the two `echo ...` lines Homebrew printed.

### Linux — Debian / Ubuntu (uses `apt`)

1. Open a terminal and run:
   ```bash
   sudo apt update && sudo apt install -y python3 python3-venv python3-pip
   ```
   (`sudo` means "do this as administrator"; it may ask for your password — typing shows nothing, that's normal.)
2. Verify:
   ```bash
   python3 --version
   ```
   **Expected output:**
   ```
   Python 3.12.x
   ```
   (An older 3.x is fine to start, but 3.11+ is recommended.)

### Linux — RHEL 8 / Rocky / Alma / Fedora (uses `dnf`)

RHEL 8 and its relatives ship with an old system Python (3.6) that other system tools depend on — we must **not** disturb it. Instead we install a modern Python *alongside* it and call that one by name. This is the safe, standard practice on enterprise Linux.

1. Install a modern Python (try 3.12; if your VM's repositories don't have it, 3.11 works just as well):
   ```bash
   sudo dnf install -y python3.12 python3.12-pip
   ```
   If that reports "No match for argument", use 3.11 instead:
   ```bash
   sudo dnf install -y python3.11 python3.11-pip
   ```
2. Verify by calling the version explicitly (on RHEL, plain `python3` may still be the old 3.6 — so we say `python3.12`):
   ```bash
   python3.12 --version
   ```
   **Expected output:**
   ```
   Python 3.12.x
   ```
   (If you installed 3.11, use `python3.11` everywhere this guide later says `python`.)

> **Why call it `python3.12` and not just `python`?** On enterprise Linux, several built-in system utilities are written for the old Python 3.6, so the generic `python3` name is deliberately left pointing at 3.6 to avoid breaking them. By calling `python3.12` explicitly, we get our modern Python without touching anything the operating system relies on. Everyday analogy: it's like keeping the building's original master key untouched and carrying your own clearly-labelled key for your own office.

> **Corporate RHEL VM note.** On a managed RHEL VM you may not have `sudo` rights, or the software repositories may be restricted. If `dnf install` is blocked, that's an IT-permissions matter, not a mistake on your part — ask whoever administers the VM to install `python3.12` (and later `git` and `R`), or request temporary install rights. Everything after installation needs no special permissions.

---

## Part C — Install VS Code (your editor)

VS Code is where you'll open, read, and edit the project files.

1. Go to `https://code.visualstudio.com/` and download the version for your operating system. Install it (accept the defaults).
2. Open VS Code once so it finishes setting up.
3. Install the **Python extension**: click the squares icon on the left sidebar (Extensions), type `Python` in the search box, and click **Install** on the one published by Microsoft.
4. *(macOS only, optional but handy)* Open the Command Palette with ⌘+Shift+P, type `Shell Command: Install 'code' command in PATH`, and select it. Now you can open VS Code from the terminal by typing `code .`.
5. Verify from a terminal:
   ```bash
   code --version
   ```
   **Expected output:** three lines — a version number, a long commit hash, and a CPU architecture. Any output here means success.

**If it goes wrong (Windows/Linux):** if `code` isn't recognised, you can still use VS Code normally by opening it from the Start menu / applications; the `code` command is a convenience, not a requirement.

> **On a headless Linux server (a RHEL 8 VM with no desktop)** there's no graphical VS Code to install. You have two good options, and the project works fully with either:
> - **Edit remotely (recommended):** install VS Code on your *own* laptop, add its free **Remote - SSH** extension, and connect to the VM. You then edit the files on the server as if they were local — same comfortable editor, code stays on the VM. Everyday analogy: like using a remote-desktop to drive another computer, but just for files.
> - **Edit in the terminal:** use a built-in text editor such as `nano` (beginner-friendly) or `vim`. Nothing in this project requires a graphical editor — every step is command-line driven.

---

## Part D — Install Git and tell it who you are

Git is the save-game system. It also needs to know your name and email so each snapshot ("commit") is signed.

1. Install Git:
   - **Windows:** download from `https://git-scm.com/download/win`; run the installer and accept all the defaults (they're sensible).
   - **macOS:** `brew install git`
   - **Linux — Debian/Ubuntu:** `sudo apt install -y git`
   - **Linux — RHEL 8 / Rocky / Alma / Fedora:** `sudo dnf install -y git`
2. Verify:
   ```bash
   git --version
   ```
   **Expected output:**
   ```
   git version 2.x.x
   ```
3. Set your identity (use the same email you'll use for GitHub):
   ```bash
   git config --global user.name "Your Name"
   git config --global user.email "you@example.com"
   ```
   This prints nothing — silence means success.
4. Tell Git your preferred *default* branch name is `master` (so new repos start on `master`, matching our workflow):
   ```bash
   git config --global init.defaultBranch master
   ```
5. Confirm your settings:
   ```bash
   git config --global --list
   ```
   **Expected output** includes lines like:
   ```
   user.name=Your Name
   user.email=you@example.com
   init.defaultbranch=master
   ```

---

## Part E — Create your GitHub account and an *empty* repository

GitHub is the online home for the project.

1. Go to `https://github.com/` and sign up (or sign in). Use the same email as in Part D.
2. Click the **+** in the top-right corner → **New repository**.
3. Fill in:
   - **Repository name:** `strainscope`
   - **Description:** *A multi-omics workflow that ranks beneficial microbial strains and explains why.*
   - **Public** (so others can see and learn from it).
   - **Important:** leave **"Add a README file", "Add .gitignore", and "Choose a license" all UNticked.** We want a truly empty repository so our local `master` branch becomes the first thing pushed. (If GitHub creates a `main` branch for you, it complicates the `master` setup — an empty repo avoids that.)
4. Click **Create repository**.
5. On the next page, GitHub shows a URL like `https://github.com/YOUR-USERNAME/strainscope.git`. **Copy it** — you'll paste it in Part G. (Keep this browser tab open.)

> **Everyday analogy:** you've just reserved an empty plot of land online (the repo). In the next parts you'll build a house locally (your project folder) and then move it onto the plot (push).

---

## Part F — Create the project folder and a virtual environment

### What is a virtual environment, and why does it matter?

When you install a Python package (a bundle of pre-written code), by default it goes into one shared pile for your whole computer. Two projects that need *different versions* of the same package will then fight. A **virtual environment** is a private, sealed toolbox for **one project** — its packages live inside the project folder and can't clash with anything else. It also means anyone who clones your repo can recreate the *exact* same toolbox, so "it works on my machine" becomes "it works on everyone's machine." Reproducibility is the entire point of this project, so this step is not optional.

**Everyday analogy:** a shared kitchen where everyone dumps ingredients in one cupboard leads to chaos; a virtual environment gives each recipe its own labelled box of exactly the right ingredients.

### Steps

1. Choose where your projects will live and create the folder. (Pick any location you like; here we use a `projects` folder in your home directory.)
   ```bash
   mkdir -p ~/projects/strainscope
   cd ~/projects/strainscope
   ```
   On **Windows PowerShell**, `~` also works; if it doesn't, use `mkdir $HOME\projects\strainscope` then `cd $HOME\projects\strainscope`.
2. Create the virtual environment (we'll name it `.venv`, the conventional name). Use the command that names the Python you installed:
   ```bash
   python -m venv .venv
   ```
   - On **macOS / Debian / Ubuntu**, if `python` isn't found, use `python3 -m venv .venv`.
   - On **RHEL 8 / Rocky / Alma**, use the version you installed: `python3.12 -m venv .venv` (or `python3.11 -m venv .venv`).

   This prints nothing and creates a hidden `.venv` folder.

   > **Good news:** once the environment is *activated* in the next step, the generic command `python` works inside it on every platform — the version differences only matter for this one creation step. Everyday analogy: you pick the right key to open the toolbox once; once it's open, all the tools inside are labelled the same way for everyone.
3. **Activate** it (this "steps into" the toolbox for your current terminal):
   - **Windows PowerShell:**
     ```powershell
     .\.venv\Scripts\Activate.ps1
     ```
     If you get a red error about "running scripts is disabled", run this once, then try again:
     ```powershell
     Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
     ```
   - **macOS / Linux:**
     ```bash
     source .venv/bin/activate
     ```
   **Expected result:** your terminal prompt now starts with `(.venv)`. That prefix means the toolbox is active.
4. Upgrade the installer tool inside the environment:
   ```bash
   python -m pip install --upgrade pip
   ```
   **Expected output:** a line ending in something like `Successfully installed pip-XX.x`.

> **To leave the environment** later, type `deactivate`. **To re-enter** it in a new terminal, `cd` into the project and run the activate command again. You must be inside `(.venv)` whenever you install packages or run the project.

**If it goes wrong:** if activation "worked" but `pip install` later installs things globally, you probably opened a new terminal and forgot to re-activate. Always check for the `(.venv)` prefix first.

---

## Part G — Lay down the folder structure and connect to GitHub

Now we create the project's skeleton and link it to the empty GitHub repo.

1. Make sure you're in the project folder with the environment active (`(.venv)` prefix, prompt in `~/projects/strainscope`).
2. Create the standard folders. This layout has a place for everything, which we'll explain in step 3:
   ```bash
   mkdir -p src/strainscope R artifacts app data/raw data/processed tests notebooks docs .streamlit
   ```
3. **Why this structure?** Each folder has one clear job, so a stranger (and future-you) can find anything instantly:
   - `src/strainscope/` — the reusable backend code (data generation, cleaning, models, graph).
   - `R/` — the one specialised R script (DIABLO integration).
   - `artifacts/` — small precomputed outputs the app reads (predictions, trained model).
   - `app/` — the Streamlit app (the frontend/website).
   - `data/raw/` and `data/processed/` — generated data before and after cleaning.
   - `tests/` — automated checks that prove the code works.
   - `notebooks/` — optional exploratory notebooks.
   - `docs/` — this tutorial (the docs you're reading).
   - `.streamlit/` — configuration for the app when deployed.
4. Create a few starter files:
   ```bash
   # A .gitignore tells Git which files to NEVER save (secrets, the huge .venv, caches).
   cat > .gitignore <<'EOF'
   # Python
   .venv/
   __pycache__/
   *.pyc

   # Secrets — never commit API keys
   .streamlit/secrets.toml
   .env
   .Renviron

   # R / renv — keep the lockfile (the receipt), ignore the built library.
   # (renv also writes its own .gitignore inside renv/ automatically.)
   renv/library/
   renv/local/
   renv/cellar/
   renv/lock/
   renv/python/
   renv/staging/

   # Data & artifacts that can be regenerated (we'll adjust this later per phase)
   data/raw/*
   data/processed/*
   !data/raw/.gitkeep
   !data/processed/.gitkeep

   # OS noise
   .DS_Store
   EOF

   # Keep empty data folders in Git with placeholder files
   touch data/raw/.gitkeep data/processed/.gitkeep

   # A minimal requirements file (the project's toolbox list). We'll grow it each phase.
   cat > requirements.txt <<'EOF'
   pandas
   numpy
   scikit-learn
   duckdb
   networkx
   streamlit
   plotly
   matplotlib
   faker
   pytest
   EOF

   # A tiny placeholder README so the repo isn't empty; we replace it with the real one later.
   cat > README.md <<'EOF'
   # StrainScope

   A multi-omics workflow that ranks beneficial microbial strains and explains why.
   Full documentation lives in the `docs/` folder — start with `docs/00-architecture.md`.
   EOF
   ```
   > **What is `.gitignore`?** A list of files Git should pretend it can't see. We ignore the giant `.venv` folder (anyone can rebuild it from `requirements.txt`) and, critically, any secrets file with API keys. Committing a secret to a public repo is the classic beginner mistake; this prevents it.
5. Install the starter packages into your environment:
   ```bash
   pip install -r requirements.txt
   ```
   **Expected output:** a lot of scrolling, ending in `Successfully installed pandas-... numpy-... scikit-learn-...` and the rest. This can take a couple of minutes the first time.
6. Verify a package imports correctly:
   ```bash
   python -c "import pandas, sklearn, duckdb, networkx, streamlit; print('all good')"
   ```
   **Expected output:**
   ```
   all good
   ```

**If it goes wrong:** if an install fails with a compiler error, make sure you're on Python 3.11 or 3.12 (very new or very old Python sometimes lacks prebuilt packages). Check with `python --version`. Re-running `pip install -r requirements.txt` after a network hiccup is safe.

---

## Part H — Initialise Git and push with the `master` / `beta` / `develop` workflow

This is the branch model you'll use for the whole project. First, the plain-language version of *why three branches*:

- **`master`** — the "official, stable" version. The clean copy you're proud to show.
- **`beta`** — a "release candidate" copy: stable enough to preview, one notch below master's caution.
- **`develop`** — your **working** branch. This is where you actually make changes day to day.

The daily rhythm is: **work on `develop`, then push `develop` up to all three remote branches at once** so they stay in lock-step. You'll see the single command that does that below.

> **What is a "branch"?** A parallel copy of your project where you can make changes without disturbing the others. **"Local"** means on your laptop; **"origin"** means the copy on GitHub. So "push" = "send my local snapshots up to origin (GitHub)."

### Steps

1. Turn your folder into a Git repository (starting on `master`, per your global setting):
   ```bash
   git init
   ```
   **Expected output:**
   ```
   Initialized empty Git repository in .../strainscope/.git/
   ```
   Confirm you're on `master`:
   ```bash
   git branch --show-current
   ```
   **Expected output:** `master` (if it shows `main`, run `git branch -m master` to rename it).
2. Stage and commit everything (your first snapshot):
   ```bash
   git add .
   git commit -m "chore: initialise project structure, docs, and toolbox"
   ```
   **Expected output:** a summary line like `... files changed, ... insertions(+)`.
3. Connect your local repo to the empty GitHub repo (paste the URL you copied in Part E):
   ```bash
   git remote add origin https://github.com/YOUR-USERNAME/strainscope.git
   ```
   Verify:
   ```bash
   git remote -v
   ```
   **Expected output:** two lines showing `origin` with your URL (fetch and push).
4. Create the other two branches from `master`:
   ```bash
   git branch beta
   git branch develop
   ```
   (These print nothing. `git branch` on its own now lists all three, with `*` next to `master`.)
5. Save the **`check-public-safe.sh`** script (provided with this project) into the **root** of your repo, and make it runnable — this is the pre-push safety gate, explained fully in the next section. Then run it once before your very first push:
   ```bash
   chmod +x check-public-safe.sh    # macOS/Linux; on Windows use: bash check-public-safe.sh
   ./check-public-safe.sh
   ```
   **Expected output:** ✓ ticks ending in `✓ SAFE TO PUSH to the public repository`. (For this first, essentially-empty project there's nothing sensitive yet — but running it now builds the habit and confirms the script works.) Then stage and commit it with the rest:
   ```bash
   git add -A && git commit -m "chore: add pre-push public-safety gate"
   ```
6. Push all three branches to GitHub for the first time. The first push of each branch needs `-u` (which links local and remote so future pushes are shorter):
   ```bash
   git push -u origin master
   git push -u origin beta
   git push -u origin develop
   ```
   **Expected output:** for each, several lines ending in something like `* [new branch]      master -> master`. GitHub may open a browser window the first time to authorise; approve it.
7. On GitHub, refresh your repo page. You should now see your files, and a branch dropdown listing **master, beta, develop**. 
8. *(Recommended)* Set `master` as the **default branch** on GitHub: repo **Settings → Branches → Default branch → switch to `master`**. This makes `master` the first thing visitors see.

### Your everyday workflow from now on

Whenever you finish a piece of work, you'll be on `develop`, and you'll run these three commands:

```bash
# 0. Safety first — run the checks BEFORE staging anything.
pytest -q                     # once tests exist (from Phase 4 on); skip earlier
./check-public-safe.sh        # must print "SAFE TO PUSH" before you continue

# 1. Then the commit + push ritual:
git switch develop
git add -A
git commit -m "a short message describing what you did"
git push origin develop develop:beta develop:master

# 2. Bring your LOCAL master in step with the remote master you just updated:
git switch master
git pull --ff-only origin master
git switch develop
```

The two safety commands come **first**, on purpose: there's no point staging or committing anything until you know the tests pass and nothing sensitive is about to be published. If `./check-public-safe.sh` prints **NOT SAFE TO PUSH**, stop and fix the flagged items before going any further. (`pytest -q` has nothing to run until Phase 4 adds the first tests, so you can omit it before then — it does no harm either way.)

**What each line does, in plain terms:**

- `git switch develop` — make sure you're on the working branch before you touch anything. (Everyday analogy: sit down at your own desk, not someone else's.)
- `git add -A` — stage **all** your changes (new, edited, and deleted files) so Git knows what to include in the snapshot. `-A` = "everything".
- `git commit -m "..."` — take the snapshot, with a short note describing what changed.
- `git push origin develop develop:beta develop:master` — send your local `develop` up to the remote `develop`, and *also* fast-forward remote `beta` and `master` to match it — all in one command. Read `develop:beta` as "send my local develop to the remote branch called beta." One line keeps all three copies on GitHub in step with your latest work.
- `git switch master` → `git pull --ff-only origin master` → `git switch develop` — because the push just moved remote `master` forward, your *local* `master` is now behind. This trio hops onto local `master`, pulls the update, and hops back to `develop` so you're ready to keep working. `--ff-only` means "only update if it can be done cleanly, with no messy merge — otherwise stop and tell me." (Everyday analogy: after mailing three copies of a document, you update the copy in your own drawer so it matches what you sent.)

> **Optional — tags.** When you finish something worth marking as a version (like `v0.1.0`), you create a tag and push it with `--tags`: `git tag v0.1.0` then `git push origin develop develop:beta develop:master --tags`. You only add `--tags` when you've actually created a new tag; day-to-day commits don't need it.

> **Make sure you're on `develop` before working.** Check with `git branch --show-current`. If it doesn't say `develop`, switch with `git switch develop`.

**If it goes wrong:** if a push is *rejected* with a message about "non-fast-forward", it means the remote has a change your local branch doesn't. For a solo project this is rare; if it happens, run `git pull origin develop` to bring the changes down, resolve any conflicts your editor highlights, then push again. If `git pull --ff-only origin master` refuses because it "cannot fast-forward", it means local `master` has drifted; the safe fix is `git switch master && git reset --hard origin/master && git switch develop` (this makes local `master` an exact copy of the remote — safe here because you never edit `master` directly, only ever on `develop`).

> **This same ritual — safety checks first, then commit, push to all three, sync master — is how every phase in this project ends.** Each phase guide repeats the exact commands so it becomes second nature.

### The pre-push safety gate: `check-public-safe.sh`

Because this repository is **public**, a single leaked secret — most likely an API key once we add the AI features — would be visible to the whole world the moment you push. `.gitignore` prevents *accidental* staging, but it can't catch a file you force-add, or a key you paste into a script or a doc by mistake. So the project ships a small script, `check-public-safe.sh`, that you run **before every push**. It inspects what Git actually tracks and refuses to give the all-clear if anything sensitive would be published.

> **Everyday analogy:** `.gitignore` is the lock on your front door; `check-public-safe.sh` is the guard who checks your bag on the way out. The lock stops the obvious mistakes; the guard catches the one that slipped through. You want both.

What it checks, in plain terms:
1. **Secret / environment / data paths** aren't tracked (`.venv`, `.streamlit/secrets.toml`, `.env`, `.Renviron`, real data under `data/`, …).
2. **Sensitive file types** aren't tracked anywhere (`.key`, `.pem`, `.env`, database files like `.duckdb`/`.sqlite`, …). It deliberately allows the small `.csv` and `.pkl` files we *do* publish as artifacts.
3. **Credential-shaped strings** in any tracked file — it matches the actual *formats* of real keys (OpenAI `sk-…`, GitHub `ghp_…`, AWS `AKIA…`, private-key blocks), so ordinary docs that merely mention "API key" don't trip it.
4. **Hard-coded local machine paths** (like a real home-directory path under `/Users/…`, `/home/…`, or `C:\Users\…`) that would both leak your machine and break reproducibility for anyone who clones the repo. Use `~` or a relative path instead.
5. **Large tracked files** (over 5 MB) — a warning, since data and models are meant to stay small or be regenerated.
6. **Personal attribution** — lists where your name/handle appears (README, LICENSE) so you can confirm it's the intended public credit, not a new leak.

It prints **`✓ SAFE TO PUSH`** (and exits cleanly) or **`✗ NOT SAFE TO PUSH`** with the exact lines to fix.

**Set it up once:**

1. Save the `check-public-safe.sh` file into the **root** of your project (the same folder as `README.md`).
2. Make it runnable (macOS / Linux):
   ```bash
   chmod +x check-public-safe.sh
   ```
   (`chmod +x` means "mark this file as a program I'm allowed to run" — you only do it once.)
3. Run it any time to check:
   ```bash
   ./check-public-safe.sh
   ```
   **Expected output on a clean project:** a list of ✓ ticks ending in `✓ SAFE TO PUSH to the public repository`.

> **On Windows**, run it through **Git Bash** (the terminal that installs alongside Git for Windows — you already have it from Part D). Open Git Bash in the project folder and run `bash check-public-safe.sh` (no `chmod` needed there). It works the same way; only the launch command differs.

> **Tip:** make the script *yours* — near the bottom it lists your GitHub handle so it can tell "intended attribution" apart from a real leak. If you fork or rename, update that one line to your own details.

**If it goes wrong:** if the gate flags something you believe is safe, read the flagged line first — most "false alarms" are real (a placeholder key that looks too much like a real one, or an example path that shouldn't ship). If it's genuinely intended, the honest fix is to make the content unmistakably non-secret (use an obvious placeholder like `sk-REPLACE_ME`) rather than to weaken the check.

---

## Part I — Install R (needed at the integration phase)

You can do this now, or skip it and come back when you reach the integration doc — I'll remind you there. R is a second language used for one specialised, high-value step (the DIABLO multi-omics integration).

1. Install R:
   - **Windows/macOS:** download the installer from `https://cran.r-project.org/` and run it with defaults. (On macOS you can instead run `brew install r`.)
   - **Linux — Debian/Ubuntu:** `sudo apt install -y r-base`
   - **Linux — RHEL 8 / Rocky / Alma:** R lives in the community **EPEL** repository, which in turn needs the **CodeReady Builder** (CRB / PowerTools) repository enabled. Run these three commands in order:
     ```bash
     # 1. Enable the CodeReady Builder repo (R depends on packages here).
     #    On true RHEL:
     sudo subscription-manager repos --enable "codeready-builder-for-rhel-8-$(arch)-rpms"
     #    On Rocky/Alma instead, use this line rather than the one above:
     #    sudo dnf config-manager --set-enabled powertools

     # 2. Add the EPEL repository (where the R package is published).
     sudo dnf install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-8.noarch.rpm

     # 3. Install R itself.
     sudo dnf install -y R
     ```
     > **What just happened, plainly:** enterprise Linux keeps "extra" software in optional add-on catalogues you switch on when needed. Step 1 unlocks a catalogue of building-block libraries R relies on; step 2 adds the catalogue that actually contains R; step 3 installs it. Everyday analogy: to buy a specialist ingredient you first get a membership to two extra stores, then do the shopping. You only do this once.
2. Verify:
   ```bash
   R --version
   ```
   **Expected output:** a few lines starting with `R version 4.x.x`.
3. Install the mixOmics package (this is what provides DIABLO). Open R by typing `R` in your terminal, then paste:
   ```r
   install.packages("BiocManager")
   BiocManager::install("mixOmics")
   ```
   When it asks whether to update other packages, typing `n` (no) is usually fine for a first install. This download is sizeable; let it finish.
4. Confirm it loaded, still inside R:
   ```r
   library(mixOmics)
   ```
   **Expected result:** some startup messages and no red `Error`. Then type `q()` and press Enter, and `n` when asked to save the workspace, to leave R.

**If it goes wrong:** mixOmics has many dependencies; if one fails, R usually names it — re-running `BiocManager::install("mixOmics")` often completes the rest. If R names a missing *system* library, install the development version of it:
- **Debian/Ubuntu:** `sudo apt install -y libcurl4-openssl-dev libssl-dev libxml2-dev`
- **RHEL 8 / Rocky / Alma:** `sudo dnf install -y libcurl-devel openssl-devel libxml2-devel`

then retry. (These are common building blocks R packages compile against — think of them as the power tools mixOmics borrows while assembling itself.) Because R is only needed for one offline step whose results we save as a small file, a temporary R hiccup never blocks the rest of the project.

### Lock the R toolbox with `renv` (R's virtual environment)

Just as Python has a virtual environment (`.venv`) plus a `requirements.txt` shopping list, R has **`renv`** — its own sealed, per-project toolbox that records the *exact* package versions this project used. Without it, the Python half of the project would be reproducible and the R half wouldn't, which is an inconsistency we don't want in a project whose whole point is that a stranger can rebuild it identically.

**Everyday analogy:** `renv` is the R-language twin of `.venv` + `requirements.txt` — a labelled box of exactly the right R ingredients that ships with the project, plus a receipt (`renv.lock`) listing every version so anyone can recreate the identical box.

Do this once, from your project folder (the one with the `(.venv)` prefix is fine — `renv` is about R, and lives happily alongside the Python environment):

1. Still needing R, install `renv` (from your terminal, launching R non-interactively):
   ```bash
   R -e 'install.packages("renv", repos="https://cloud.r-project.org")'
   ```
   **Expected output:** download messages ending with `* DONE (renv)`.
2. Initialise `renv` for this project. Because installing mixOmics from scratch into a fresh renv library is slow, we tell renv to reuse the packages you already installed in Part I rather than re-downloading them:
   ```bash
   R -e 'renv::init(bare = TRUE)'
   ```
   **Expected output:** messages ending with something like `renv activated -- please restart the R session`. This creates three things in your project: an `renv/` folder (the sealed R library), a `renv.lock` file (the receipt of versions), and an `.Rprofile` file (which auto-activates renv whenever R starts here).
3. Record mixOmics (and its dependencies) into the project's lockfile so the receipt is complete:
   ```bash
   R -e 'renv::record("mixOmics"); renv::snapshot()'
   ```
   If it asks you to confirm writing the lockfile, answer `y`. **Expected output:** `The lockfile has been updated.`
4. Confirm the receipt exists:
   ```bash
   ls renv.lock
   ```
   **Expected output:** `renv.lock`

> **What each new file is for:**
> - `renv.lock` — the receipt of exact R package versions (this **is** committed to Git; it's how others rebuild your R toolbox).
> - `renv/` — the sealed R library itself (mostly **not** committed — like `.venv`, it's rebuildable from the lockfile; renv adds its own `.gitignore` inside this folder automatically).
> - `.Rprofile` — a small file that switches renv on automatically every time R runs in this project.
>
> **Later, on any machine**, a person restores your exact R setup with one command from inside the project: `R -e 'renv::restore()'`. That's the R equivalent of `pip install -r requirements.txt`.

**If it goes wrong:** if `renv::init()` warns that it found no packages to record, that's fine at this stage — you'll snapshot again after the integration phase adds real R code. If R can't reach the internet through a proxy at work, `renv` respects the same proxy settings as base R; setting the `https_proxy` environment variable before launching R usually resolves it.

---

## Part J — Final checkpoint

Run these four checks. All four passing means your environment is fully ready.

1. Python works:
   ```bash
   python --version
   ```
   → `Python 3.12.x`
2. Git works and knows you:
   ```bash
   git --version && git config --global user.name
   ```
   → a git version, then your name.
3. The environment and packages are installed (must show `(.venv)` in your prompt):
   ```bash
   python -c "import pandas, sklearn, duckdb, networkx, streamlit; print('env OK')"
   ```
   → `env OK`
4. GitHub has your three branches: refresh the repo page and see **master / beta / develop** in the branch dropdown.
5. *(If you did Part I)* the R toolbox is locked:
   ```bash
   ls renv.lock
   ```
   → `renv.lock`

If all four (or five) pass — congratulations, the hardest part for most beginners (setup) is behind you. You have a real, reproducible, version-controlled project on the internet, with nothing built yet but every foundation in place.

---

## Concepts you just learned (glossary for this page)

- **Python / R** — programming languages; Python is the engine, R handles one specialist step.
- **VS Code** — the editor where you read and write code.
- **Terminal / PowerShell** — the text window where you type commands.
- **PATH** — the list of places your computer looks for programs; "adding to PATH" makes a tool runnable by name.
- **Git** — snapshots your code so you can go back in time and share it.
- **Repository (repo)** — the project as Git tracks it; lives locally and on GitHub.
- **Branch** — a parallel copy of the project (`master`, `beta`, `develop`).
- **Local vs origin** — your laptop's copy vs GitHub's copy.
- **Commit** — one saved snapshot, with a message describing it.
- **Push** — send your local snapshots up to GitHub.
- **Virtual environment (`.venv`)** — a sealed, per-project toolbox of Python packages.
- **`requirements.txt`** — the shopping list of Python packages that recreates the toolbox.
- **`renv`** — R's equivalent of a virtual environment: a sealed, per-project R toolbox.
- **`renv.lock`** — the receipt of exact R package versions; the R twin of `requirements.txt`.
- **`.gitignore`** — the list of files Git should never save (secrets, the giant `.venv`).
- **Package** — a reusable bundle of pre-written code you install and import.

---

## What's next

Next is **`02-data-generation.md`** — Box 1 of the architecture. You'll write the generator that invents a realistic, biologically-grounded library of microbial strains with three omics layers and a performance score, learn what a "random seed" is and why reproducibility depends on it, and end the phase with real data on disk and your first meaningful commit pushed to all three branches.
