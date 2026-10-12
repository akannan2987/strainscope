# Switching on a language model (optional), at home and online

[← README](../README.md) · [Handbook](HANDBOOK.md) · [Phase 6b §8](07b-docs-assistant.md#8-step-4-optional-written-answers-from-a-model-on-your-own-computer) · [Phase 7 §10](08-deployment-ai.md#10-step-6-optional-a-language-model-for-the-three-assistants) · [Glossary](GLOSSARY.md) · [Roadmap](ROADMAP.md)

**Prerequisites:** the project set up on your computer and the app running ([Handbook Stage 10](HANDBOOK.md#stage-10-phase-6-the-app)). For the online copy, an online copy of your own ([Phase 7 §9](08-deployment-ai.md#9-step-5-put-the-app-online-streamlit-community-cloud)).

Everything in StrainScope works without a language model. The three assistants find their answers by search and by rules, and they show you where every answer came from. A model, if you switch one on, adds one thing to each:

- **Ask StrainScope** writes a short answer above the passages it found, citing them.
- **Ask the graph** writes a short answer above the numbered facts, citing them, and may not add a number of its own.
- **Ask the data** writes a new SQL query when no tested recipe fits. The query passes five guards before it runs, and it's shown so you can check it.

*In plain words* (the Strain and Ranking pages) never uses a model. What each assistant may send to a model, and what it never sends, is the table in [Phase 7 §1](08-deployment-ai.md#what-a-model-may-see-and-what-it-never-sees). The short version: the question you typed, documentation passages, table and column names, a few example recipes and facts about concepts may go; a row of data, a strain's results, an upload or anything else on your computer never does.

This page collects every way to switch a model on and off in one place. The two guides linked above explain the ideas behind it.

---

## 1. Pick a setup

| Setup | The model runs on | Costs | What leaves your computer | Use it for |
|---|---|---|---|---|
| **A. Ollama, on your computer** | your computer | nothing | nothing | trying it out, and private work |
| **B. A hosted provider, at home** | the provider's computers | a free tier or a paid plan | the requests in the table of Phase 7 §1 | a computer too small or too slow for a local model |
| **C. A hosted provider, for an online copy** | the provider's computers | the same | the same, for every visitor | your online copy (this project's is [strainscope.streamlit.app](https://strainscope.streamlit.app)) |

A model on your laptop can't serve an online copy: the host can't reach your laptop. So an online copy needs setup C, and it's worth trying setup B at home first, with the same key and model.

## 2. The settings, and where they live

Five settings decide everything. They have the same names at home and online:

| Setting | What it says | Values |
|---|---|---|
| `STRAINSCOPE_ASK_BACKEND` | whether a model is used, and which kind | `none` (the default), `local` (Ollama on this computer) or `hosted` (a provider) |
| `STRAINSCOPE_ASK_URL` | where to send the request | for `local`, leave it out (`http://localhost:11434/v1` is used); for `hosted`, the provider's address |
| `STRAINSCOPE_ASK_MODEL` | which model | for `local`, leave it out (`llama3.2:3b` is used); for `hosted`, a name from the provider's list |
| `STRAINSCOPE_ASK_KEY` | the key for a hosted provider | only for `hosted`; treat it like a password |
| `STRAINSCOPE_AI_DAILY_LIMIT` | the most model requests per day | 200 on an online copy unless you set it; no limit at home |

**At home** they live in `.env`, the file in the project folder that Git never commits ([why](02c-more-real-sources.md#1-the-secrets-lesson-this-phases-big-idea)). To open it in VS Code, click `.env` in the Explorer sidebar on the left. Three rules: an empty value counts as not set; if a name appears twice, the later line wins; and a setting typed in the terminal (`export NAME=value`, PowerShell: `$env:NAME = "value"`) wins over the file until that terminal closes. **Online** they live in the host's Secrets box, written in TOML (`NAME = "value"`, with quotes).

The app reads them when it starts. **After changing them, restart the app** (Ctrl+C in its terminal, then start it again), or reboot the online copy.

---

## 3. Setup A: Ollama on your computer

This downloads about 2 GB and works best with 8 GB of memory or more.

1. **Install Ollama** (once per computer), from [ollama.com/download](https://ollama.com/download):
   - **macOS 14 (Sonoma) or newer:** download `Ollama.dmg`, open it and drag **Ollama** into **Applications**. Then start it from Applications. When it asks whether it may install the command-line tool (a link called `ollama` in `/usr/local/bin`), allow it. A small llama icon appears in the menu bar while it runs. To see your macOS version: `sw_vers -productVersion`. On an Intel Mac the model runs on the processor only, so answers are slower than on an Apple-chip Mac.
   - **Windows 10 (22H2) or newer:** run the installer from the download page. It adds the `ollama` command and keeps Ollama running in the background.
   - **Linux, including a RHEL 8 VM:** `curl -fsSL https://ollama.com/install.sh | sh`, then `sudo systemctl start ollama`.

2. **Open a new terminal window** (so it finds the new command), go to the project folder, switch on the project's toolbox, and get the model:

   ```bash
   cd ~/projects/strainscope                 # your project folder; Windows PowerShell: cd $HOME\projects\strainscope
   source .venv/bin/activate                 # Windows PowerShell: .\.venv\Scripts\Activate.ps1
   ollama -v
   ollama pull llama3.2:3b
   ```

   **You should see** `(.venv)` at the start of your prompt, a version number, then a download that ends with `success`.
   **If instead** you see `ollama: command not found` (PowerShell: `The term 'ollama' is not recognized`), see §8.

3. **Switch it on.** Add one line to `.env` (if you don't have a `.env` yet, the command creates it):

   ```bash
   echo 'STRAINSCOPE_ASK_BACKEND=local' >> .env           # Windows PowerShell: Add-Content .env 'STRAINSCOPE_ASK_BACKEND=local'
   ```

   If you used setup B before, also delete its `STRAINSCOPE_ASK_URL`, `STRAINSCOPE_ASK_MODEL` and `STRAINSCOPE_ASK_KEY` lines from `.env`: a URL or model name there would win over Ollama's defaults.

4. **Check it from the terminal:**

   ```bash
   python src/strainscope/service.py status
   ```

   **You should see** this line among the others:

   ```
     ✓ AI features (optional)   on, local: llama3.2:3b at http://localhost:11434/v1 (on this computer); 0 model request(s) today, no daily cap
   ```

   Then ask something:

   ```bash
   python src/strainscope/ask_graph.py "How does iturin suppress disease?"
   ```

   **You should see** a block called `Written answer (llama3.2:3b, from the facts below):` above the seven facts of [Phase 7 §7](08-deployment-ai.md#7-step-3-ask-the-graph). The wording comes from the model, so it differs from computer to computer; what stays the same is that it cites the facts as `[3]` or `[3][4]`. The first answer takes longest, because Ollama loads the model into memory.

5. **Restart the app**, if it's running, and continue with §6.

## 4. Setup B: a hosted provider at home

Any provider with an **OpenAI-compatible interface** works ([what that is](GLOSSARY.md#phase-6b-ask-strainscope-doc-07b)). Google's Gemini API has a free tier, so it's the example here. Free tiers, model names and terms change; look them up on the provider's pages when you set this up (the details below were current in October 2026).

1. **Get a key.** Sign in at [aistudio.google.com/apikey](https://aistudio.google.com/apikey) and press *Create API key*. Copy it into `.env` in step 3, and nowhere else: not into a file Git tracks, and not into a chat or an issue.
2. **Pick a model** on the [models page](https://ai.google.dev/gemini-api/docs/models). A *Flash-Lite* model is plenty; `gemini-3.5-flash-lite` is one.
3. **Add four lines to `.env`.** If you don't have a `.env` yet, make one from the template first: `cp .env.example .env` (PowerShell: `Copy-Item .env.example .env`). Then open it (§2) and add, at the end:

   ```
   STRAINSCOPE_ASK_BACKEND=hosted
   STRAINSCOPE_ASK_URL=https://generativelanguage.googleapis.com/v1beta/openai
   STRAINSCOPE_ASK_MODEL=gemini-3.5-flash-lite
   STRAINSCOPE_ASK_KEY=your-key
   ```

   with your key in place of `your-key`. Being the last lines, they win over any earlier line with the same name.
4. **Check it** with the two commands of §3 step 4 (in a terminal where `(.venv)` shows). The status line now starts `on, hosted: gemini-3.5-flash-lite at https://generativelanguage.googleapis.com/v1beta/openai (hosted)`, and the answer's block says `Written answer (gemini-3.5-flash-lite, from the facts below):`.

## 5. Setup C: an online copy

Do setup B at home first, so you know the key and the model name work.

1. Go to [share.streamlit.io](https://share.streamlit.io). Next to your app, open the **⋮** menu, then **Settings**, then **Secrets**.
2. Below the line that's already there (`STRAINSCOPE_MODE = "public"`), add the same four settings in TOML, with quotes:

   ```
   STRAINSCOPE_ASK_BACKEND = "hosted"
   STRAINSCOPE_ASK_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
   STRAINSCOPE_ASK_MODEL = "gemini-3.5-flash-lite"
   STRAINSCOPE_ASK_KEY = "your-key"
   ```

   Press **Save**. (Every line has to sit above any `[section]` heading; StrainScope doesn't use any.)
3. **Reboot the app**: the same **⋮** menu, then **Reboot**.
4. **Check it**: open **About this copy**. The *AI features* line says `on, hosted: gemini-3.5-flash-lite ...; 0 of 200 model requests used today (UTC)`.

Every visitor's model requests then go to the provider on your key, within the daily cap: after 200 in a day, the assistants answer by search alone until midnight (UTC). To change the number, add `STRAINSCOPE_AI_DAILY_LIMIT = "100"` (any whole number) to the Secrets box and reboot. Google's pricing page says that on the free tier, what you send may be used to improve its products. StrainScope sends only what Phase 7 §1 lists: the question typed, and text that is public in this repository anyway. For anything confidential, use a paid plan or a local model.

---

## 6. Using it in the app

With a model switched on, each Ask page shows a switch under the question box, on by default:

| Page | The switch | What you get |
|---|---|---|
| **Ask StrainScope** | *Also write a short answer (model name)* | a **Written answer** box above the passages, citing them as [1], [2], [3] |
| **Ask the graph** | *Also write a short answer (model name)* | a **Written answer** box above the route and the numbered facts |
| **Ask the data** | *When no recipe fits, let (model name) write a query* | for a question no recipe answers, *No recipe fitted, so (model name) wrote this query...*, the query and its table |

Turn a switch off to get the answer without a model for that page. What a model is asked stays narrow either way:

- On Ask StrainScope and Ask the graph, the model writes only when the search has already found the answer, and the passages or facts stay under what it writes.
- On Ask the data, a tested recipe that fits always runs without the model; the model is asked only when none fits.
- A question about a strain on Ask the graph is always answered by rules.

**About this copy** shows whether a model is on, and the footer of each Ask page says so too.

Read a written answer as a summary of what's under it. If the two disagree, the passages or facts win; if a model's query looks wrong, open it in the SQL console with the button under it and fix it there.

## 7. Switching it off

- **At home:** in `.env`, set every `STRAINSCOPE_ASK_BACKEND` line to `none` (or delete them all), then restart the app. If one is set in the terminal, clear it too: `unset STRAINSCOPE_ASK_BACKEND` (PowerShell: `Remove-Item Env:STRAINSCOPE_ASK_BACKEND`). To stop Ollama itself: quit it from the menu-bar icon (macOS) or the system tray (Windows), or `sudo systemctl stop ollama` (Linux).
- **Online:** delete the four `STRAINSCOPE_ASK_*` lines from the Secrets box, press **Save**, and reboot the app.
- **The key:** if you no longer need it, delete it on the same AI Studio page where you created it.

## 8. When something goes wrong

| What you see | What it means, and what to do |
|---|---|
| `ollama: command not found` (macOS or Linux) or `The term 'ollama' is not recognized` (Windows) | **macOS:** Ollama isn't installed, or it was never started (starting it is what adds the command). `ls /Applications \| grep -i ollama` shows whether it's there; if it is, start it with `open -a Ollama`, allow the command-line tool, and open a new terminal window; if not, install it (§3 step 1). **Windows:** close PowerShell and open a new window; if it still fails, install Ollama again from the download page. **Linux:** run the install command of §3 step 1 again and read its last lines. |
| *About this copy* still says *off* | The app wasn't restarted after the change, or the line went into `.env.example` instead of `.env`, or a setting typed in the terminal wins over the file: `echo $STRAINSCOPE_ASK_BACKEND` shows it (PowerShell: `$env:STRAINSCOPE_ASK_BACKEND`), and `unset STRAINSCOPE_ASK_BACKEND` clears it (PowerShell: `Remove-Item Env:STRAINSCOPE_ASK_BACKEND`). Online: the line is missing, misspelt or sits under a `[section]` heading in the Secrets box; fix it and reboot. |
| The model stays on after you switched it off | Another `STRAINSCOPE_ASK_BACKEND` line later in `.env`, or one set in the terminal, still says `local` or `hosted` (§7). |
| `Couldn't reach the model at http://localhost:11434/v1. Is Ollama running? (ollama -v)` | Ollama isn't running. Start it (macOS: from Applications; Windows: from the Start menu; Linux: `sudo systemctl start ollama`, or `ollama serve` in a second terminal). |
| `Couldn't reach the model at https://...` (a hosted provider) | The address is mistyped, or this computer can't reach the internet. Check `STRAINSCOPE_ASK_URL` against §4 step 3. |
| `Written answers need STRAINSCOPE_ASK_URL and STRAINSCOPE_ASK_MODEL` | `STRAINSCOPE_ASK_BACKEND=hosted` is set, but the address or the model name is missing (§4 step 3). |
| `The hosted backend needs STRAINSCOPE_ASK_KEY in your .env file` | The key line is missing or empty. |
| `The model at ... took longer than 120 seconds to answer.` | The computer is too slow for this model, for example a laptop without a graphics card. Try the smaller one: `ollama pull llama3.2:1b`, then add `STRAINSCOPE_ASK_MODEL=llama3.2:1b` to `.env` and restart the app. |
| `The model service answered with HTTP 400`, `401` or `403` | The key wasn't accepted (Gemini answers a bad key with 400). Check that it was copied whole, and that the API is enabled for the key's project. |
| `The model service answered with HTTP 404` | The model name is wrong or no longer offered: look it up on the provider's models page. With Ollama, the model hasn't been downloaded: `ollama list` shows what you have, and `ollama pull` plus the name gets it. |
| `The model service answered with HTTP 429` | The provider's own limit for your key was reached. Wait, or lower `STRAINSCOPE_AI_DAILY_LIMIT`. |
| `This copy has used its 200 model requests for today` | The daily cap was reached. The assistants carry on without written answers until midnight (UTC). |
| A note that the model's answer *didn't cite the sections correctly* (Ask StrainScope), or *wasn't shown because it cites nothing*, *cites something it wasn't given* or *used a number the facts don't hold* (Ask the graph) | The model broke a rule, so its answer isn't shown. The passages or facts underneath still answer the question. |
| A model's query fails with a DuckDB message | The model guessed a column that isn't there. Open the query in the SQL console and fix it, or rephrase the question. |

## 9. What's planned

A model already serves all three assistants; what's left is in the [roadmap](ROADMAP.md#deferred-items-and-their-triggers), each item with the event that would bring it forward: a model on the public online copy (setup C, whenever its owner chooses), follow-up questions in a conversation, model-written wording for the plain-language explanations (only with a model on the same computer), and a model that summarises the rows a query returns (the same condition). [Phase 7b](HANDBOOK.md#stage-13-phase-7b-the-mcp-server) turns things around: instead of StrainScope asking a model, an AI assistant you already use will be able to call StrainScope's tools through an MCP server.
