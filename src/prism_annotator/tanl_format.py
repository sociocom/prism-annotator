"""Generate TANL inline-annotated text from Entity objects."""

from __future__ import annotations

from prism_annotator.models import AnnotatedDocument
from prism_annotator.tanl_parser import (
    CERTAINTY_ABBREV,
    STATE_ABBREV,
    TIMEX3_TYPE_ABBREV,
)


def _abbrev_attr(cls: str, attrs: dict) -> str:
    """Build abbreviated attribute string for a TANL tag."""
    if cls == "TIMEX3":
        t = attrs.get("type", "")
        return TIMEX3_TYPE_ABBREV.get(t, t)
    if "certainty" in attrs:
        return CERTAINTY_ABBREV.get(attrs["certainty"], attrs["certainty"])
    if "state" in attrs:
        return STATE_ABBREV.get(attrs["state"], attrs["state"])
    return ""


def _entity_tag(text: str, cls: str, attrs: dict, eid: str) -> str:
    """Format: ``[text | type(abbrev) | eid]``."""
    abbrev = _abbrev_attr(cls, attrs)
    type_str = f"{cls}({abbrev})" if abbrev else cls
    return f"[{text} | {type_str} | {eid}]"


def document_to_tanl(doc: AnnotatedDocument) -> tuple[str, dict[str, int]]:
    """Convert entity-annotated document to TANL inline text.

    Returns ``(tanl_text, eid_to_index)`` where ``eid_to_index`` maps
    ``"e1"`` -> ``0``, etc.
    """
    text = doc.text or ""
    entities = doc.entities

    eid_map: dict[int, str] = {i: f"e{i + 1}" for i in range(len(entities))}
    eid_to_index: dict[str, int] = {v: k for k, v in eid_map.items()}

    # Separate entities with/without span
    positioned: list[tuple[int, int, int]] = []  # (start, end, entity_index)
    unpositioned: list[int] = []

    for i, ent in enumerate(entities):
        if ent.span is not None:
            positioned.append((ent.span.start, ent.span.end, i))
        else:
            unpositioned.append(i)

    # Sort by start position, then by span length descending (longer first)
    positioned.sort(key=lambda x: (x[0], -(x[1] - x[0])))

    # Remove nested entities: if B is fully inside A, move B to unpositioned
    filtered: list[tuple[int, int, int]] = []
    for start, end, idx in positioned:
        nested = False
        for fs, fe, _ in filtered:
            if start >= fs and end <= fe and (start, end) != (fs, fe):
                nested = True
                break
        if nested:
            unpositioned.append(idx)
        else:
            filtered.append((start, end, idx))

    # Build TANL text by walking through source text
    parts: list[str] = []
    cursor = 0
    for start, end, idx in filtered:
        ent = entities[idx]
        eid = eid_map[idx]
        if start > cursor:
            parts.append(text[cursor:start])
        parts.append(_entity_tag(text[start:end], ent.label, ent.attributes, eid))
        cursor = end

    if cursor < len(text):
        parts.append(text[cursor:])

    tanl_text = "".join(parts)

    # Append unpositioned entities
    if unpositioned:
        tanl_text += "\n\n（位置未確定エンティティ）\n"
        for idx in unpositioned:
            ent = entities[idx]
            eid = eid_map[idx]
            tanl_text += _entity_tag(ent.text, ent.label, ent.attributes, eid) + "\n"

    return tanl_text, eid_to_index
