# Switching on a language model (optional), at home and online

[← README](../README.md) · [Handbook](HANDBOOK.md) · [Phase 6b §8](07b-docs-assistant.md#8-step-4-optional-written-answers-from-a-model-on-your-own-computer) · [Phase 7 §10](08-deployment-ai.md#10-step-6-optional-a-language-model-for-the-three-assistants) · [Glossary](GLOSSARY.md) · [Roadmap](ROADMAP.md)

**Prerequisites:** the project set up on your computer and the app running ([Handbook Stage 10](HANDBOOK.md#stage-10-phase-6-the-app)). For the online copy, an online copy of your own ([Phase 7 §9](08-deployment-ai.md#9-step-5-put-the-app-online-streamlit-community-cloud)).

Everything in StrainScope works without a language model. The three assistants find their answers by search and by rules, and they show you where every answer came from. A model, if you switch one on, adds one thing to each:

- **Ask StrainScope** writes a short answer above the passages it found, citing them.
- **Ask the graph** writes a short answer above the numbered facts, citing them, and may not add a number of its own.
- **Ask the data** writes a new SQL query when no tested recipe fits. The query passes five guards before it runs, and it's shown so you can check it.

*In plain words* (the Strain and Ranking pages) never uses a model. What each assistant may send to a model, and what it never sends, is the table in [Phase 7 §1](08-deployment-ai.md#what-a-model-may-see-and-what-it-never-sees). The short version: the question you typed, documentation passages, table and column names, a few example recipes and facts about concepts may go, along with StrainScope's fixed rules for the model; a row of data, a strain's results, an upload or anything else on your computer never does.

This page collects every way to switch a model on and off in one place, and how to check that your model follows the rules (§9). The two guides linked above explain the ideas behind it.

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

   **You should see** a block called `Written answer (llama3.2:3b, from the facts below):` between the first line and the route, with the seven facts of [Phase 7 §7](08-deployment-ai.md#7-step-3-ask-the-graph) under it. On an Intel MacBook Pro it looked like this (the answer is one long line in the terminal; it's wrapped here so you can read it):

   ```
     ✓ From the knowledge graph: 7 facts about iturin, each with its source.

     Written answer (llama3.2:3b, from the facts below):

       Iturin suppresses disease by working through lipopeptide membrane attack [3][4], but the exact
       mechanism is not known [5]. Iturin is a product of the ituA gene [7], and its chemical structure
       is C48H74N12O14 with a molecular weight of 1043.2 [2].

     Route: iturin -acts_by-> lipopeptide membrane attack -contributes_to-> disease suppression
   ```

   Your wording may differ, because it comes from the model (a newer version of the model, or another computer, can change it). What stays the same is the request: it asks for every sentence to end with the numbers of the facts it uses, such as `[3]` or `[3][4]`, and the checks make sure a shown answer cites at least one fact and only facts it was given (§9). Read the answer as a summary to check against the facts under it. In the one above, *the exact mechanism is not known [5]* misreads fact 5, because facts 3 and 4 give the mechanism. The checks can tell that a sentence cites a fact, but not whether it reads the fact correctly, so when the two disagree, the facts win. Each answer took 5 to 15 seconds on that Mac; the first one after Ollama starts can take longer, because Ollama loads the model into memory first. If you see `(written answer: The model's answer wasn't shown because it cites nothing. ...)` instead, see §8.

5. **Check that your model cites its sources** (optional, a minute or two):

   ```bash
   python src/strainscope/service.py check-model
   ```

   It asks the model four questions, two through Ask the graph and two through Ask StrainScope, with exactly the requests the app sends, and says for each one whether the written answer would be shown. **You should see** a heading, the model's name, four results that each start with ✓ (with the model's answer under it), ✗ (with the reason it would be hidden) or · (the question never reached the model, for example because Ollama isn't running, with the reason), and at the end:

   ```
     4 of 4 written answers would be shown.
   ```

   Fewer than four isn't an error, because a hidden answer leaves the passages or facts on screen. §9 explains what the check looks for.

6. **Restart the app**, if it's running, and continue with §6.

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
4. **Check it** with the two commands of §3 step 4 (in a terminal where `(.venv)` shows). The status line now starts `on, hosted: gemini-3.5-flash-lite at https://generativelanguage.googleapis.com/v1beta/openai (hosted)`, and the answer's block says `Written answer (gemini-3.5-flash-lite, from the facts below):`. `python src/strainscope/service.py check-model` (§3 step 5) works the same way; its four requests count towards the provider's limits like any others.

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
- On Ask StrainScope the model is given only the strong matches: the best passage, and the next ones only if they match nearly as well (§9). The screen still shows all three.
- On Ask the data, a tested recipe that fits always runs without the model; the model is asked only when none fits.
- A question about a strain on Ask the graph is always answered by rules.

**About this copy** shows whether a model is on, and the footer of each Ask page says so too.

Read a written answer as a summary of what's under it. If the two disagree, the passages or facts win; if a model's query looks wrong, open it in the SQL console with the button under it and fix it there.

## 7. Switching it off

- **At home:** in `.env`, set every `STRAINSCOPE_ASK_BACKEND` line to `none` (or delete them all), then restart the app. If one is set in the terminal, clear it too: `unset STRAINSCOPE_ASK_BACKEND` (PowerShell: `Remove-Item Env:STRAINSCOPE_ASK_BACKEND`). To stop Ollama itself: quit it from the menu-bar icon (macOS) or the system tray (Windows), or `sudo systemctl stop ollama` (Linux). To remove the model, or Ollama itself, from the computer: [`docs/UNINSTALL.md`](UNINSTALL.md#the-language-model-ollama).
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
| A note that the model's answer *didn't cite the sections correctly* (Ask StrainScope), or *wasn't shown because it cites nothing*, *cites something it wasn't given* or *used a number the facts don't hold* (Ask the graph) | The model broke a rule, so its answer isn't shown, and the passages or facts underneath still answer the question. Once in a while that's normal. If it happens to most answers, bring your copy up to date (`git pull`: the request described in §9 arrived in [Handbook Stage 12.1](HANDBOOK.md#stage-121-fix-for-small-language-models-the-model-check-and-clearer-suggestions)), then run `python src/strainscope/service.py check-model`. If the check shows most answers hidden, a larger model usually follows the rules better, if your computer has the memory for it: `ollama pull llama3.1:8b` (a 4.9 GB download that needs at least 8 GB of free memory), then `STRAINSCOPE_ASK_MODEL=llama3.1:8b` in `.env` and a restart. |
| `check-model` says `No language model is switched on` | `STRAINSCOPE_ASK_BACKEND` isn't set to `local` or `hosted` in `.env` or in this terminal (§2). |
| A model's query fails with a DuckDB message | The model guessed a column that isn't there. Open the query in the SQL console and fix it, or rephrase the question. |

## 9. How a written answer is asked for, and checked

Ask StrainScope and Ask the graph send a model the material they found, numbered, and ask for a short answer that cites it. A citation is a number in square brackets, such as `[3]`, that points at one passage or fact; with it, you can check every sentence against its source. Before an answer reaches the screen, three checks run in `src/strainscope/llm.py`:

1. Does it cite at least one number?
2. Does it cite only numbers it was given? (An answer citing `[7]` when there were three passages is hidden.)
3. Ask the graph only: does it add no number of its own? A formula or a weight the facts hold is fine; a percentage the facts don't hold isn't.

An answer that fails any of them is hidden, with a short note saying why, and the passages or facts stay on screen. If the model ignores the rules, you lose the summary and keep everything else.

![What a model is sent, the checks, and the test that chose the request](../figures/written_answer_check.png)

### Why the request says it three ways

The first version of the request said it once, in the rules: *Cite the facts you use as [1], [2] and so on.* The tests passed: they use a stand-in model whose replies the tests write themselves, so a real model's habits never came up. llama3.2:3b, the small model of setup A, didn't: on an Intel MacBook Pro it wrote correct sentences, for example *Iturin suppresses disease by working through lipopeptide membrane attack, which contributes to disease suppression*, without a single citation, so every answer was hidden.

To find out what a small model needs, I asked the same four questions (two for each assistant) with four versions of the request, using the same model on the same Mac:

| Version | What the request adds | Answers shown |
|---|---|---|
| A | nothing: the rules say *cite* once | 0 of 4 |
| B | the rule spelled out with an example sentence: *End every sentence with the numbers of the facts it uses, in square brackets, like this: The pump runs on solar power [1]. It moves water to the tank [2][3].* | 4 of 4 |
| C | B, plus a reminder at the very end, after the material | 4 of 4 |
| D | C, plus one worked example: a question about a made-up pump, and an answer that cites it | 4 of 4 |

B, C and D all passed. I chose D because its answers were the shortest overall and padded the least: with B and C the model sometimes added a claim no passage makes (that the simulated data "helps to improve its performance and accuracy"). A worked example like this is called **few-shot prompting** (one shot here): the model is shown a finished example of the task, not only a description of it. In this test it wasn't what made the model cite (B already did, with the example sentence alone), but it kept the answers shortest. It's about a pump on purpose: nothing from StrainScope and no numbers, so the model can't copy a fact or a number from it into a real answer.

So since the fix in [Handbook Stage 12.1](HANDBOOK.md#stage-121-fix-for-small-language-models-the-model-check-and-clearer-suggestions), every written-answer request has four parts, in this order: the rules (with the citation rule), the worked example (as one question and one answer), the real question with its numbered material, and the reminder. You can see it in `cited_messages()` in `src/strainscope/llm.py`, and the tests in `tests/test_llm.py`, `tests/test_ask.py` and `tests/test_ask_graph.py` check every part.

A larger model may well have cited with version A. The test only shows what one small model needed, which is why the check below exists.

### Only strong matches go to the model

Citations make an answer checkable, but they can't make it right when the material is off the point. With llama3.2:3b switched on, the first starter question, "How do I set up my laptop?", got a written answer about choosing a language model. It cited correctly, and it was no help: the passage it leaned on, [2], was the table in §1 of this page. The search had put the right guide first (match 0.22), but the next two matches (0.15 each) only shared two of the question's words, and the model summarised all three. Ask someone to sum up three pages and they'll sum up the third as well, even if it's about something else, so it's better to hand over only the pages that answer the question.

So Ask StrainScope now gives the model the best passage and, of the next two, only those whose match is at least three quarters of the best one's (`STRONG_MATCH` and `model_hits()` in `src/strainscope/ask.py`). The numbers stay the ones on the screen, so an answer citing a passage the model wasn't given is hidden. Two examples from the golden questions:

| Question | Matches of the three passages shown | Given to the model |
|---|---|---|
| "What is a balanced error rate?" | 0.47, 0.27, 0.20 | [1] only |
| "Why is the data simulated?" | 0.17, 0.16, 0.15 | all three |

Of the 49 starter and golden questions the search answers, 27 now send one passage and 22 send two or three. (Three quarters of the best *match* is a different rule from the gate's 75 % of the question's *words*, described in [Phase 6b §1](07b-docs-assistant.md#the-gate-answered-closest-or-refused); they just happen to use the same share.)

### Check your own model

```bash
python src/strainscope/service.py check-model
```

It asks the four questions of the test above through the real assistants, so the requests are exactly the ones the app sends, and runs the three checks on each answer. Run it after switching to a new model or provider, or after updating Ollama. It sends four requests, which count towards a hosted provider's limits. `STRAINSCOPE_AI_DAILY_LIMIT` counts from 0 in every program that starts, so the check never uses up the app's allowance, but a limit below 4 stops it partway. A question that never reaches the model (Ollama not running, a used-up limit, a missing key) is marked with · and the reason, and doesn't count as hidden. With no model switched on, it sends nothing and says so.

## 10. What's planned

A model already serves all three assistants; what's left is in the [roadmap](ROADMAP.md#deferred-items-and-their-triggers), each item with the event that would bring it forward: a model on the public online copy (setup C, whenever its owner chooses), follow-up questions in a conversation, model-written wording for the plain-language explanations (only with a model on the same computer), a model that summarises the rows a query returns (the same condition), and a button on *About this copy* that runs the model check of §9, for the owner of an online copy, who can't run a terminal command there. [Phase 7b](08b-mcp-server.md) turned things around: instead of StrainScope asking a model, an AI assistant app you already use (Claude Desktop, Claude Code and others) calls StrainScope's tools through its MCP server. That needs none of the settings in this document, because the app brings its own model; what the app's model then sees is listed in [`docs/08b-mcp-server.md` §1](08b-mcp-server.md#what-the-assistant-sees).
