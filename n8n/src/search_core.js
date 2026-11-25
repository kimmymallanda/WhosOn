// JavaScript copy of src/rules_search.py, plus the citation check for the model's answer.
// Holds no rulebook text: sections arrive as input. tests/test_rules_search.py compares the two.

const K1 = 1.4, B = 0.6, MIN_SCORE = 2.0;

const STOPWORDS = new Set(`a about an and any are as at be been but by can could do does for from get had has have how i if in
into is it its may many me much must my no not of on or our out shall should so than that the their them then there
these they this to up us we what when where which who will with would you your`.split(/\s+/));

const SYNONYMS = {
  rain: ['inclement', 'weather'], raining: ['inclement', 'weather'], lightning: ['inclement', 'weather'],
  degrees: ['temperature'], hot: ['temperature'], cold: ['temperature'],
  late: ['default'], short: ['default'], sandbagging: ['sandbag'],
  sub: ['roster', 'lineup', 'player'], add: ['added'], sidelines: ['spectators', 'coaching'],
  string: ['racquet'], racket: ['racquet'], penalty: ['forfeit'], lines: ['position'], line: ['position'],
};

function stem(word) {
  for (const suffix of ['ing', 'ed', 'es', 's']) {
    if (word.endsWith(suffix) && word.length - suffix.length >= 3) { word = word.slice(0, -suffix.length); break; }
  }
  const last = word[word.length - 1];
  if (word.length > 3 && last === word[word.length - 2] && last !== 'l' && last !== 's') word = word.slice(0, -1);
  return word.length > 3 && word.endsWith('e') ? word.slice(0, -1) : word;
}

function tokens(text) {
  const words = String(text).toLowerCase().replace(/’/g, "'").replace(/'s/g, '').match(/[a-z0-9]+/g) || [];
  return words.filter((w) => !STOPWORDS.has(w)).map(stem);
}

function queryTerms(question) {
  const terms = new Map(tokens(question).map((t) => [t, 1.0]));
  for (const word of String(question).toLowerCase().match(/[a-z]+/g) || []) {
    for (const extra of SYNONYMS[word] || []) if (!terms.has(stem(extra))) terms.set(stem(extra), 0.5);
  }
  return terms;
}

function search(question, sections, k = 4) {
  const docs = sections.map((s) => {
    const counts = new Map();
    for (const t of tokens(`${s.id} ${s.title} ${s.text}`)) counts.set(t, (counts.get(t) || 0) + 1);
    return counts;
  });
  const lengths = docs.map((d) => [...d.values()].reduce((a, b) => a + b, 0));
  const average = lengths.reduce((a, b) => a + b, 0) / lengths.length;
  const terms = queryTerms(question);
  const scored = [];
  docs.forEach((doc, i) => {
    let score = 0;
    for (const [term, weight] of terms) {
      if (!doc.has(term)) continue;
      const seen = docs.filter((d) => d.has(term)).length;
      const idf = Math.log(1 + (docs.length - seen + 0.5) / (seen + 0.5));
      const tf = doc.get(term);
      score += (weight * idf * tf * (K1 + 1)) / (tf + K1 * (1 - B + (B * lengths[i]) / average));
    }
    if (score >= MIN_SCORE) scored.push({ score, i });
  });
  scored.sort((a, b) => b.score - a.score || a.i - b.i);
  return scored.slice(0, k).map(({ score, i }) => ({ ...sections[i], score: Math.round(score * 1000) / 1000 }));
}

// An answer is only shown if every [citation] is one of the retrieved sections and there is at least one.
function checkAnswer(answer, hits) {
  const cited = [...new Set([...String(answer).matchAll(/\[([^\]]+)\]/g)].map((m) => m[1].trim()))];
  const known = new Map(hits.map((h) => [h.id, h]));
  const ok = cited.length > 0 && cited.every((id) => known.has(id));
  if (!ok) {
    return { ok: false, answer: 'I could not answer this from the ALTA rulebook. Please ask your flight coordinator.', sources: [] };
  }
  return { ok: true, answer: String(answer).trim(), sources: cited.map((id) => ({ id, page: known.get(id).page, text: known.get(id).text })) };
}
