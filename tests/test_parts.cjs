const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const Parts = require("../site/parts.js");
const row = (group, qty, cost_gbp) => ({
  group, qty, cost_gbp, name: 'A "quoted", component\nsecond line', mass_g: 1,
  estimate: true, note: "=potential formula",
  links: [{ label: "Amazon search", url: "https://www.amazon.co.uk/s?k=Pico" }]
});
test("pack budgets counted once; zero quantity excluded", () => {
  assert.deepEqual(Parts.totals([row("Flight", 7, 18.22), row("Ground", 2, 10), row("Materials", 1, 11.57), row("Flight", 0, 20)]),
    { flight: 29.79, ground: 10, total: 39.79 });
});
test("CSV preserves URLs, quotes, multiline names, all groups and safe cells", () => {
  const csv = Parts.csv([row("Flight", 7, 18.22), row("Ground", 1, 10), row("Materials", 1, 11.57)]);
  assert.ok(csv.startsWith("\uFEFF"));
  assert.ok(csv.includes('A ""quoted"", component\nsecond line'));
  assert.ok(csv.includes("https://www.amazon.co.uk/s?k=Pico"));
  assert.ok(csv.includes("'=potential formula"));
  assert.ok(csv.includes('"Ground"') && csv.includes('"Materials"'));
  assert.ok(csv.includes('"18.22"'));
});
test("spreadsheet paste has stable columns", () => {
  for (const line of Parts.tsv([row("Flight", 1, 5)]).split("\r\n")) assert.equal(line.split("\t").length, 8);
});
test("print has clickable URLs and escaped component text", () => {
  const r = row("Flight", 1, 1); r.name = '<script>alert("x")</script>';
  const html = Parts.printDocument([r], "Budget, not live prices");
  assert.ok(!html.includes("<script>"));
  assert.ok(html.includes('href="https://www.amazon.co.uk/s?k=Pico"'));
  assert.ok(html.includes("Budget, not live prices"));
});
test("tabs have unique panels and scripts exist", () => {
  const html = fs.readFileSync(require.resolve("../site/index.html"), "utf8");
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(m => m[1]);
  assert.equal(ids.length, new Set(ids).size);
  const panels = [...html.matchAll(/aria-controls="([^"]+)"/g)].map(m => m[1]);
  assert.equal(panels.length, 5);
  panels.forEach(id => assert.ok(ids.includes(id)));
  [...html.matchAll(/<script src="([^"]+)"/g)].forEach(m =>
    assert.ok(fs.existsSync(require("node:path").join(__dirname, "../site", m[1]))));
});
