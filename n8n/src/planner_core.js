// ALTA lineup planner. A JavaScript copy of src/planner.py for n8n Code nodes; see that file for the design.
// Needs rules_core.js and time_fit_core.js above it, plus ROSTER, CONFIG and HISTORY.
// tests/test_n8n_nodes.py checks that this returns exactly what the Python planner returns.

const WEIGHTS = { move: 4, newcomer: 3, new_pair: 6, risky: 12, played: 1, side: 2, rank: 2, reserve: 10 };
const COMPONENTS = ['move', 'newcomer', 'new_pair', 'risky', 'played', 'side', 'rank', 'reserve'];

const cmp = (x, y) => (x < y ? -1 : x > y ? 1 : 0);
const pkey = (pair) => [...pair].sort().join('-');

function makeScorer(roster, config, state, pool, firstStart, windows, baseline, ranking, reserve) {
  const n = config.lines;
  const size = config.players_per_line;
  const side = {};
  for (const p of roster.players) side[p.id] = p.side || 'either';
  const firstMin = toMin(firstStart);

  const fit = {};
  for (const p of pool) for (let line = 1; line <= n; line++) fit[`${p}|${line}`] = timeFit(windows[p] || null, line, firstMin, config);
  const allowed = {};
  for (const p of pool) allowed[p] = allowedLinesForPlayer(p, state, config).filter((line) => fit[`${p}|${line}`].status !== 'no');

  const hasBaseline = !!(baseline && baseline.length);
  const baseLine = {};
  const basePairs = new Set();
  (baseline || []).forEach((pair, i) => {
    for (const p of pair) baseLine[p] = i + 1;
    basePairs.add(pkey(pair));
  });

  const hasRanking = !!(ranking && ranking.length);
  const ideal = {};
  if (hasRanking) {
    const order = ranking.filter((p) => pool.includes(p)).concat(pool.filter((p) => !ranking.includes(p)));
    order.forEach((p, i) => { ideal[p] = Math.min(n, 1 + Math.floor(i / size)); });
  }

  function pairCost(a, b, line) {
    const c = {};
    for (const name of COMPONENTS) c[name] = 0;
    for (const p of [a, b]) {
      c.played += WEIGHTS.played * (state.played[p] || 0);
      if (hasBaseline) {
        if (p in baseLine) c.move += WEIGHTS.move * Math.abs(line - baseLine[p]);
        else c.newcomer += WEIGHTS.newcomer;
      } else if (p in state.lastLine) {
        c.move += WEIGHTS.move * Math.abs(line - state.lastLine[p]);
      }
      if (fit[`${p}|${line}`].status === 'risky') c.risky += WEIGHTS.risky;
      if (hasRanking) c.rank += WEIGHTS.rank * Math.abs(line - ideal[p]);
      if (reserve.has(p)) c.reserve += WEIGHTS.reserve;
    }
    const isNew = hasBaseline ? !basePairs.has(pkey([a, b])) : !(pairKey([a, b]) in state.pairLast);
    if (isNew) c.new_pair += WEIGHTS.new_pair;
    if (side[a] === side[b] && (side[a] === 'ad' || side[a] === 'deuce')) c.side += WEIGHTS.side;
    return c;
  }
  return { fit, allowed, pairCost };
}

function reasonsFor(a, b, line, byId, state, fit, windows) {
  const first = (pid) => byId[pid].name.split(' ')[0];
  const out = [];
  const pk = pairKey([a, b]);
  if (pk in state.pairLast) {
    const last = state.pairLast[pk];
    const [w, l] = state.pairRecord[pk] || [0, 0];
    const rec = w + l ? ` Record together: ${w}-${l}.` : '';
    if (last === line) out.push(`Same pair as before, last played line ${line}.${rec} (R5)`);
    else out.push(`Played together at line ${last}, so line ${line} is one move.${rec} (R5)`);
  } else {
    const parts = [a, b].map((p) => (p in state.lastLine ? `${first(p)} last played line ${state.lastLine[p]}` : `${first(p)} hasn't played this season`));
    out.push(`New pair. ${parts.join(', ')}; line ${line} is within two lines for each. (R6)`);
  }
  for (const p of [a, b]) {
    if (windows[p]) out.push(`${first(p)}: ${fit[`${p}|${line}`].why}.`);
  }
  return out;
}

