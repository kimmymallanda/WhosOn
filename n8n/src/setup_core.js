// Checks for the captain's setup page: league and season, roster upload, schedule upload.
// This logic exists only as JavaScript (it runs in n8n Code nodes). tests/test_setup_import.py runs it in Node.js.
// n8n/build_nodes.py prepends LEAGUES (and LEVELS) from data/alta_leagues.json.
//
// Every check returns problems of two kinds. An "error" blocks the upload until the captain fixes the file.
// A "warning" is shown but does not block (for example, fewer players than the league minimum).

const norm = (s) => String(s === null || s === undefined ? '' : s).toLowerCase().replace(/[^a-z0-9]/g, '');
const clean = (v) => (v === null || v === undefined ? '' : String(v).trim());
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

// ---------------------------------------------------------------- league and season

function fmt12(hhmm) {
  const [h, m] = hhmm.split(':').map(Number);
  return `${h % 12 || 12}:${String(m).padStart(2, '0')} ${h < 12 ? 'AM' : 'PM'}`;
}

function joinList(items) {
  if (items.length <= 1) return items.join('');
  return `${items.slice(0, -1).join(', ')} or ${items[items.length - 1]}`;
}

function leagueCheck(league, season, levelFlight) {
  const lg = LEAGUES[league];
  if (!lg) return { ok: false, error: `I don't know the league "${league}". Pick one from the list.` };
  if (!lg.seasons.includes(season)) {
    return { ok: false, error: `${league} plays in ${joinList(lg.seasons)}, not ${season}. Pick the right season, or a different league.` };
  }
  let level = null;
  if (clean(levelFlight) !== '') {
    const p = parseLevelFlight(levelFlight);
    if (!p || p.flight === null) {
      return { ok: false, error: `"${clean(levelFlight)}" is not a level flight like AA-3 or A-5. AA has flights 1 to 3, and A, B and C have flights 1 to 8.` };
    }
    level = `${p.level}-${p.flight}`;
  }
  const times = lg.start_times.map(fmt12);
  const slots = [];
  for (let i = 0; i < times.length; i++) {
    const first = 2 * i + 1;
    const last = Math.min(2 * i + 2, lg.lines);
    slots.push(`${first === last ? 'line ' + first : 'lines ' + first + '-' + last} at ${times[i]}`);
  }
  return {
    ok: true,
    league,
    season,
    day: lg.day,
    lines: lg.lines,
    start_times: times,
    roster_min: lg.roster_min,
    level_flight: level,
    summary: `${league} plays on ${lg.day}s in the ${season} season: ${lg.lines} doubles lines (${slots.join(', ')}). A team needs at least ${lg.roster_min} players on its roster.${level ? ` Your team is ${level}.` : ''}`,
  };
}

// ---------------------------------------------------------------- reading a spreadsheet

function unionKeys(rows) {
  const keys = [];
  for (const r of rows) for (const k of Object.keys(r)) if (!keys.includes(k)) keys.push(k);
  return keys;
}

function mapColumns(keys, aliases) {
  const map = {};
  for (const key of keys) {
    const n = norm(key);
    for (const [field, names] of Object.entries(aliases)) {
      if (names.includes(n) && !(field in map)) map[field] = key;
    }
  }
  return map;
}

const isBlankRow = (r) => Object.values(r).every((v) => clean(v) === '');

function makeProblems() {
  const list = [];
  return { list, add: (severity, row, field, message) => list.push({ severity, row, field, message }) };
}

// ---------------------------------------------------------------- roster

const ROSTER_ALIASES = {
  name: ['name', 'playername', 'player', 'fullname'],
  first: ['firstname', 'first'],
  last: ['lastname', 'last', 'surname'],
  email: ['email', 'emailaddress', 'mail', 'playeremail'],
  mobile: ['mobile', 'mobilenumber', 'mobilephone', 'cell', 'cellphone', 'cellnumber', 'phone', 'phonenumber'],
  level_flight: ['levelflight', 'level', 'rating', 'flight', 'altalevel', 'altalevelflight', 'finallevelflight'],
  side: ['side', 'preferredside', 'courtside', 'preferredcourtside'],
};

