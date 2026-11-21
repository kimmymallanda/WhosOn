// Does a player's time limit fit a line? A JavaScript copy of src/line_times.py for n8n Code nodes.
// Lines play two per start slot, an hour apart (every adult ALTA league). A line can run 1 to 3 hours,
// so a listed start is the earliest start. n8n/build_nodes.py prepends CONFIG.

const toMin = (hhmm) => {
  const [h, m] = hhmm.split(':');
  return Number(h) * 60 + Number(m);
};

const fmt = (minutes) => {
  const h = Math.floor(minutes / 60) % 24;
  const m = minutes % 60;
  return `${h % 12 || 12}:${String(m).padStart(2, '0')} ${h < 12 ? 'AM' : 'PM'}`;
};

function parseWindow(text) {
  const out = { earliestStart: null, latestEnd: null };
  if (!text) return out;
  const m = /\b(after|until)\s+(\d{1,2}):(\d{2})\b/.exec(String(text).toLowerCase());
  if (m) {
    const minutes = Number(m[2]) * 60 + Number(m[3]);
    if (m[1] === 'after') out.earliestStart = minutes;
    else out.latestEnd = minutes;
  }
  return out;
}

function timeFit(window, line, firstStartMin, config) {
  const start = firstStartMin + 60 * Math.floor((line - 1) / 2);
  const hours = config.line_duration_hours;
  const short = start + Math.trunc(hours.min * 60);
  const long = start + Math.trunc(hours.max * 60);
  const w = parseWindow(window);
  const base = { line, start: fmt(start), ends_if_short: fmt(short), ends_if_long: fmt(long) };
  if (w.earliestStart !== null && start < w.earliestStart) {
    return { ...base, status: 'no', why: `starts at ${fmt(start)}, before ${fmt(w.earliestStart)}` };
  }
  if (w.latestEnd !== null) {
    if (long <= w.latestEnd) return { ...base, status: 'ok', why: `done by ${fmt(long)} even if it runs ${hours.max} hours` };
    if (short <= w.latestEnd) return { ...base, status: 'risky', why: `fits a ${hours.min}-hour line, not a long one` };
    return { ...base, status: 'no', why: `cannot finish by ${fmt(w.latestEnd)}` };
  }
  return { ...base, status: 'ok', why: 'no time limit' };
}
