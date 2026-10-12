# Contributing to StrainScope

Thanks for wanting to help. This page says how a change travels from an idea to a release, and what every change has to pass. It's written for someone who has never contributed to a project on GitHub, so it explains the words as it goes.

If you only want to *use* StrainScope, the [Handbook](docs/HANDBOOK.md) is the place to start.

## Ways to help

| You'd like to... | Do this |
|---|---|
| report something that doesn't work | open an issue and choose **Something doesn't work** (a short form) |
| suggest an idea | open an issue and choose **An idea or a wish**; the [roadmap](docs/ROADMAP.md) shows what's planned already |
| say an assistant's answer missed | press *Not what you needed? Suggest a fix* under the answer in the app; it opens an issue with your question filled in |
| fix a guide, a typo or some code | send a pull request (below) |
| report a security problem | privately, never in a public issue: see [`SECURITY.md`](SECURITY.md) |

An **issue** is a public note on GitHub's *Issues* tab that anyone can read and answer. A **pull request** is a proposed change: you show the exact lines you'd change, the automatic tests run on it, and the maintainer decides whether to take it in.

## The branches

Three branches live on GitHub, and on a normal day all three point at the same commit:

| Branch | What it holds |
|---|---|
| `master` | the released state. The online copy and the GitHub Pages site are built from it, and the version tags (v0.1.0 ... v1.0.0) sit on it. |
| `beta` | the state about to be released; the same commit as `master` after every push in this workflow |
| `develop` | where all work happens |

I always work on a local `develop` and push it to all three at once ([`docs/01-setup.md` Part H](docs/01-setup.md#part-h-initialise-git-and-push-with-the-master--beta--develop-workflow) explains why):

```bash
git switch develop
git add -A
git commit -m "<what changed>"
git push origin develop develop:beta develop:master

## add --tags to the push only after making a release tag (How a release happens, below)

## then switch back to local master and pull in the remote changes
git switch master
git pull --ff-only origin master
git switch develop
```

## Sending a pull request

1. **Fork** the repository: the *Fork* button on GitHub makes your own copy under your account. On the form, untick *Copy the master branch only* if it's ticked, so your copy has `develop` too. Then clone your fork: `git clone https://github.com/<your user name>/strainscope.git`, and `cd strainscope`.
2. Set it up once with the [setup guide](docs/01-setup.md), then build the database: `python src/strainscope/pipeline.py database`.
3. Make a branch from `develop` for your change: `git switch develop`, then `git switch -c fix-typo-in-phase-4`.
4. Make the change, and run the checks below.
5. Commit, push the branch to your fork (`git push origin fix-typo-in-phase-4`), and open a pull request **into `develop`**: GitHub offers a *Compare & pull request* button for the branch you just pushed. It fills in a short checklist; tick what you did.
6. The automatic tests ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) run on Windows, macOS, Linux and RHEL 8. A green tick means they all passed. For someone's first pull request, GitHub waits for the maintainer to approve the run before it starts.

## What every change must pass

```bash
pytest -q                     # every test; skips are named with their reason by pytest -q -rs
./check-public-safe.sh        # must end with SAFE TO PUSH  (Windows: bash check-public-safe.sh in Git Bash)
```

and, for these kinds of change:

- **Code in `src/`, `app/`, `tests/`, `figures/` or `tools/`:** `python -m pyflakes src app tests figures tools` prints nothing (install it once with `python -m pip install pyflakes`).
- **A result could change** (anything in Phases 1 to 5): `python src/strainscope/pipeline.py`, then `python src/strainscope/pipeline.py compare`. Then put the committed results back before you commit (`git restore artifacts/`, then `python src/strainscope/pipeline.py database`), unless the change is meant to move a number; in that case, say which and why in the pull request.
- **Any document or docstring:** `python src/strainscope/ask.py --golden` still passes. Ask StrainScope searches every document, so a new paragraph that repeats a golden question's words can take that question's best match ([`docs/07b-docs-assistant.md` §7](docs/07b-docs-assistant.md#7-step-3-the-golden-questions)).
- **The app:** `python -m streamlit run app/streamlit_app.py` and click through the page you changed. `tests/test_app.py` clicks through every page as well.

## How the documents are written

The documents are a tutorial for someone with no background in biology, statistics or programming, so a few habits hold everywhere:

- **The [Handbook](docs/HANDBOOK.md) is updated in the same change** as the work it describes, and so is [`CHANGELOG.md`](CHANGELOG.md) (under *[Unreleased]*). If the Handbook falls behind the code, that's a bug.
- **Every file is named by its path from the project folder** (`src/strainscope/harmonize.py`, never `harmonize.py`), and every document a page mentions is linked.
- **Every term is explained the first time it appears**, with an everyday example, and lands in the [Glossary](docs/GLOSSARY.md).
- **"You should see" blocks show the real output**, line for line, from a real run.
- **Commands, commit messages and tag messages use plain keyboard characters only** (no long dashes or curly quotes, which terminals mangle; [why](docs/01-setup.md#copy-commands-safely-plain-keyboard-characters-only)).
- **Every command works on Windows, macOS and RHEL 8**; where they differ, both forms are shown.
- **The data is simulated, and every document that shows a result says so.**

## How a release happens

1. Changes collect under *[Unreleased]* in [`CHANGELOG.md`](CHANGELOG.md).
2. When they add up to a new usable level, *[Unreleased]* becomes the new version with the day's date, and [`CITATION.cff`](CITATION.cff) gets the same version and date (`tests/test_deploy.py` checks they agree).
3. The commit is pushed, and the tag is made only after the automatic tests have passed on that exact commit ([`docs/09-packaging.md`](docs/09-packaging.md) walks through it).

Version numbers follow *semantic versioning*: the first number changes when something you rely on stops working the old way, the second when something new arrives, the third for fixes ([the version tags](docs/ROADMAP.md#version-tags)).

## Be kind

Assume good intent, explain rather than correct, and remember that many readers here are learning. Questions are welcome; there's no such thing as a silly one in a project written for beginners.

## Licence

By contributing, you agree that your contribution is published under the project's [MIT licence](LICENSE).