function parseLevelFlight(text) {
  const m = /^\s*(AA|A|B|C)\s*-?\s*(\d)?\s*$/.exec(String(text || '').toUpperCase());
  if (!m) return null;
  const flight = m[2] ? Number(m[2]) : null;
  if (flight !== null && !(flight >= 1 && flight <= LEVELS.flights[m[1]])) return null;
  return { level: m[1], flight };
}

function normalizePhone(text) {
  const digits = String(text).replace(/\D/g, '');
  if (digits.length === 10) return `+1${digits}`;
  if (digits.length === 11 && digits[0] === '1') return `+${digits}`;
  return null;
}

function normalizeSide(text) {
  const s = norm(text);
  if (['', 'either', 'any', 'both', 'eitherside'].includes(s)) return 'either';
  if (['ad', 'adcourt', 'adside', 'a'].includes(s)) return 'ad';
  if (['deuce', 'deucecourt', 'deuceside', 'd'].includes(s)) return 'deuce';
  return null;
}

function parseRoster(rows, ctx) {
  const { list: problems, add } = makeProblems();
  const real = rows.filter((r) => !isBlankRow(r));
  const map = mapColumns(unionKeys(real), ROSTER_ALIASES);
  const hasName = map.name || (map.first && map.last);
  if (!hasName) add('error', null, 'name', 'I could not find a "Name" column (or "First Name" and "Last Name").');
  if (!map.email) add('error', null, 'email', 'I could not find an "Email" column. Players are reached by email, so every player needs one.');
  if (!hasName || !map.email) return summarize({ players: [] }, problems, real.length); // nothing to read without these columns

  const players = [];
  const seenEmail = {};
  const seenName = {};
  rows.forEach((r, i) => {
    if (isBlankRow(r)) return;
    const rowNo = i + 2; // row 1 is the heading row
    const name = map.name ? clean(r[map.name]) : [clean(r[map.first]), clean(r[map.last])].filter(Boolean).join(' ');
    const email = map.email ? clean(r[map.email]).toLowerCase() : '';
    let bad = false;
    if (hasName && !name) { add('error', rowNo, 'name', 'This row has no name.'); bad = true; }
    if (map.email) {
      if (!email) { add('error', rowNo, 'email', `${name || 'This player'} has no email address.`); bad = true; }
      else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { add('error', rowNo, 'email', `${name || 'This player'}'s email "${email}" does not look right.`); bad = true; }
      else if (seenEmail[email]) { add('error', rowNo, 'email', `${email} is already used in row ${seenEmail[email]}.`); bad = true; }
    }
    if (name && seenName[norm(name)]) add('warning', rowNo, 'name', `${name} appears twice (also in row ${seenName[norm(name)]}). Is that two different players?`);
    if (bad) return;
    seenEmail[email] = rowNo;
    if (name) seenName[norm(name)] = rowNo;

    let mobile = null;
    if (map.mobile && clean(r[map.mobile])) {
      mobile = normalizePhone(r[map.mobile]);
      if (!mobile) add('warning', rowNo, 'mobile', `${name}'s number "${clean(r[map.mobile])}" is not a 10-digit US number, so I left it out.`);
    }
    let level = null;
    if (map.level_flight && clean(r[map.level_flight])) {
      const p = parseLevelFlight(r[map.level_flight]);
      if (p) level = p.flight ? `${p.level}-${p.flight}` : p.level;
      else add('warning', rowNo, 'level_flight', `${name}'s level "${clean(r[map.level_flight])}" is not an ALTA level like AA-3 or A-5, so I left it out.`);
    }
    let side = 'either';
    if (map.side) {
      const s = normalizeSide(r[map.side]);
      if (s === null) add('warning', rowNo, 'side', `${name}'s side "${clean(r[map.side])}" is not ad, deuce or either. I used either.`);
      else side = s;
    }
    players.push({ name, email, mobile, level_flight: level, side });
  });

  if (ctx && ctx.roster_min && players.length < ctx.roster_min) {
    add('warning', null, 'count', `I found ${players.length} players. ${ctx.league || 'This league'} needs at least ${ctx.roster_min} on a roster. You can continue, but check nobody is missing.`);
  }
  return summarize({ players }, problems, real.length);
}

