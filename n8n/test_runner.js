// Runs an n8n Code-node file outside n8n, with fake input items.
// Usage: node n8n/test_runner.js <node_file.js> <items.json>
// Prints the node's output items (the .json part of each) as JSON.
const fs = require('fs');

const [, , file, itemsFile] = process.argv;
const code = fs.readFileSync(file, 'utf8');
const items = JSON.parse(fs.readFileSync(itemsFile, 'utf8')).map((json) => ({ json }));
const run = new Function('$input', code); // the node body uses a top-level return, like n8n does
const out = run({ all: () => items });
process.stdout.write(JSON.stringify(out.map((o) => o.json)));
