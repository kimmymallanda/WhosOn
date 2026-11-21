/* Scenario data for the phone prototype: Sunday Women AA-3, week 3, the Saturday-night drop.
   Rules lines ("check_lineup -> ...") are real output from src/rules_checker.py on data/season_history.json.
   Parser JSON is illustrative. Players and results are synthetic. */
window.SCENARIO = (function () {
  var FULL = { carla: "Carla Ruiz", lena: "Lena Fischer", isla: "Isla Moreno", dana: "Dana Kim" };
  var SHORT = { carla: "Carla", lena: "Lena", isla: "Isla", dana: "Dana" };
  var PLAYER_IDS = ["carla", "lena", "isla", "dana"];

  var LINEUP = {
    lines: [
      { lab: "Line 1 · 1:00 PM", who: "Ava Chen + Brooke Patel", why: "Same pair as before, last played line 1. Record together: 2-0. (R5)" },
      { lab: "Line 2 · 1:00 PM", who: "Carla Ruiz + Lena Fischer", why: "Same pair as before, last played line 2. Record together: 1-1. (R5) Lena: done by 4:00 PM even if it runs 3 hours." },
      { lab: "Line 3 · 2:00 PM", who: "Ellie Brooks + Fran Okafor", why: "Same pair as before, last played line 3. Record together: 1-1. (R5)" },
      { lab: "Line 4 · 2:00 PM", who: "Maya Singh + Priya Shah", why: "Same pair as before, last played line 4. Record together: 1-1. (R5)" },
      { lab: "Line 5 · 3:00 PM", who: "Hana Sato + Sam Torres", why: "Same pair as before, last played line 5. Record together: 0-1. (R5)" }
    ],
    pass: "Rules check passed (R1 to R7)",
    bench: "Backups: Dana Kim, Kara Lewis"
  };
  var LINEUP2 = JSON.parse(JSON.stringify(LINEUP));
  LINEUP2.lines[1] = {
    lab: "Line 2 · 1:00 PM", who: "Dana Kim + Lena Fischer",
    why: "New pair. Dana hasn't played this season, Lena last played line 2; line 2 is within two lines for each. (R6) Lena: done by 4:00 PM even if it runs 3 hours.",
    changed: true
  };
  LINEUP2.bench = "Backups: Kara Lewis";

  var STEPS = [
    {
      when: "Wed 6:00 PM", clock: "6:00", focus: "cap", player: "carla",
      title: "The captain picks the match",
      caption: "Wednesday evening. The agent asks before it texts anyone, because every message to the whole team needs the captain's OK.",
      behind: "Week 3 of 6: Sunday, Apr 25 vs Oak Hill TC (away).\nSunday Women's lines 1-2 start at 1:00 PM, lines 3-4 at 2:00 PM, line 5 at 3:00 PM.\nA line can run 1 to 3 hours, so later lines can start late.",
      tag: "Start times: ALTA General Rules Adult Leagues, Fall 2026, League-Specific Rules.",
      msgs: [
        { t: "cap", from: "agent", text: "Week 3: Sunday, Apr 25 vs Oak Hill TC (away). Lines 1-2 start at 1:00 PM, lines 3-4 at 2:00 PM, line 5 at 3:00 PM. Want me to text the team to ask who can play?", chips: [{ label: "Send to team", primary: true }] }
      ]
    },
    {
      when: "Wed 6:02 PM", clock: "6:02", focus: "player", player: "lena",
      title: "Each player gets a private text",
      caption: "One text per player, not a group thread. It lists all three start times, because a player's time limit decides which lines she can play.",
      behind: "16 players on the roster get one text each.\nThe channel is simulated here. The real connector (email, Slack or SMS) comes later.",
      tag: "",
      msgs: [
        { t: "cap", from: "me", text: "Send to team" },
        { t: "cap", from: "agent", text: "Done. I'm texting all 16 players one by one. I'll tell you as replies come in." },
        { t: "lena", from: "agent", text: "Hi Lena! Can you play Sunday, Apr 25 vs Oak Hill TC (away)? Lines 1-2 start at 1:00 PM, lines 3-4 at 2:00 PM, line 5 at 3:00 PM, and a line can run 1 to 3 hours. Reply in your own words, and tell me if you have a time limit." },
        { t: "isla", from: "agent", text: "Hi Isla! Can you play Sunday, Apr 25 vs Oak Hill TC (away)? Lines 1-2 start at 1:00 PM, lines 3-4 at 2:00 PM, line 5 at 3:00 PM, and a line can run 1 to 3 hours. Reply in your own words, and tell me if you have a time limit." }
      ]
    },
    {
      when: "Wed 6:14 PM", clock: "6:14", focus: "player", player: "lena",
      title: "A time limit decides which lines fit",
      caption: "Lena can play but has to leave by 4:00. A line can take up to 3 hours, so only the 1:00 PM lines (1 and 2) are safe for her.",
      behind: "{\n  \"status\": \"conditional\",\n  \"time_window\": \"until 16:00\",\n  \"conditions\": null,\n  \"confidence\": 0.9,\n  \"follow_up\": null\n}\n\ntime_fit(\"until 16:00\"):\n  Line 1  1:00 PM  ok\n  Line 2  1:00 PM  ok\n  Line 3  2:00 PM  risky\n  Line 4  2:00 PM  risky\n  Line 5  3:00 PM  risky",
      tag: "The parser JSON is illustrative. The line fit is real output from the project's time-fit code. Risky means it fits a 1-hour line, not a 3-hour one.",
      msgs: [
        { t: "lena", from: "me", text: "yes! but I have to leave by 4" },
        { t: "lena", from: "agent", text: "Got it, free until 4:00 PM. I'll keep you in the 1:00 PM lines so you can stay for a long match." }
      ]
    },
    {
      when: "Wed 7:40 PM", clock: "7:40", focus: "player", player: "isla",
      title: "A vague reply gets a question",
      caption: "The agent never guesses. Isla isn't marked available. She gets one clear follow-up instead.",
      behind: "{\n  \"status\": \"unknown\",\n  \"time_window\": null,\n  \"conditions\": null,\n  \"confidence\": 0.6,\n  \"follow_up\": \"No problem! Can you let me know by Thursday evening so I can plan the lineup?\"\n}",
      tag: "Illustrative parser output for \"maybe, depends on my babysitter\".",
      msgs: [
        { t: "isla", from: "me", text: "maybe, depends on my babysitter 😬" },
        { t: "isla", from: "agent", text: "No problem! Can you let me know by Thursday evening so I can plan the lineup?" },
        { t: "isla", from: "me", text: "will do!" },
        { t: "isla", from: "agent", text: "Thanks Isla! I'll check in Thursday." }
      ]
    },
    {
      when: "Thu 8:00 PM", clock: "8:00", focus: "cap", player: "isla",
      title: "Thursday: a lineup to approve",
      caption: "The captain decides the order. The agent only offers lineups that fit everyone's availability and ALTA's movement rules, explains each spot, and cites the rule it relied on.",
      behind: "check_lineup(lineup) -> []\n(no violations, R1 to R7)\n\nOut: Gina, Isla, Jess, Nora\nBackups: Dana, Kara",
      tag: "The lineup and each reason come from the project's lineup planner (the best of its legal options). The first line is real rules-checker output. Season history for weeks 1 and 2 is made up.",
      msgs: [
        { t: "isla", from: "me", text: "sorry, sitter fell through. I'm out" },
        { t: "isla", from: "agent", text: "Thanks for telling me, Isla. See you next week!" },
        { t: "cap", from: "agent", text: "Everyone has replied: 12 can play (Lena only until 4:00), 4 are out. Here's the lineup I'd play on Sunday.", card: LINEUP, chips: [{ label: "Approve lineup", primary: true }, { label: "Change", ghost: true }] }
      ]
    },
    {
      when: "Thu 8:03 PM", clock: "8:03", focus: "cap", player: "isla",
      title: "Approve, then approve sending",
      caption: "Two separate taps: the lineup itself, then sending it to the players.",
      behind: "Nothing leaves the agent until the captain taps.",
      tag: "",
      msgs: [
        { t: "cap", from: "me", text: "Approve lineup" },
        { t: "cap", from: "agent", text: "Saved. Want me to text each player her line?", chips: [{ label: "Send to team", primary: true }] }
      ]
    },
    {
      when: "Thu 8:05 PM", clock: "8:05", focus: "player", player: "carla",
      title: "Each player gets her own line",
      caption: "Each text is built from the lineup: her line, her partner, her start time, when to arrive, and how long to plan to stay.",
      behind: "10 players get their line, partner and time.\n2 backups get a stand-by note.",
      tag: "The wording comes from the project's message builder, so the times are always right.",
      msgs: [
        { t: "cap", from: "me", text: "Send to team" },
        { t: "cap", from: "agent", text: "Sent. All 10 players have their line and 2 backups are on stand-by." },
        { t: "carla", from: "agent", text: "Carla, you're on Line 2 with Lena Fischer for Sunday, Apr 25 vs Oak Hill TC. Start: 1:00 PM. Arrive by 12:50 PM to warm up. A line can run up to 3 hours, so plan to stay until about 4:00 PM. Reply here if anything changes." },
        { t: "lena", from: "agent", text: "Lena, you're on Line 2 with Carla Ruiz for Sunday, Apr 25 vs Oak Hill TC. Start: 1:00 PM. Arrive by 12:50 PM to warm up. A line can run up to 3 hours, so plan to stay until about 4:00 PM. Reply here if anything changes." },
        { t: "dana", from: "agent", text: "Dana, you're a backup for Sunday, Apr 25. I'll only text you if someone drops." }
      ]
    },
    {
      when: "Sat 9:04 PM", clock: "9:04", focus: "cap", player: "carla",
      title: "Saturday 9:04 PM: a player drops",
      caption: "Carla texts the agent, not the captain. The agent sees the lineup is no longer legal and starts fixing it.",
      behind: "{\n  \"status\": \"unavailable\",\n  \"time_window\": null,\n  \"conditions\": null,\n  \"confidence\": 0.95,\n  \"follow_up\": null\n}\n\ncheck_lineup(old lineup) ->\n  R4: Carla Ruiz is not confirmed available.",
      tag: "The parser JSON is illustrative. The rules line is real checker output.",
      msgs: [
        { t: "carla", from: "me", text: "omg so sorry, my daughter has a fever, I can't play tomorrow 😷" },
        { t: "carla", from: "agent", text: "Hope she feels better soon! I'll find a replacement now. Thanks for telling me early." },
        { t: "cap", from: "agent", text: "Heads up: Carla Ruiz dropped out of Line 2. Lena Fischer needs a partner for a 1:00 PM start. I'm finding a legal replacement." }
      ]
    },
    {
      when: "Sat 9:06 PM", clock: "9:06", focus: "player", player: "dana",
      title: "The agent skips a backup who can't legally play",
      caption: "Kara is the obvious pick, but ALTA lets a player move only two lines from where she last played. The agent checks first, so it never offers a spot a player can't take.",
      behind: "check_lineup(Kara at line 2) ->\n  R6: Kara Lewis last played line 5; a player may move only 2 lines, so line 2 is not allowed.\n\nLines each may play:\n  Kara  [3, 4, 5]\n  Dana  [1, 2, 3, 4, 5]  (no matches yet)",
      tag: "Real output from the project's rules checker, using made-up season history.",
      msgs: [
        { t: "cap", from: "agent", text: "Two backups: Kara Lewis and Dana Kim. Kara can't play line 2. She last played line 5, and ALTA lets a player move only two lines (R6). Dana hasn't played this season, so any line is legal for her. I asked Dana." },
        { t: "dana", from: "agent", text: "Hi Dana, a spot just opened: Sunday, Apr 25 vs Oak Hill TC, Line 2 with Lena Fischer, 1:00 PM start. A line can run up to 3 hours. Can you play?" }
      ]
    },
    {
      when: "Sat 9:11 PM", clock: "9:11", focus: "cap", player: "dana",
      title: "A backup says yes, the lineup is fixed",
      caption: "The agent re-checks the whole lineup before showing it. The changed spot is highlighted, so the captain only reads what moved.",
      behind: "{\n  \"status\": \"available\",\n  \"time_window\": null,\n  \"conditions\": null,\n  \"confidence\": 0.95,\n  \"follow_up\": null\n}\n\ncheck_lineup(corrected lineup) -> []",
      tag: "The parser JSON is illustrative. The rules line is real checker output.",
      msgs: [
        { t: "dana", from: "me", text: "yes! I can do 1:00 🎾" },
        { t: "dana", from: "agent", text: "You're in! Line 2 with Lena Fischer, 1:00 PM. Arrive by 12:50 PM to warm up and plan to stay until about 4:00 PM." },
        { t: "cap", from: "agent", text: "Dana Kim said yes. Line 2 is now Dana Kim + Lena Fischer (was Carla Ruiz).", card: LINEUP2, chips: [{ label: "Approve change", primary: true }, { label: "Change", ghost: true }] }
      ]
    },
    {
      when: "Sat 9:12 PM", clock: "9:12", focus: "cap", player: "lena",
      title: "One tap and it's done",
      caption: "In this scenario the drop took one tap from the captain, eight minutes after Carla's text (simulated clock).",
      behind: "Captain taps in this scenario: 4\n(Send, Approve, Send, Approve)\n\nProject target: under 10 minutes of captain time per match.",
      tag: "",
      msgs: [
        { t: "cap", from: "me", text: "Approve change" },
        { t: "cap", from: "agent", text: "Done. I told Lena about her new partner and let Carla off the hook. You're set for tomorrow." },
        { t: "lena", from: "agent", text: "Lena, your partner for Line 2 is now Dana Kim. Same 1:00 PM start." },
        { t: "dana", from: "agent", text: "Dana, you're on Line 2 with Lena Fischer for Sunday, Apr 25 vs Oak Hill TC. Start: 1:00 PM. Arrive by 12:50 PM to warm up. A line can run up to 3 hours, so plan to stay until about 4:00 PM. Reply here if anything changes." }
      ]
    }
  ];

  return { FULL: FULL, SHORT: SHORT, PLAYER_IDS: PLAYER_IDS, STEPS: STEPS };
})();