// ---------------------------------------------------------------- schedule

const SCHEDULE_ALIASES = {
  date: ['date', 'matchdate', 'day', 'when', 'matchday'],
  opponent: ['opponent', 'opposingteam', 'opposition', 'vs', 'against', 'team', 'opponentteam'],
  home_away: ['homeaway', 'homeoraway', 'ha', 'homeaway', 'homeoraway', 'homeoraway'],
  facility: ['facility', 'location', 'courts', 'site', 'venue', 'where'],
};
const COLUMN_LABEL = { date: 'Date', opponent: 'Opponent', home_away: 'Home/Away' };

const MONTHS = { jan: 1, january: 1, feb: 2, february: 2, mar: 3, march: 3, apr: 4, april: 4, may: 5, jun: 6, june: 6, jul: 7, july: 7, aug: 8, august: 8, sep: 9, sept: 9, september: 9, oct: 10, october: 10, nov: 11, november: 11, dec: 12, december: 12 };
const DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

function makeDate(y, m, d) {
  if (!y || !m || !d) return null;
  const dt = new Date(Date.UTC(y, m - 1, d));
  if (dt.getUTCFullYear() !== y || dt.getUTCMonth() !== m - 1 || dt.getUTCDate() !== d) return null;
  return `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
}

function parseDate(value, defaultYear) {
  if (value === null || value === undefined || clean(value) === '') return null;
  const s = clean(value);
  if (typeof value === 'number' || /^\d{5}(\.\d+)?$/.test(s)) {
    const n = Number(value);
    if (n > 20000 && n < 80000) { // an Excel date number
      const dt = new Date(Date.UTC(1899, 11, 30) + Math.floor(n) * 86400000);
      return makeDate(dt.getUTCFullYear(), dt.getUTCMonth() + 1, dt.getUTCDate());
    }
  }
  let m = /^(\d{4})-(\d{1,2})-(\d{1,2})/.exec(s);
  if (m) return makeDate(Number(m[1]), Number(m[2]), Number(m[3]));
  m = /^(\d{1,2})\/(\d{1,2})\/(\d{2,4})$/.exec(s);
  if (m) return makeDate(Number(m[3]) < 100 ? 2000 + Number(m[3]) : Number(m[3]), Number(m[1]), Number(m[2]));
  m = /^(?:[A-Za-z]+,?\s+)?([A-Za-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?$/.exec(s);
  if (m && MONTHS[m[1].toLowerCase()]) return makeDate(m[3] ? Number(m[3]) : defaultYear, MONTHS[m[1].toLowerCase()], Number(m[2]));
  return null;
}

const weekdayOf = (iso) => new Date(`${iso}T00:00:00Z`).getUTCDay();
const prettyDate = (iso) => `${MONTH_NAMES[Number(iso.slice(5, 7)) - 1]} ${Number(iso.slice(8, 10))}`;

function normalizeHomeAway(text) {
  const s = norm(text);
  if (['home', 'h'].includes(s)) return 'home';
  if (['away', 'a', 'visitor', 'visiting', 'v', 'at'].includes(s) || String(text).trim() === '@') return 'away';
  return null;
}

function warnMatchCount(matches, add) {
  if (matches.length && matches.length !== 6 && matches.length !== 7) {
    add('warning', null, 'count', `I found ${matches.length} matches. An ALTA regular season is usually 6 or 7 matches. Check that none are missing.`);
  }
}

function parseSchedule(rows, ctx) {
  const { list: problems, add } = makeProblems();
  const lg = LEAGUES[ctx.league];
  const real = rows.filter((r) => !isBlankRow(r));
  const map = mapColumns(unionKeys(real), SCHEDULE_ALIASES);
  for (const need of ['date', 'opponent', 'home_away']) {
    if (!map[need]) add('error', null, need, `I could not find a "${COLUMN_LABEL[need]}" column.`);
  }
  if (problems.length) return summarize({ matches: [] }, problems, real.length); // nothing to read without these columns
  const matches = [];
  const seenDate = {};
  rows.forEach((r, i) => {
    if (isBlankRow(r)) return;
    const rowNo = i + 2;
    let bad = false;
    const iso = map.date ? parseDate(r[map.date], ctx.year) : null;
    if (map.date) {
      if (!iso) {
        add('error', rowNo, 'date', clean(r[map.date]) === '' ? 'This row has no date.' : `I could not read the date "${clean(r[map.date])}". Try a format like 2027-04-11 or 4/11/2027.`);
        bad = true;
      } else if (seenDate[iso]) { add('error', rowNo, 'date', `${prettyDate(iso)} is already used in row ${seenDate[iso]}.`); bad = true; }
    }
    const opponent = map.opponent ? clean(r[map.opponent]) : '';
    if (map.opponent && !opponent) { add('error', rowNo, 'opponent', `${iso ? prettyDate(iso) : 'This row'} has no opponent.`); bad = true; }
    let homeAway = null;
    if (map.home_away) {
      homeAway = normalizeHomeAway(r[map.home_away]);
      if (!homeAway) { add('error', rowNo, 'home_away', `${iso ? prettyDate(iso) : 'This row'}: "${clean(r[map.home_away])}" is not Home or Away.`); bad = true; }
    }
    if (bad) return;
    seenDate[iso] = rowNo;
    if (lg && weekdayOf(iso) !== DAY_NAMES.indexOf(lg.day)) {
      add('warning', rowNo, 'date', `${prettyDate(iso)} is a ${DAY_NAMES[weekdayOf(iso)]}, but ${ctx.league} plays on ${lg.day}s. That is fine if this match was moved.`);
    }
    matches.push({ date: iso, opponent, home_away: homeAway, facility: map.facility ? clean(r[map.facility]) || null : null });
  });
  matches.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
  matches.forEach((m, idx) => { m.week = idx + 1; });
  warnMatchCount(matches, add);
  return summarize({ matches }, problems, real.length);
}


// ---------------------------------------------------------------- schedule from ALTA's PDF

// ALTA's printed division schedule: a list of teams (number, facility, captains), then one line per Sunday
// with the pairings ("Team 8 at Team 1" means Team 1 is home). The captain tells us (or we match from her name)
// which team she is. Needs the text of the PDF, not a picture of it.
const SEASON_NAMES = ['Winter', 'Spring', 'Summer', 'Fall'];

function pdfTeams(lines) {
  const teams = {};
  let current = null;
  for (const line of lines) {
    if (/^(Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday),/.test(line)) break;
    const t = /^(\d{1,2})\s+(.+),\s*(.+)$/.exec(line);
    if (t) {
      const words = t[2].split(' ');
      const last = words.pop();
      current = { facility: words.join(' ').trim(), captains: [`${last}, ${t[3]}`.trim()] };
      teams[Number(t[1])] = current;
    } else if (current && /^[^\d]+,\s*[^\d]+$/.test(line) && !/^Team #/.test(line)) {
      current.captains.push(line);
    }
  }
  return teams;
}

// "KIDD, HANNAH" and "Hannah Kidd" are the same person.
function samePerson(pdfName, captainName) {
  const m = /^(.+),\s*(.+)$/.exec(pdfName);
  if (!m) return false;
  const want = norm(`${m[2]} ${m[1]}`);
  const parts = String(captainName || '').trim().split(/\s+/);
  return parts.length >= 2 && (norm(parts.join(' ')) === want || norm(`${parts[0]} ${parts[parts.length - 1]}`) === want);
}

function parseSchedulePdf(text, ctx) {
  const { list: problems, add } = makeProblems();
  const lines = String(text || '').replace(/\r/g, '').split('\n').map((l) => l.replace(/\s+/g, ' ').trim()).filter(Boolean);
  const flat = lines.join(' ');
  const done = (matches, extra) => summarize({ matches, ...(extra || {}) }, problems, matches.length);

  const dateRe = /(Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday),\s+([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})((?:\s+Team\s+\d+\s+at\s+Team\s+\d+)+)/g;
  const weeks = [];
  let dm;
  while ((dm = dateRe.exec(flat))) {
    const iso = MONTHS[dm[2].toLowerCase()] ? makeDate(Number(dm[4]), MONTHS[dm[2].toLowerCase()], Number(dm[3])) : null;
    const pairs = [...dm[5].matchAll(/Team\s+(\d+)\s+at\s+Team\s+(\d+)/g)].map((p) => ({ away: Number(p[1]), home: Number(p[2]) }));
    if (iso) weeks.push({ iso, pairs });
  }
  if (!weeks.length) {
    add('error', null, 'file', 'I could not find any matches in this PDF. It should be the printed division schedule from the ALTA site (with lines like "Sunday, September 13, 2026 Team 8 at Team 1"). If it is a scan or a photo, upload an Excel or CSV file instead.');
    return done([]);
  }

  const title = /(\d{4})\s+(Fall|Spring|Winter|Summer)\s+(.+?)\s+Schedule/i.exec(flat);
  if (title) {
    const league = title[3].trim();
    const season = title[2][0].toUpperCase() + title[2].slice(1).toLowerCase();
    if (ctx.league && norm(league) !== norm(ctx.league)) add('error', null, 'league', `This PDF is for ${league}, but you set up ${ctx.league}. Upload the right schedule, or start again with the right league.`);
    if (ctx.season && norm(season) !== norm(ctx.season)) add('error', null, 'season', `This PDF is for the ${season} season, but you set up ${ctx.season}.`);
    if (ctx.year && Number(title[1]) !== Number(ctx.year)) add('error', null, 'year', `This PDF is for ${title[1]}, but you set up ${ctx.year}.`);
  } else {
    add('warning', null, 'title', 'I could not read the league and season at the top of the PDF, so I could not check they match your setup.');
  }
  const lvl = /\b(AA|A|B|C)-(\d)\s*,?\s*Division\s+(\d+)\s+of\s+(\d+)/i.exec(flat);
  if (lvl && ctx.level_flight && norm(`${lvl[1]}-${lvl[2]}`) !== norm(ctx.level_flight)) {
    add('warning', null, 'level_flight', `This PDF is for ${lvl[1].toUpperCase()}-${lvl[2]}, but you set up ${ctx.level_flight}.`);
  }

  const teams = pdfTeams(lines);
  const teamList = Object.keys(teams).map(Number).sort((a, b) => a - b);
  let me = ctx.team_no !== undefined && ctx.team_no !== null && clean(ctx.team_no) !== '' ? Number(ctx.team_no) : null;
  if (me !== null && !weeks.some((w) => w.pairs.some((p) => p.home === me || p.away === me))) {
    add('error', null, 'team_no', `Team ${clean(ctx.team_no)} does not play in this schedule. Check your team number in the team list at the top of the PDF.`);
    return done([], { teams });
  }
  if (me === null) {
    const found = teamList.filter((n) => teams[n].captains.some((c) => samePerson(c, ctx.captain_name)));
    if (found.length === 1) {
      me = found[0];
      add('warning', null, 'team_no', `I matched you to Team ${me} (${teams[me].facility}) from your name. If that is wrong, upload again and type your team number.`);
    } else {
      const list = teamList.length ? teamList.map((n) => `Team ${n}: ${teams[n].facility} (${teams[n].captains[0]})`).join('; ') : 'see the team list at the top of the PDF';
      add('error', null, 'team_no', `Which team are you? Upload the PDF again and type your team number. ${list}.`);
      return done([], { teams });
    }
  }

  const matches = [];
  for (const w of weeks) {
    const pair = w.pairs.find((p) => p.home === me || p.away === me);
    if (!pair) { add('warning', null, 'bye', `${prettyDate(w.iso)}: Team ${me} has no match (a bye week), so I left it out.`); continue; }
    const home = pair.home === me;
    const opp = home ? pair.away : pair.home;
    const host = teams[pair.home];
    matches.push({
      date: w.iso,
      opponent: `Team ${opp}${teams[opp] ? ` (${teams[opp].facility})` : ''}`,
      home_away: home ? 'home' : 'away',
      facility: host ? host.facility : null,
    });
    const lg = LEAGUES[ctx.league];
    if (lg && weekdayOf(w.iso) !== DAY_NAMES.indexOf(lg.day)) add('warning', null, 'date', `${prettyDate(w.iso)} is a ${DAY_NAMES[weekdayOf(w.iso)]}, but ${ctx.league} plays on ${lg.day}s.`);
  }
  matches.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
  matches.forEach((m, idx) => { m.week = idx + 1; });
  warnMatchCount(matches, add);
  return done(matches, { team_no: me });
}

// ---------------------------------------------------------------- results and report

function summarize(data, problems, rowsRead) {
  const errors = problems.filter((p) => p.severity === 'error').length;
  const warnings = problems.length - errors;
  return { ...data, problems, summary: { rows_read: rowsRead, errors, warnings, ok: errors === 0 } };
}

function renderReport(title, result, listHtml) {
  const items = result.problems.map((p) => {
    const where = p.row ? `Row ${p.row}: ` : '';
    return `<li><b>${p.severity === 'error' ? 'Fix' : 'Check'}</b> ${esc(where + p.message)}</li>`;
  });
  const head = result.summary.ok
    ? `<p>${esc(title)} looks good: ${result.summary.errors} problems to fix, ${result.summary.warnings} things to double-check.</p>`
    : `<p>${esc(title)} needs ${result.summary.errors} fix${result.summary.errors === 1 ? '' : 'es'} before I can use it. Nothing was saved. Fix the file and upload it again.</p>`;
  return `${head}${items.length ? `<ul>${items.join('')}</ul>` : ''}${listHtml || ''}`;
}

function rosterTable(players) {
  const rows = players.map((p) => `<tr><td>${esc(p.name)}</td><td>${esc(p.email)}</td><td>${esc(p.mobile || '')}</td><td>${esc(p.level_flight || '')}</td><td>${esc(p.side)}</td></tr>`);
  return `<table border="1" cellpadding="6" style="border-collapse:collapse"><tr><th>Name</th><th>Email</th><th>Mobile</th><th>Level</th><th>Side</th></tr>${rows.join('')}</table>`;
}

function scheduleTable(matches) {
  const rows = matches.map((m) => `<tr><td>${m.week}</td><td>${esc(prettyDate(m.date))}</td><td>${esc(m.opponent)}</td><td>${m.home_away}</td><td>${esc(m.facility || '')}</td></tr>`);
  return `<table border="1" cellpadding="6" style="border-collapse:collapse"><tr><th>Week</th><th>Date</th><th>Opponent</th><th>Home/Away</th><th>Facility</th></tr>${rows.join('')}</table>`;
}

function checkRoster(rows, ctx) {
  const res = parseRoster(rows, ctx);
  return { ...res, report_html: renderReport('Your roster', res, res.players.length ? rosterTable(res.players) : '') };
}

function checkSchedule(rows, ctx) {
  const res = ctx.pdf_text !== undefined && ctx.pdf_text !== null ? parseSchedulePdf(ctx.pdf_text, ctx) : parseSchedule(rows, ctx);
  return { ...res, report_html: renderReport('Your schedule', res, res.matches.length ? scheduleTable(res.matches) : '') };
}
