"""Generate a standalone HTML viewer for a prism-annotator annotation run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from prism_annotator.models import AnnotatedDocument, load_results
from prism_annotator.output import _align_entities
from prism_annotator.schema import (
    ENTITY_TYPES,
    TEMPORAL_RELATIONS,
)

# ── Colour palette (PRISM specification) ─────────────────────────────────────

ENTITY_COLORS: dict[str, str] = {
    "d": "#FF1B1C",
    "a": "#FF7F11",
    "f": "#247BA0",
    "c": "#008148",
    "TIMEX3": "#A14A86",
    "t-test": "#FFFD82",
    "t-key": "#FFFD82",
    "t-val": "#F786AA",
    "m-key": "#F786AA",
    "m-val": "#F786AA",
    "r": "#B8B8D1",
    "cc": "#562C2C",
    "p": "#E0E0E0",
}

LIGHT_TEXT_TYPES = {"d", "f", "c", "TIMEX3", "cc"}

TAG_ABBREV: dict[str, str] = {
    "d": "D", "a": "A", "f": "F", "c": "C", "TIMEX3": "時",
    "t-test": "Tt", "t-key": "Tk", "t-val": "Tv",
    "m-key": "Mk", "m-val": "Mv", "r": "R", "cc": "CC", "p": "P",
}

ATTR_SHORTHAND: dict[str, str] = {
    "positive": "+", "negative": "-", "suspicious": "?", "general": "*",
    "executed": "+", "negated": "-", "scheduled": "予", "other": "他",
}

TIMEX3_TYPE_SHORTHAND: dict[str, str] = {
    "DATE": "DATE", "TIME": "TIME", "DURATION": "DUR", "SET": "SET",
    "AGE": "AGE", "MED": "MED", "MISC": "MISC",
}


# ── Relation resolution ──────────────────────────────────────────────────────

TEMPORAL_REL_NAMES = set(TEMPORAL_RELATIONS.keys())



# ── Document data serialisation ──────────────────────────────────────────────


def prepare_doc_data(doc: AnnotatedDocument) -> dict:
    """Prepare a single AnnotatedDocument for JSON embedding in the viewer."""
    aligned = _align_entities(doc.text, doc.entities)
    aligned_map: dict[int, tuple[int, int]] = {idx: (s, e) for s, e, idx in aligned}
    ents = []
    for i, ent in enumerate(doc.entities):
        se = aligned_map.get(i)
        start = se[0] if se else None
        end = se[1] if se else None

        ents.append({
            "cls": ent.label,
            "text": ent.text,
            "start": start,
            "end": end,
            "attrs": ent.attributes,
        })

    temporal = TEMPORAL_REL_NAMES
    relations: list[dict] = []
    for rel in doc.relations:
        try:
            from_idx = int(rel.from_eid.removeprefix("e")) - 1
            to_idx = int(rel.to_eid.removeprefix("e")) - 1
        except (ValueError, IndexError):
            continue
        if not (0 <= from_idx < len(ents) and 0 <= to_idx < len(ents)):
            continue
        cat = "temporal" if rel.rel_type in temporal else "medical"
        relations.append({"from": from_idx, "to": to_idx, "type": rel.rel_type, "cat": cat})

    return {
        "id": doc.doc_id,
        "text": doc.text,
        "entities": ents,
        "relations": relations,
    }


# ── HTML generation ──────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>prism-annotator Viewer — %(run_name)s</title>
<style>
:root {
  --sidebar-w: 280px;
  --font-ja: "Noto Sans JP", "Hiragino Sans", "Yu Gothic", sans-serif;
%(color_vars)s
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: var(--font-ja); font-size: 14px; display: flex; height: 100vh; overflow: hidden; color: #333; }

/* Sidebar (col 1) */
#sidebar { width: var(--sidebar-w); min-width: var(--sidebar-w); background: #f5f5f5; border-right: 1px solid #ddd; display: flex; flex-direction: column; overflow: hidden; }
#stats { padding: 12px; border-bottom: 1px solid #ddd; font-size: 12px; line-height: 1.6; }
#stats h2 { font-size: 13px; margin-bottom: 4px; }
#stats .stat-row { display: flex; justify-content: space-between; }
#doc-search { margin: 8px; padding: 6px 8px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; }
#doc-list { flex: 1; overflow-y: auto; list-style: none; }
#doc-list li { padding: 6px 12px; cursor: pointer; font-size: 12px; border-bottom: 1px solid #eee; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
#doc-list li:hover { background: #e3f2fd; }
#doc-list li.active { background: #bbdefb; font-weight: 600; }

/* Centre column (col 2): legend + annotated text */
#centre { flex: 1; display: flex; flex-direction: column; overflow: hidden; min-width: 0; }
#legend-bar { padding: 6px 12px; background: #fafafa; border-bottom: 1px solid #ddd; display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
.legend-item { display: inline-flex; align-items: center; gap: 3px; font-size: 11px; padding: 2px 6px; border-radius: 3px; cursor: pointer; user-select: none; border: 1px solid transparent; }
.legend-item.off { opacity: 0.3; text-decoration: line-through; }
.legend-item .swatch { width: 12px; height: 12px; border-radius: 2px; border: 1px solid #aaa; }
#doc-header { font-size: 14px; font-weight: 600; padding: 8px 12px; border-bottom: 1px solid #eee; background: #fff; }
#text-panel { flex: 1; overflow-y: auto; line-height: 2.4; padding: 12px; background: #fff; white-space: pre-wrap; word-break: break-all; font-size: 14px; }

/* Entity spans */
.ent { border-radius: 5px; padding: 1px 0.2em; position: relative; cursor: pointer; font-weight: 600; margin: 0 0.1em; display: inline; }
.ent.hl { outline: 2.5px solid #d32f2f; outline-offset: 1px; z-index: 2; }
.ent.hl-partner { outline: 2.5px solid #1565c0; outline-offset: 1px; z-index: 1; }
.ent.hidden-type { background: transparent !important; color: inherit !important; cursor: default; outline: none !important; }
.ent.hidden-type .tag { display: none; }
.tag { font-size: 9px; font-weight: 600; margin-right: 0.15em; padding: 0.05em 0.2em; border-radius: 3px; border: 1px solid currentColor; vertical-align: 15%%; white-space: nowrap; }

/* Tooltip */
.ent-tooltip { display: none; position: absolute; bottom: calc(100%% + 6px); left: 0; background: #333; color: #fff; font-size: 11px; font-weight: 400; padding: 4px 8px; border-radius: 4px; white-space: nowrap; z-index: 100; pointer-events: none; }
.ent:hover .ent-tooltip { display: block; }

/* Right panel (col 3): tabbed tables */
#right-panel { width: 420px; min-width: 320px; border-left: 1px solid #ddd; display: flex; flex-direction: column; overflow: hidden; background: #fff; }
#tab-bar { display: flex; border-bottom: 1px solid #ddd; background: #fafafa; }
.tab-btn { flex: 1; padding: 8px 0; text-align: center; font-size: 12px; font-weight: 600; cursor: pointer; border: none; background: transparent; border-bottom: 2px solid transparent; color: #666; }
.tab-btn:hover { color: #333; background: #f0f0f0; }
.tab-btn.active { color: #1565c0; border-bottom-color: #1565c0; }
.tab-content { flex: 1; overflow-y: auto; padding: 8px; display: none; }
.tab-content.active { display: block; }

/* Tables */
table { width: 100%%; border-collapse: collapse; font-size: 12px; }
th { background: #f5f5f5; text-align: left; padding: 4px 6px; border: 1px solid #e0e0e0; font-weight: 600; position: sticky; top: 0; z-index: 1; }
td { padding: 4px 6px; border: 1px solid #e0e0e0; vertical-align: top; }
tr.rel-row:hover { background: #e3f2fd; cursor: pointer; }
tr.rel-row.hl { background: #bbdefb; }
tr.ent-row:hover { background: #f5f5f5; cursor: pointer; }
tr.ent-row.hl { background: #fff9c4; }
.not-found { color: #999; font-style: italic; }
.ent-count { font-size: 10px; color: #777; margin-left: 4px; }
</style>
</head>
<body>

<div id="sidebar">
  <div id="stats"></div>
  <input id="doc-search" type="text" placeholder="Search documents...">
  <ul id="doc-list"></ul>
</div>

<div id="centre">
  <div id="legend-bar"></div>
  <div id="doc-header"></div>
  <div id="text-panel"></div>
</div>

<div id="right-panel">
  <div id="tab-bar">
    <button class="tab-btn active" data-tab="relations" onclick="switchTab('relations')">Relations</button>
    <button class="tab-btn" data-tab="entities" onclick="switchTab('entities')">Entities</button>
  </div>
  <div id="relations-section" class="tab-content active"></div>
  <div id="entities-section" class="tab-content"></div>
</div>

<script>
const DATA = %(data_json)s;
const ENTITY_TYPES = %(entity_types_json)s;
const ENTITY_COLORS = %(entity_colors_json)s;
const LIGHT_TEXT_TYPES = new Set(%(light_text_types_json)s);
const TAG_ABBREV = %(tag_abbrev_json)s;
const ATTR_SHORTHAND = %(attr_shorthand_json)s;
const TIMEX3_TYPE_SHORTHAND = %(timex3_type_shorthand_json)s;

function buildTagLabel(e) {
  let base = TAG_ABBREV[e.cls] || e.cls;
  let suffix = "";
  if (e.cls === "TIMEX3" && e.attrs.type) {
    suffix = TIMEX3_TYPE_SHORTHAND[e.attrs.type] || e.attrs.type;
  } else if (e.attrs.certainty) {
    suffix = ATTR_SHORTHAND[e.attrs.certainty] || e.attrs.certainty;
  } else if (e.attrs.state) {
    suffix = ATTR_SHORTHAND[e.attrs.state] || e.attrs.state;
  }
  return suffix ? `${base}(${suffix})` : base;
}

let currentDocIdx = 0;
let hiddenTypes = new Set();
let selectedEntIdx = null;

// ── Sidebar ──

function buildStats() {
  const el = document.getElementById("stats");
  const totalDocs = DATA.length;
  let totalEnts = 0, totalRels = 0;
  for (const doc of DATA) {
    totalEnts += doc.entities.length;
    totalRels += doc.relations.length;
  }
  el.innerHTML = `<h2>Run Statistics</h2>` +
    `<div class="stat-row"><span>Documents</span><span>${totalDocs}</span></div>` +
    `<div class="stat-row"><span>Entities</span><span>${totalEnts.toLocaleString()}</span></div>` +
    `<div class="stat-row"><span>Relations</span><span>${totalRels.toLocaleString()}</span></div>`;
}

function buildDocList() {
  const ul = document.getElementById("doc-list");
  ul.innerHTML = "";
  for (let i = 0; i < DATA.length; i++) {
    const li = document.createElement("li");
    li.dataset.idx = i;
    li.textContent = DATA[i].id;
    const badge = document.createElement("span");
    badge.className = "ent-count";
    badge.textContent = `(${DATA[i].entities.length})`;
    li.appendChild(badge);
    if (i === currentDocIdx) li.classList.add("active");
    li.addEventListener("click", () => selectDoc(i));
    ul.appendChild(li);
  }
}

document.getElementById("doc-search").addEventListener("input", function() {
  const q = this.value.toLowerCase();
  for (const li of document.querySelectorAll("#doc-list li")) {
    li.style.display = li.textContent.toLowerCase().includes(q) ? "" : "none";
  }
});

// ── Legend ──

function buildLegend() {
  const bar = document.getElementById("legend-bar");
  bar.innerHTML = "";
  for (const [cls, label] of Object.entries(ENTITY_TYPES)) {
    const item = document.createElement("span");
    item.className = "legend-item";
    item.dataset.cls = cls;
    const swatch = document.createElement("span");
    swatch.className = "swatch";
    swatch.style.background = ENTITY_COLORS[cls] || "#eee";
    item.appendChild(swatch);
    item.appendChild(document.createTextNode(`${cls} ${label}`));
    item.addEventListener("click", () => toggleType(cls));
    bar.appendChild(item);
  }
}

function toggleType(cls) {
  if (hiddenTypes.has(cls)) hiddenTypes.delete(cls); else hiddenTypes.add(cls);
  for (const item of document.querySelectorAll(".legend-item")) {
    item.classList.toggle("off", hiddenTypes.has(item.dataset.cls));
  }
  applyTypeVisibility();
}

function applyTypeVisibility() {
  for (const span of document.querySelectorAll(".ent[data-cls]")) {
    span.classList.toggle("hidden-type", hiddenTypes.has(span.dataset.cls));
  }
  for (const row of document.querySelectorAll(".ent-row[data-cls]")) {
    row.style.display = hiddenTypes.has(row.dataset.cls) ? "none" : "";
  }
}

// ── Document rendering ──

function selectDoc(idx) {
  currentDocIdx = idx;
  selectedEntIdx = null;
  for (const li of document.querySelectorAll("#doc-list li")) {
    li.classList.toggle("active", parseInt(li.dataset.idx) === idx);
  }
  renderDoc();
}

function escapeHtml(s) {
  return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

function renderDoc() {
  const doc = DATA[currentDocIdx];
  document.getElementById("doc-header").textContent =
    `${doc.id}  (${doc.entities.length} entities, ${doc.relations.length} relations)`;
  renderTextPanel(doc);
  renderRelationsTable(doc);
  renderEntitiesTable(doc);
  applyTypeVisibility();
}

function renderTextPanel(doc) {
  const panel = document.getElementById("text-panel");
  const text = doc.text;
  if (!text) { panel.innerHTML = "<em>No text</em>"; return; }

  // Collect positioned entities as non-overlapping spans
  // Sort by start position; skip entities without positions
  const positioned = [];
  for (let i = 0; i < doc.entities.length; i++) {
    const e = doc.entities[i];
    if (e.start != null && e.end != null) {
      positioned.push({idx: i, start: e.start, end: e.end});
    }
  }
  positioned.sort((a, b) => a.start - b.start || b.end - a.end);

  // Build HTML by walking through source text
  let html = "";
  let cursor = 0;
  for (const p of positioned) {
    if (p.start < cursor) continue; // skip overlapping
    if (p.start > cursor) {
      html += escapeHtml(text.slice(cursor, p.start));
    }
    const e = doc.entities[p.idx];
    const color = ENTITY_COLORS[e.cls] || "#eee";
    const textColor = LIGHT_TEXT_TYPES.has(e.cls) ? "#fff" : "#000";
    const tagLabel = buildTagLabel(e);
    let tip = `e${p.idx+1} ${e.cls}: ${e.text}`;
    const attrParts = Object.entries(e.attrs || {}).map(([k,v]) => `${k}=${v}`);
    if (attrParts.length) tip += ` [${attrParts.join(", ")}]`;
    html += `<span class="ent" data-eidx="${p.idx}" data-cls="${e.cls}" style="background:${color};color:${textColor};" ` +
            `onmouseenter="hoverEnt(${p.idx})" onmouseleave="unhoverEnt()" onclick="clickEnt(${p.idx})">` +
            `<span class="tag">${tagLabel}</span>` +
            `<span class="ent-tooltip">${escapeHtml(tip)}</span>` +
            escapeHtml(text.slice(p.start, p.end)) +
            `</span>`;
    cursor = p.end;
  }
  if (cursor < text.length) {
    html += escapeHtml(text.slice(cursor));
  }
  panel.innerHTML = html;
}

function renderRelationsTable(doc) {
  const section = document.getElementById("relations-section");
  if (!doc.relations.length) { section.innerHTML = ""; return; }

  const grouped = {};
  for (let ri = 0; ri < doc.relations.length; ri++) {
    const r = doc.relations[ri];
    const key = `${r.cat}:${r.type}`;
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push({...r, ri});
  }

  let html = `<div style="font-size:13px;font-weight:600;margin:8px 0 4px;padding-bottom:4px;border-bottom:1px solid #e0e0e0;">Relations (${doc.relations.length})</div>`;
  html += `<table><tr><th>Type</th><th>From</th><th></th><th>To</th></tr>`;
  for (const [key, rels] of Object.entries(grouped).sort()) {
    for (const r of rels) {
      const fromE = doc.entities[r.from];
      const toE = doc.entities[r.to];
      const catLabel = r.cat === "temporal" ? "T" : "M";
      html += `<tr class="rel-row" data-ri="${r.ri}" data-from="${r.from}" data-to="${r.to}" ` +
              `onmouseenter="hoverRel(${r.from},${r.to})" onmouseleave="unhoverRel()" onclick="clickRel(${r.from},${r.to})">` +
              `<td><span style="color:${r.cat==='temporal'?'#1565c0':'#2e7d32'};font-weight:600;">[${catLabel}]</span> ${r.type}</td>` +
              `<td>${escapeHtml(fromE?.text||"?")} <span style="color:#999">(${fromE?.cls||"?"})</span></td>` +
              `<td>\u2192</td>` +
              `<td>${escapeHtml(toE?.text||"?")} <span style="color:#999">(${toE?.cls||"?"})</span></td></tr>`;
    }
  }
  html += `</table>`;
  section.innerHTML = html;
}

function renderEntitiesTable(doc) {
  const section = document.getElementById("entities-section");
  let html = `<div style="font-size:13px;font-weight:600;margin:8px 0 4px;padding-bottom:4px;border-bottom:1px solid #e0e0e0;">Entities (${doc.entities.length})</div>`;
  html += `<table><tr><th>#</th><th>Type</th><th>Text</th><th>Attributes</th><th>Span</th></tr>`;
  for (let i = 0; i < doc.entities.length; i++) {
    const e = doc.entities[i];
    const color = ENTITY_COLORS[e.cls] || "#eee";
    const textColor = LIGHT_TEXT_TYPES.has(e.cls) ? "#fff" : "#000";
    const tagLabel = buildTagLabel(e);
    const allAttr = Object.entries(e.attrs || {}).map(([k,v])=>`${k}=${v}`).join(", ");
    const spanStr = e.start != null ? `${e.start}\u2013${e.end}` : `<span class="not-found">not found</span>`;
    html += `<tr class="ent-row" data-eidx="${i}" data-cls="${e.cls}" ` +
            `onmouseenter="hoverEnt(${i})" onmouseleave="unhoverEnt()" onclick="clickEnt(${i})">` +
            `<td>e${i+1}</td>` +
            `<td><span style="background:${color};color:${textColor};padding:1px 6px;border-radius:4px;font-weight:600;font-size:11px;">${tagLabel}</span></td>` +
            `<td>${escapeHtml(e.text)}</td>` +
            `<td>${allAttr || "\u2014"}</td>` +
            `<td>${spanStr}</td></tr>`;
  }
  html += `</table>`;
  section.innerHTML = html;
}

// ── Interaction ──

function hoverEnt(idx) {
  clearHighlights();
  highlightEnt(idx, "hl");
  const doc = DATA[currentDocIdx];
  for (const r of doc.relations) {
    if (r.from === idx) highlightEnt(r.to, "hl-partner");
    if (r.to === idx) highlightEnt(r.from, "hl-partner");
  }
  for (const row of document.querySelectorAll(".rel-row")) {
    if (parseInt(row.dataset.from) === idx || parseInt(row.dataset.to) === idx) {
      row.classList.add("hl");
    }
  }
  const entRow = document.querySelector(`.ent-row[data-eidx="${idx}"]`);
  if (entRow) entRow.classList.add("hl");
}

function unhoverEnt() {
  if (selectedEntIdx != null) return;
  clearHighlights();
}

function clickEnt(idx) {
  if (selectedEntIdx === idx) { selectedEntIdx = null; clearHighlights(); return; }
  selectedEntIdx = idx;
  hoverEnt(idx);
  const span = document.querySelector(`.ent[data-eidx="${idx}"]`);
  if (span) span.scrollIntoView({behavior: "smooth", block: "center"});
}

function hoverRel(fromIdx, toIdx) {
  clearHighlights();
  highlightEnt(fromIdx, "hl");
  highlightEnt(toIdx, "hl-partner");
}

function clickRel(fromIdx, toIdx) {
  selectedEntIdx = fromIdx;
  hoverRel(fromIdx, toIdx);
  const span = document.querySelector(`.ent[data-eidx="${fromIdx}"]`);
  if (span) span.scrollIntoView({behavior: "smooth", block: "center"});
}

function unhoverRel() {
  if (selectedEntIdx != null) return;
  clearHighlights();
}

function highlightEnt(idx, cls) {
  for (const span of document.querySelectorAll(`.ent[data-eidx="${idx}"]`)) {
    span.classList.add(cls);
  }
}

function clearHighlights() {
  for (const el of document.querySelectorAll(".hl, .hl-partner")) {
    el.classList.remove("hl", "hl-partner");
  }
}

document.addEventListener("click", function(e) {
  if (!e.target.closest(".ent") && !e.target.closest(".ent-row") && !e.target.closest(".rel-row")) {
    selectedEntIdx = null;
    clearHighlights();
  }
});

// ── Tabs ──
function switchTab(tab) {
  for (const btn of document.querySelectorAll(".tab-btn")) {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  }
  for (const tc of document.querySelectorAll(".tab-content")) {
    tc.classList.toggle("active", tc.id === tab + "-section");
  }
}

// ── Init ──
buildStats();
buildDocList();
buildLegend();
renderDoc();
</script>
</body>
</html>"""