function plan(roster, config, state, args) {
  const n = config.lines;
  const size = config.players_per_line;
  const windows = args.windows || {};
  const k = args.k === undefined || args.k === null ? 3 : args.k;
  const nodeBudget = args.node_budget === undefined || args.node_budget === null ? 200000 : args.node_budget;
  const byId = {};
  for (const p of roster.players) byId[p.id] = p;
  const reserveSet = new Set(args.reserve || []);
  const excluded = new Set(args.exclude || []);
  const pool = [...new Set([...(args.available || []), ...reserveSet])].filter((p) => !excluded.has(p) && p in byId).sort();
  const fixed = {};
  for (const [line, pair] of Object.entries(args.fixed || {})) fixed[Number(line)] = [...pair].sort();
  const { fit, allowed, pairCost } = makeScorer(roster, config, state, pool, args.first_start, windows, args.baseline, args.ranking, reserveSet);

  const cands = {};
  for (let line = 1; line <= n; line++) {
    const rows = [];
    for (let i = 0; i < pool.length; i++) {
      for (let j = i + 1; j < pool.length; j++) {
        const a = pool[i];
        const b = pool[j];
        if (line in fixed && !(fixed[line][0] === a && fixed[line][1] === b)) continue;
        if (!allowed[a].includes(line) || !allowed[b].includes(line)) continue;
        const pk = pairKey([a, b]);
        if (pk in state.pairLast && Math.abs(line - state.pairLast[pk]) > config.pair_move_limit) continue;
        const comps = pairCost(a, b, line);
        rows.push({ total: COMPONENTS.reduce((s, name) => s + comps[name], 0), a, b, comps });
      }
    }
    rows.sort((x, y) => x.total - y.total || cmp(x.a, y.a) || cmp(x.b, y.b));
    cands[line] = rows;
  }

  let best = [];
  const stats = { nodes: 0, exhausted: false, rejected: {} };
  const poolSet = new Set(pool);

  function dfs(line, used, total, chosen, compsList) {
    if (stats.exhausted) return;
    if (best.length === k && total >= best[best.length - 1].total) return;
    if (line > n) {
      const lineup = chosen.map(([a, b]) => [a, b]);
      const violations = checkLineup(lineup, roster, config, poolSet, state);
      if (violations.length) {
        for (const rid of [...new Set(violations.map((v) => v.rule_id))].sort()) stats.rejected[rid] = (stats.rejected[rid] || 0) + 1;
        return;
      }
      best.push({ total, key: lineup.map((p) => p.join('-')).join(';'), lineup, compsList: [...compsList] });
      best.sort((x, y) => x.total - y.total || cmp(x.key, y.key));
      best = best.slice(0, k);
      return;
    }
    for (const row of cands[line]) {
      stats.nodes += 1;
      if (stats.nodes > nodeBudget) {
        stats.exhausted = true;
        return;
      }
      if (used.has(row.a) || used.has(row.b)) continue;
      dfs(line + 1, new Set([...used, row.a, row.b]), total + row.total, [...chosen, [row.a, row.b]], [...compsList, row.comps]);
    }
  }
  dfs(1, new Set(), 0, [], []);

  const options = best.map((b, idx) => {
    const breakdown = {};
    for (const name of COMPONENTS) breakdown[name] = b.compsList.reduce((s, c) => s + c[name], 0);
    const lines = [];
    const warnings = [];
    b.lineup.forEach(([a, c], i) => {
      const line = i + 1;
      lines.push({
        line,
        start: fit[`${a}|${line}`].start,
        players: [a, c].map((p) => ({ id: p, name: byId[p].name })),
        reasons: reasonsFor(a, c, line, byId, state, fit, windows),
      });
      for (const p of [a, c]) {
        if (fit[`${p}|${line}`].status === 'risky') warnings.push(`${byId[p].name.split(' ')[0]} may have to leave early if line ${line} runs long.`);
        if (reserveSet.has(p)) warnings.push(`${byId[p].name} said she would play only if needed.`);
      }
    });
    const usedIds = new Set(b.lineup.flat());
    return { rank: idx + 1, lineup: b.lineup, score: b.total, breakdown, lines, bench: pool.filter((p) => !usedIds.has(p)), warnings };
  });

  const linesCounts = [];
  for (let line = 1; line <= n; line++) linesCounts.push(cands[line].length);
  let reason = null;
  if (!options.length) {
    const need = n * size;
    if (pool.length < need) reason = `Only ${pool.length} players are available and ${need} are needed.`;
    else if (stats.exhausted) reason = 'The search hit its limit before finding a legal lineup.';
    else if (linesCounts.includes(0)) reason = `No legal pair is available for line ${linesCounts.indexOf(0) + 1}.`;
    else reason = 'No combination of legal pairs works together (for example, the same players are needed on two lines, or sandbagging rule R7 blocks every order).';
  }
  return { options, pool, complete: !stats.exhausted, candidates_per_line: linesCounts, rejected_at_leaf: stats.rejected, none_reason: reason };
}
