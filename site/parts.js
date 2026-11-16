// Dependency-free purchasing and export helpers, shared with the tests.
(function (root) {
  "use strict";
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (v) => Number(v).toFixed(2);
  const lineCost = (r) => r.qty > 0 ? Number(r.cost_gbp) : 0;
  function totals(rows) {
    const sum = (g) => rows.filter(r => r.group === g).reduce((n, r) => n + lineCost(r), 0);
    const flight = sum("Flight") + sum("Materials"), ground = sum("Ground");
    return { flight, ground, total: flight + ground };
  }
  function safeCell(value) {
    const s = String(value ?? "");
    return /^[\s]*[=+@-]/.test(s) ? "'" + s : s;
  }
  function exportRows(rows) {
    return [["Group", "Component", "Quantity", "Mass each (g)", "Mass estimated", "Line budget GBP (not unit price)", "Supplier links", "Notes"],
      ...rows.map(r => [r.group, r.name, r.qty, r.group === "Flight" ? r.mass_g : "",
        r.group === "Flight" ? (r.estimate ? "Yes" : "No") : "", money(lineCost(r)),
        r.links.map(l => l.label + ": " + l.url).join(" | "), r.note])];
  }
  function csv(rows) {
    return "\uFEFF" + exportRows(rows).map(row => row.map(s =>
      '"' + safeCell(s).replace(/"/g, '""') + '"').join(",")).join("\r\n") + "\r\n";
  }
  function tsv(rows) {
    return exportRows(rows).map(row => row.map(s => safeCell(s).replace(/[\t\r\n]+/g, " ")).join("\t")).join("\r\n");
  }
  function printDocument(rows, priceNote) {
    const t = totals(rows);
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Asteria parts list</title>' +
      '<style>@page{size:A4 landscape;margin:12mm}body{font:10px/1.4 system-ui;color:#111}h1{font-size:24px}' +
      'table{width:100%;border-collapse:collapse;table-layout:fixed}th,td{text-align:left;padding:7px;border-bottom:1px solid #ddd;vertical-align:top;overflow-wrap:anywhere}' +
      'th:first-child{width:22%}th:nth-child(2){width:9%}th:nth-child(3){width:5%}th:nth-child(4){width:9%}th:nth-child(5){width:29%}' +
      'thead{display:table-header-group}tr{break-inside:avoid}a{color:#17477a}small{display:block}</style></head><body>' +
      '<h1>Asteria · Parts list</h1><p>Exported ' + esc(new Date().toISOString().slice(0, 10)) +
      ' · Flight + recovery £' + money(t.flight) + ' · Ground £' + money(t.ground) + ' · Total £' + money(t.total) + '</p>' +
      '<p>' + esc(priceNote) + '</p><table><thead><tr><th>Component</th><th>Group</th><th>Qty</th><th>Line £</th><th>Supplier links</th><th>Notes</th></tr></thead><tbody>' +
      rows.map(r => '<tr><td>' + esc(r.name) + (r.group === "Flight" ? '<small>' + esc(r.mass_g) + ' g each' + (r.estimate ? ' (estimated)' : '') + '</small>' : '') +
        '</td><td>' + esc(r.group) + '</td><td>' + r.qty + '</td><td>' + money(lineCost(r)) + '</td><td>' +
        r.links.map(l => '<a href="' + esc(l.url) + '">' + esc(l.label) + '</a><small>' + esc(l.url) + '</small>').join('<br>') +
        '</td><td>' + esc(r.note) + '</td></tr>').join("") + '</tbody></table></body></html>';
  }
  const api = { esc, totals, lineCost, csv, tsv, printDocument };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Parts = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