def build_html(docs: list[AnnotatedDocument], run_name: str) -> str:
    """Build the complete HTML string from AnnotatedDocuments."""
    doc_data = []
    for doc in docs:
        doc_data.append(prepare_doc_data(doc))

    color_vars = "\n".join(
        f"  --color-{cls}: {color};" for cls, color in ENTITY_COLORS.items()
    )

    return HTML_TEMPLATE % {
        "run_name": run_name,
        "color_vars": color_vars,
        "data_json": json.dumps(doc_data, ensure_ascii=False),
        "entity_types_json": json.dumps(ENTITY_TYPES, ensure_ascii=False),
        "entity_colors_json": json.dumps(ENTITY_COLORS, ensure_ascii=False),
        "light_text_types_json": json.dumps(sorted(LIGHT_TEXT_TYPES), ensure_ascii=False),
        "tag_abbrev_json": json.dumps(TAG_ABBREV, ensure_ascii=False),
        "attr_shorthand_json": json.dumps(ATTR_SHORTHAND, ensure_ascii=False),
        "timex3_type_shorthand_json": json.dumps(
            TIMEX3_TYPE_SHORTHAND, ensure_ascii=False
        ),
    }


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate an HTML viewer for a prism-annotator annotation run."
    )
    parser.add_argument("run_dir", type=Path, help="Path to a run output directory")
    parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Output HTML path (default: {run_dir}/viewer.html)",
    )
    args = parser.parse_args()

    run_dir: Path = args.run_dir
    results_path = run_dir / "results.json"

    if not results_path.exists():
        print(f"Error: {results_path} not found")
        raise SystemExit(1)

    docs = load_results(results_path)
    print(f"Loaded {len(docs)} documents from {results_path}")

    html = build_html(docs, run_dir.name)

    output_path = args.output or (run_dir / "viewer.html")
    output_path.write_text(html, encoding="utf-8")
    print(f"Viewer written to {output_path} ({len(html) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
