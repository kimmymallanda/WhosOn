# Build the MVP: Tennis Captain Agent (the "9pm drop" demo)

Read `CLAUDE.md` first. It has the architecture, design rules, data files and targets.
This prompt narrows that plan to a demo-able MVP.

## Goal
An agent that acts as co-captain for an adult league tennis team. For one upcoming
match it must: collect availability from players by one-on-one message, parse their
messy replies, build a valid lineup, and, when a player drops late, find and ask a
sub and produce a corrected lineup. The captain approves every lineup with one tap.

The MVP is done when I can run the **9pm-drop demo** end to end on the synthetic
data (see "Definition of done").

## Who uses it
- **Captain** (me, or a captain I interview): sets the match, approves lineups and
  team-wide messages. Wants to spend under 10 minutes per match.
- **Players**: get one-on-one messages and reply in plain language. They never
  install or log in to anything.

## In scope for the MVP
1. **Availability request**: for a chosen match from `data/schedule_sunday_women_A.json`, send
   each player on `data/roster.json` a one-on-one text (`src/messages.py`) with the match
   details and all three line start times, so players can name a time limit. This is an ALTA
   team (Sunday Women AA-3 first): five doubles lines, lines 1-2 start together, lines 3-4 an
   hour later, line 5 an hour after that, and a line can take 1 to 3 hours. Regular season only.
2. **Availability parser**: LLM turns each reply into
   `{status, time_window, conditions, confidence, follow_up}` using
   `prompts/availability_parser.md`. Confidence below 0.8 or status `unknown` sends
   the `follow_up` question to the player. Never guess.
3. **Rules checker in code**: `src/rules_checker.py` (`check_lineup`, `allowed_lines_for_pair`,
   `check_roster_add`) is the only authority on eligibility. It implements ALTA's regular-season
   rules R1 to R8 (see `data/league_rules_ALTA.md`): format, roster, one line, availability,
   pair movement, player movement, sandbagging, roster add-ons. Extend it only if an ALTA rule
   is missing, with a test and a rule ID for each. `src/line_times.py` compares a player's
   time limit with line start times (a line may run 1 to 3 hours, so it reports ok, risky or no).
4. **Lineup planner (code first)**: `src/planner.py` (with a JavaScript copy in n8n) searches the
   legal five-line lineups and returns the best few, so every option is legal by construction.
   The captain decides the order: she can give a ranking, fix a pair on a line, or rest a
   player. It scores stability against last week's lineup (or the current one after a drop),
   fairness (matches played), time limits, preferred side and her ranking, explains every line
   with the rule ID it relied on, and says why when no legal lineup exists. A model may phrase
   the message to the captain; it never decides who is legal. The parser only extracts a time
   limit; the comparison with line times is code (`line_times.time_fit`).
5. **Captain approval**: the lineup goes to the captain with Approve / Change. Nothing
   is sent to the team until the captain approves.
6. **Sub finder**: when a player in the approved lineup drops, rank eligible players
   (available or conditional-and-compatible, not already in the lineup, rule-valid),
   message the top candidates, handle yes/no, and re-run the planner and the
   rules checker for the corrected lineup. The captain approves again.
7. **Season memory**: each player's last legal line, each pair's last line together and
   win/loss record, and matches played. The movement and sandbagging rules cannot be
   checked without these. Start from `data/season_history.json`; a JSON file or small data
   table is enough. Decide with the captain whether to track it from week 1 or import ALTA's
   tracking sheet.

## Out of scope for the MVP
SMS via Twilio (stretch), reading iMessage or WhatsApp group chats (no practical API),
payments, a mobile app, multi-team support (the league is a setting, so other adult ALTA
teams work by changing it), playoffs, reading ALTA's member portal (it needs a login), and RAG over the rulebook (Week 2, build after the
demo works unless it's trivial).

## Non-negotiable design rules (from CLAUDE.md)
- Hard eligibility rules live in code. The LLM proposes. `check_lineup()` must return
  no violations before any lineup is shown to the captain or sent.
- Ask, don't guess. Low-confidence parses trigger a clarifying message.
- The captain approves every lineup and any message to the whole team.
- Explain every slot with a one-line reason and the rule ID.
- Store only roster data: names, contact handles, ratings, availability, results.
- Keep keys in `.env`. Never commit them. Never put real player data in the repo.
  All data stays synthetic for now.

## Technical approach
- **Orchestrator:** n8n with Claude. Build and test the workflows with the n8n tools
  available in this environment (call `get_user_preferences` and read the n8n
  instance context first). Start from my existing workflow in
  `../Tennis Coach Agent.json` (a manual trigger, the parser agent with structured
  output, an If node on confidence, and edit-fields nodes) and extend it rather than
  starting over. Export the stable workflows to an `n8n/` folder as JSON.
- **Models:** a small fast model (Claude Haiku) for the parser. A stronger model
  (Claude Sonnet) for the lineup planner. Latest model IDs only.
- **Code:** Python 3.11+, type hints, small pure functions. Anything deterministic
  (eligibility, playoff counts, ranking subs) is code, not a prompt. If n8n needs to
  call it, expose it as a small function or HTTP endpoint and say how to run it.
- **Messaging for the MVP:** email or Slack DMs, one-on-one. Ask me which one before
  wiring it up. For the first demo, a simulated channel where I type each player's
  reply is acceptable, as long as the connector can be swapped later.
- **Captain approval:** a message to me with Approve / Change buttons (Slack) or a
  reply-to-approve link (email). Whatever it is, one tap.

## Evaluation (do not skip)
- Parser: run `python evals/score_parser.py` against `data/labeled_replies.jsonl`.
  The prompt was tuned on the current 20 replies, so also write a **held-out set of
  at least 20 new messy replies** that are never used to tune the prompt, and report
  accuracy on those separately. Target 95%+.
- Rules checker: `pytest -q` passes, and each new rule has a test.
- Lineup validity must be 100%: add a test that runs the planner over many
  availability scenarios and asserts `check_lineup()` returns no violations.

## How to work
1. First, read the repo and my n8n workflow, then give me a short plan: which
   workflows you'll build, what runs in n8n vs. Python, and any questions
   (messaging channel, real league rules). Wait for my OK.
2. Build in this order, showing me working output at each step:
   a. Parser workflow scoring on the held-out set.
   b. Availability collection loop with follow-up questions.
   c. Lineup planner plus rules-checker veto loop (retry, then escalate to captain).
   d. Captain approval step.
   e. 9pm-drop: sub finder and corrected lineup.
3. Keep it simple. Ask before adding anything out of scope.
4. Report test and eval results honestly, including failures. Flag every assumption.

## Definition of done: the 9pm-drop demo
On the synthetic roster and a chosen match:
1. The agent messages all players and collects replies, including at least 5 messy ones
   ("maybe if it's after 2", "emergency sub only pls", "👍", "can play but only doubles").
2. It sends at least one clarifying question for an ambiguous reply.
3. It proposes a lineup with a one-line reason and rule ID per slot, and
   `check_lineup()` shows no violations.
4. I approve with one tap.
5. A player in the lineup drops at 9pm. The agent finds eligible subs, messages them,
   gets a yes, produces a rule-valid corrected lineup, and I approve it.
6. Total captain effort in the demo is a few taps and no manual lineup editing.

## Deliverables
- Working n8n workflows (exported JSON in `n8n/`) and any supporting Python.
- Held-out parser eval set and a short results table.
- Updated `README.md` with how to run the demo.
- A short "known gaps and next steps" list (rules RAG, Twilio SMS, season memory depth).
