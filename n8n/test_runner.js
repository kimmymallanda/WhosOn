// Runs an n8n Code-node file outside n8n, with fake input items.
// Usage: node n8n/test_runner.js <node_file.js> <items.json> [other_nodes.json]
// other_nodes.json (optional) maps a node name to its output, for code that calls $('Node name').first().json.
// Prints the node's output items (the .json part of each) as JSON.
const fs = require('fs');

const [, , file, itemsFile, otherFile] = process.argv;
const code = fs.readFileSync(file, 'utf8');
const items = JSON.parse(fs.readFileSync(itemsFile, 'utf8')).map((json) => ({ json }));
const others = otherFile ? JSON.parse(fs.readFileSync(otherFile, 'utf8')) : {};
const dollar = (name) => {
  if (!(name in others)) throw new Error(`No fake output for node "${name}"`);
  const list = [].concat(others[name]).map((json) => ({ json }));
  return { first: () => list[0], all: () => list };
};
const run = new Function('$input', '$', code); // the node body uses a top-level return, like n8n does
const out = run({ all: () => items, first: () => items[0] }, dollar);
process.stdout.write(JSON.stringify(out.map((o) => o.json)));
