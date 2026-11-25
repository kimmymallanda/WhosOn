# WhosOn

Course project for the Master Agentic AI Certification (Maven, Nov 2026 – Jan 2027). Pitch Day: Jan 11–12, 2027.

## What we're building
An agent that acts as co-captain for an adult league tennis team (USTA or similar). It texts each player one-on-one for availability, reads their messy plain-language replies, builds a valid and fair lineup, and finds a sub when someone drops at 9pm. The captain approves with one tap.

- PRD (Claude doc): https://claude.ai/artifact/1SrD5p3L9pPizfviMSjTwD
- PRD (Word copy): `docs/WhosOn_PRD.docx`
- Project plan: https://claude.ai/artifact/AKoMJWQbiubj2SHJyM59ia

## League: ALTA
Built for ALTA (Atlanta Lawn Tennis Association) adult leagues, first team **Sunday Women AA-3**, designed so any adult ALTA team works by changing the league in `data/league_config.json`. Source: ALTA General Rules Adult Leagues, Fall 2026 (PDF in the folder above this project). **Regular season only. Playoffs are out of scope** (the movement rules do not apply there; ordering uses a separate win/loss value).
- Five doubles lines (1D to 5D), two players each. Lines 1-2 start together, lines 3-4 an hour later, line 5 an hour after that. A line can take 1 to 3 hours, so later lines can start late.
- The captain decides the line order. The agent offers only lineups that fit availability and ALTA's movement and sandbagging rules, and explains the trade-offs.
- A sub must be on the roster (up to six add-ons, level at or below the team's, until the scheduled start). A player never moves down once the lineup is exchanged.

## Architecture
One orchestrator (n8n + Claude) with four skills, backed by a rules knowledge base and a season memory:

1. **Messaging connector**: one-on-one messages to each player. Email or Slack DMs for the MVP; SMS via Twilio is a stretch goal. Do not try to read iMessage/WhatsApp group chats (no practical API).
2. **Availability parser (LLM)**: free-text reply → `{status, time_window, note}`. Prompt in `prompts/availability_parser.md`.
3. **League rules knowledge base (RAG)**: the league's rulebook, retrieved with citations.
4. **Rules checker (code)**: `src/rules_checker.py`. Deterministic. Can veto any lineup. ALTA rules R1 to R8: format, roster, one line, availability, pair movement, player movement, sandbagging, roster add-ons. Also gives each player's and pair's allowed lines. `src/line_times.py` compares a time limit ("until 16:00") with line start times. `src/messages.py` builds each player's text from the lineup, so times and line numbers never come from a model.
5. **Lineup planner (code first)**: `src/planner.py` searches the legal lineups and ranks them (stability against last week or the current lineup, fairness, time limits, preferred side, the captain's ranking, fixed pairs, rested players), with a reason and rule ID for every line, and says why when no legal lineup exists. The captain decides the order. A model may phrase the message to the captain; it never decides who is legal.
6. **Season memory**: each player's last legal line, each pair's last line together and win/loss record (the movement and sandbagging rules need these), matches played, reliability.
7. **Messenger and sub finder**: confirmations, nudges, sub requests.

## Non-negotiable design rules
- **Hard eligibility rules live in code, never in the model.** The LLM proposes; `rules_checker.check_lineup()` must return no violations before anything is sent.
- **Ask, don't guess.** Low-confidence parses trigger a clarifying message to the player.
- **Captain approves** every lineup and any message to the whole team.
- **Explain every slot** with a one-line reason and the rule ID it relied on.
- Store only roster data: names, contact handles, ratings, availability, results.

## Data (all synthetic)
- `data/roster.json`: 16 fictional players on a Sunday Women AA-3 team (level flights like AA-3 or A-2, preferred side).
- `data/alta_leagues.json`: line counts and start times for every adult ALTA league (from the Fall 2026 rules).
- `data/league_config.json`: this team's league, level and the movement limits.
- `data/season_history.json`: made-up weeks 1 and 2 (lineups and results), the input to the movement and sandbagging checks.
- `data/schedule_sunday_women_A.json`: six synthetic regular-season Sundays. (`data/schedule.json` is the old Saturday sample, kept only because the parser eval sets refer to its matches.)
- `data/league_rules_ALTA.md`: the rules the checker implements, with section references. Use as the starting point for rules retrieval (RAG). The old `league_rules_SAMPLE.md` is superseded and can be deleted.
- `data/labeled_replies.jsonl`: labeled availability replies (tuning set: the parser prompt was written against these). Grow to ~200.
- `data/heldout_replies.jsonl`: 30 held-out replies for match m02. **Never tune the prompt on these.** Run them to get the real accuracy number. If you read the results and change the prompt, write a fresh held-out set before quoting accuracy again.

## Commands
```bash
pip install -r requirements.txt
pytest -q                                   # rules checker, line-time and message tests
python evals/score_parser.py preds.jsonl    # score parser predictions against the tuning set
python evals/score_parser.py preds.jsonl --heldout   # score against the held-out set
python evals/heldout_to_n8n.py              # print the held-out replies as JS for the n8n Code node
python n8n/build_nodes.py                   # regenerate the n8n Code-node files (see "n8n nodes" below)
```

## n8n nodes
n8n Cloud cannot run the Python modules, so the rules and time-fit logic also exist as JavaScript in n8n Code nodes:
- `n8n/src/rules_core.js`, `n8n/src/time_fit_core.js` and `n8n/src/planner_core.js` are JavaScript copies of `src/rules_checker.py`, `src/line_times.py` and `src/planner.py`. `n8n/src/setup_core.js` has no Python copy.
- `python n8n/build_nodes.py` combines them with the data in `data/*.json` and writes `n8n/nodes/*.js` (paste into Code nodes) and `n8n/checker_cases.json` (test cases plus the Python answers).
- `tests/test_n8n_nodes.py` runs the generated node code in Node.js and requires the same output as Python, messages included. **When you change a rule, change both the Python and the JavaScript, rebuild, and keep the tests green.**
- Live n8n workflows, each on its own canvas with a note explaining what it does and how it connects:
  - **Weekly 1 of 3 - Read player replies**: the parser, the follow-up question, and which lines fit a time limit. Uses 20 sample replies for now.
  - **Weekly 2 of 3 - Check a lineup (ALTA rules)**: the rules checker (R1-R7). Called by workflow 3, and runnable by hand with sample lineups.
  - **Weekly 3 of 3 - Plan lineups (ALTA rules)**: the planner. It sends every option it proposes to workflow 2 for a second, independent check.
  - Roster, config and season history are still embedded as sample data in the planner and checker nodes. They move to the data tables below next.
- Setup workflows (all built, tested with sample data), each its own canvas named "Setup N of 5 - ...": **1 Invite a captain (email)** (you run it; saves the invite, Gmail send off), **2 Confirm league and season** (form path `tca-setup-2-league`), **3 Upload the roster** (`tca-setup-3-roster`), **4 Upload the schedule** (`tca-setup-4-schedule`; accepts Excel, CSV, or the printed ALTA division schedule PDF as is, which it reads by text with no AI: the captain types her team number, or it is matched from her name against the captains listed, and home/away and facility come from the "Team 8 at Team 1" pairings; the PDF's league, season and year must match what she confirmed in step 2. **Setup 4's "Prepare the check" node has `TEST_MODE = true` for now, which skips those matches and defaults to team 1. Set it to false before a real launch.**), **5 Review and send intro emails** (`tca-setup-5-send`, marks the team `ready`; the Gmail node is ON but a `TEST_MODE = true` node sends only one copy to the tester, **set it to false before a real launch or real players get emailed**), **Weekly 4 - Send the captain the ALTA entry sheet** (lineup laid out like ALTA's page for the captain to copy and publish herself; the agent never logs in to ALTA; Gmail off). Pages 2 to 4 call **Setup helper - Check what the captain entered**, which runs `setup_core.js`. As of Nov 25, Setup 2 to 5 are published in n8n. The real browser file upload has only been tried with test data.
- Setup flow: the captain gets an invite email with a private link, confirms league and season, then uploads a roster and a schedule (CSV or Excel). The checks are in `n8n/src/setup_core.js` (JavaScript only, tested by `tests/test_setup_import.py` with made-up files in `tests/fixtures`). Templates for the captain are in `templates/`. Data tables in n8n: **WhosOn captain invites and teams**, **WhosOn team players**, **WhosOn team matches**. Email is the first channel; nothing is sent until an inbox is connected and you approve.
- Planner weights (move 4, newcomer 3, new pair 6, risky time limit 12, matches played 1, same side 2, ranking 2, reserve 10) are whole numbers in `WEIGHTS`, in both languages, so results match exactly. They are a first guess; tune them with a real captain.

## Rules retrieval (RAG)
- `python src/build_rulebook.py` splits ALTA's General Rules text into about 70 citable sections (`data/rulebook/sections.json`). **`data/rulebook/` is gitignored: the repo is public, so never commit ALTA's rulebook text.** Source text: `osascript -l JavaScript src/pdf_text.jxa.js /full/path/rules.pdf > data/rulebook/general_rules_fall2026.txt`.
- `src/rules_search.py` (keyword search, no embeddings) with a JavaScript copy in `n8n/src/search_core.js`. The n8n Code nodes in "WhosOn Rules 2" hold a hand-pasted compact copy (not built by `build_nodes.py`): change all together.
- First-run score: right section in the top 4 for 23/24 questions (`data/rules_questions.json`) and 9/10 unseen ones (`data/rules_questions_heldout.json`; top 1: 6/10). `python evals/score_rules_search.py`. Known miss: "two lines in the same match day" (I.B).
- n8n: **WhosOn Rules 1 - Load the rulebook** (upload `sections.json` once) and **WhosOn Rules 2 - Ask the ALTA rules** (Claude Haiku answers only from retrieved sections; code rejects bad citations). Table **WhosOn rulebook sections** holds only III.E, III.F and IV.G until the file is uploaded. Both unpublished.

## Landing page
- **Product name (Nov 25, "for now"): WhosOn**, formerly Tennis Captain Agent. Not cleared for trademark (Parker Software owns a WHOSON mark) or domain. Unchanged on purpose: local folder, GitHub repo name, agent Gmail address, and `tca-` form/webhook paths.
- `site/index.html`: flashy front page; the visitor picks ALTA (beta), USTA or Custom League incl. pickleball (both waitlist only, not built). `site/join.html?league=alta|usta|custom`: detail page and email signup.
- **Messaging priority (captain's call):** the headline benefit is ending the 50-text chase to confirm availability ("Messy replies, sorted"). Lineups and rules are secondary.
- Signup posts to n8n **WhosOn Website - Beta signup** (table **WhosOn beta signups**; `source` records the league; one test row, test.signup@example.com). The workflow is unpublished and the pages are not hosted yet.

## Course plan
| Week | Dates | Build | Gate |
| --- | --- | --- | --- |
| 1 Foundations | Nov 16–22 | First n8n agent: parse availability replies | 10 messy replies parsed |
| 2 Retrieval | Nov 23–29 | RAG over league rules; rules checker in code | Cites the rule it applies |
| 3 Evals | Nov 30–Dec 6 | Subagents + connectors (email/Slack); judge-model eval | Baseline accuracy set |
| 4–5 Build | Dec 7–20 | Season memory, sub-finding, captain approval loop | 9pm-drop demo works |
| Break | Dec 21–Jan 10 | Interview 3–5 captains, harden demo, pitch | A real captain tries it |
| Pitch Day | Jan 11–12 | Live demo: the 9pm drop | Judges' feedback |

## Targets
Parsing accuracy 95%+ · lineup validity 100% · captain acceptance 80%+ · sub filled within 2 hours · captain time under 10 min per match.

## Conventions
- Python 3.11+, type hints, small pure functions; every rule check returns a rule ID.
- n8n workflows are built in the n8n UI (or by Claude through the n8n tools); export them to `n8n/` as JSON when stable. Code-node logic comes from `n8n/src/` via `n8n/build_nodes.py`, never hand-edited in n8n.
- Keep secrets (Anthropic API key, Twilio) in `.env`, never committed.
