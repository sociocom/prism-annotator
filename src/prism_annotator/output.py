"""Output writers: PRISM inline XML."""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from prism_annotator.models import AnnotatedDocument, Entity
from prism_annotator.schema import TEMPORAL_RELATIONS


def _entity_attr_str(ent: Entity) -> str:
    """Build XML attribute string from entity attributes."""
    parts: list[str] = []
    for k, v in ent.attributes.items():
        if isinstance(v, list):
            v = ",".join(str(x) for x in v)
        parts.append(f'{k}="{escape(str(v))}"')
    return " ".join(parts)


def _entity_xml_tag(ent: Entity, eid: str, text: str) -> str:
    """Build an inline XML entity tag."""
    attr_str = _entity_attr_str(ent)
    if attr_str:
        return f'<{ent.label} id="{eid}" {attr_str}>{escape(text)}</{ent.label}>'
    return f'<{ent.label} id="{eid}">{escape(text)}</{ent.label}>'


def _align_entities(
    text: str, entities: list[Entity],
) -> list[tuple[int, int, int]]:
    """Align entities to positions in the original source text.

    TANL parsing gives every entity a span, but those spans are offsets in
    the *stripped* TANL output which may differ from the original text due
    to minor LLM whitespace changes.  We use span order as a constraint
    and scan forward through the original text so that even duplicate
    entity texts (e.g. multiple ``痛み``) each get a unique position.

    Returns sorted list of ``(start, end, entity_index)``.
    """
    # Process entities in span order (TANL guarantees spans exist)
    ordered = sorted(
        range(len(entities)),
        key=lambda i: (entities[i].span.start if entities[i].span else float("inf"), i),
    )

    result: list[tuple[int, int, int]] = []
    search_from = 0

    for idx in ordered:
        et = entities[idx].text
        if not et:
            continue
        pos = text.find(et, search_from)
        if pos != -1:
            result.append((pos, pos + len(et), idx))
            search_from = pos + len(et)
        else:
            # Fallback: search from beginning (entity text may overlap with a
            # previous entity or appear earlier due to LLM text changes)
            pos = text.find(et)
            if pos != -1:
                result.append((pos, pos + len(et), idx))

    result.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    return result


def document_to_inline_xml(doc: AnnotatedDocument) -> str:
    """Convert a document to PRISM inline XML annotation format.

    Entities are inserted inline in the source text as XML tags.
    Relations are appended as ``<brel>`` and ``<trel>`` elements.
    """
    text = doc.text
    entities = doc.entities

    aligned = _align_entities(text, entities)

    # Remove overlapping: keep non-overlapping spans (greedy, left to right)
    filtered: list[tuple[int, int, int]] = []
    cursor = 0
    for start, end, idx in aligned:
        if start >= cursor:
            filtered.append((start, end, idx))
            cursor = end

    # Build inline XML
    parts: list[str] = []
    cursor = 0
    eid_map: dict[int, str] = {i: f"e{i + 1}" for i in range(len(entities))}

    for start, end, idx in filtered:
        ent = entities[idx]
        eid = eid_map[idx]
        if start > cursor:
            parts.append(escape(text[cursor:start]))
        parts.append(_entity_xml_tag(ent, eid, text[start:end]))
        cursor = end

    if cursor < len(text):
        parts.append(escape(text[cursor:]))

    inline_text = "".join(parts)

    # Build relation elements
    temporal_types = set(TEMPORAL_RELATIONS.keys())
    brels: list[str] = []
    trels: list[str] = []
    for i, rel in enumerate(doc.relations, 1):
        rid = f"r{i}"
        tag = (
            f'  <{"trel" if rel.rel_type in temporal_types else "brel"} '
            f'id="{rid}" from="{rel.from_eid}" to="{rel.to_eid}" '
            f'reltype="{rel.rel_type}" />'
        )
        if rel.rel_type in temporal_types:
            trels.append(tag)
        else:
            brels.append(tag)

    # Assemble document
    lines = [f'<document id="{doc.doc_id}">']
    lines.append(inline_text)
    if brels:
        lines.extend(brels)
    if trels:
        lines.extend(trels)
    lines.append("</document>")
    return "\n".join(lines)


def write_xml(results: list[AnnotatedDocument], output_path: Path) -> None:
    """Write results as PRISM inline-annotated XML corpus."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write("<corpus>\n")
        for doc in results:
            f.write(document_to_inline_xml(doc) + "\n")
        f.write("</corpus>\n")
