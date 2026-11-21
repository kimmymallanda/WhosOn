# ALTA adult league rules the agent uses (regular season)

Paraphrased from **ALTA General Rules Adult Leagues, Fall 2026 (last revised Spring 2026)**. Section references are to that document. The ALTA Lineup Checker in the member portal is the authority; `src/rules_checker.py` is a pre-check. Check the current season's rules before relying on any limit.

## Format and times
- **R1 Format.** A dual meet is five doubles matches (League-Specific Rules). Lines are numbered 1 to 5 and recorded as 1D to 5D on the scorecard.
- **Start times** are set per league. The first time is for lines 1-2, then "following positions" start an hour apart: Sunday Women 1:00 PM, then 2:00 and 3:00; Thursday Women 9:30, then 10:30 and 11:30; Men 9:00, then 10:00 and 11:00. Later positions start as listed or when a court is free. Full table: `data/alta_leagues.json`.
- A line can take 1 to 3 hours (captain's note, not an ALTA rule).
- **Default.** A line is defaulted if a pair is not courtside 20 minutes after its scheduled start. A defaulted match must be the lowest position (Glossary; IV.E).
- Warm-up is limited to 10 minutes (IV.G).

## Eligibility
- **R2 Roster.** Only players on the roster may play; anyone else is ineligible and the team forfeits points from the infraction down (I.I, V.A).
- **R3 One line.** A player plays in only one match per dual meet (I.B).
- **R4 Availability.** Project rule: only players who confirmed they can play are placed.
- **R8 Roster add-ons.** After schedules are posted, at most six players may be added. An added player must be a paid member, with a most recent final level flight at or below the team's level flight, and not on any adult roster for over a year. For a regularly scheduled dual meet she may be added until the scheduled start (I.G.5, I.G.6). Level flights read like AA-3 or A-5. Lower numbers are stronger, in the order AA-1 to AA-3, A-1 to A-8, B-1 to B-8, C-1 to C-8 (order and flight counts confirmed by the captain). "At or below" means the same flight or a weaker one.

## Line order (captain decides, within these limits)
- **R5 Pair movement.** In the regular season a pair may move up or down only one line from the last legal line it played together (III.E).
- **R6 Player movement.** A player without her partner may move up or down two lines from her own last legal line (III.E). Example in the rules: a pair at line 2 may split, one to line 4 and one to line 3; when they play together again they may not play lower than line 3.
- **R7 Sandbagging.** Moving a winning pair down in order to move a losing pair up is prohibited. Winning and losing are judged on results to date: more wins than losses is winning, more losses is losing, even or no record is neither. Penalty: forfeit all points from the point of infraction and below (III.E, III.F).
- **Provisional lineup.** A one-time exception approved by the league vice president when a captain cannot build a legal lineup. Positions are tracked from the previous legal lineup (Captain Handbook).
- A player not on the original lineup may join a match that has not begun. Nobody may be moved down. A player removed from the lineup is ineligible for that dual meet (IV.D).

## Not covered by the MVP
Playoffs (movement rules do not apply; playoff eligibility is two matches; lineups use a win/loss value and the ALTA Lineup Checker), "stronger pair below weaker pair" beyond R7, and Mixed Doubles line composition (not stated in the documents).
