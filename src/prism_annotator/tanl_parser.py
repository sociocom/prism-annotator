"""Parse TANL inline-annotated text into Entity objects."""

from __future__ import annotations

import re

from prism_annotator.models import CharSpan, Entity
from prism_annotator.schema import ENTITY_TYPES

# ── Attribute abbreviation maps ─────────────────────────────────────────────

CERTAINTY_ABBREV = {"positive": "+", "negative": "-", "suspicious": "?", "general": "*"}
STATE_ABBREV = {"executed": "+", "negated": "-", "scheduled": "予", "other": "他"}
TIMEX3_TYPE_ABBREV = {
    "DATE": "DATE", "TIME": "TIME", "DURATION": "DUR", "SET": "SET",
    "AGE": "AGE", "MED": "MED", "MISC": "MISC",
}

ABBREV_TO_CERTAINTY = {v: k for k, v in CERTAINTY_ABBREV.items()}
ABBREV_TO_STATE = {v: k for k, v in STATE_ABBREV.items()}
ABBREV_TO_TIMEX3_TYPE = {
    "DATE": "DATE", "TIME": "TIME", "DUR": "DURATION", "SET": "SET",
    "AGE": "AGE", "MED": "MED", "MISC": "MISC",
    "DURATION": "DURATION",
}

# ── Regex ───────────────────────────────────────────────────────────────────

# Pattern: [entity_text | type_with_abbrev] — tolerates optional spaces around |
ENTITY_TAG_RE = re.compile(r"\[([^|\]]+?)\s*\|\s*([^\]]+?)\]")


def _parse_type_abbrev(type_str: str) -> tuple[str, dict[str, str]]:
    """Parse ``'type(abbrev)'`` or ``'type'`` into (label, attributes)."""
    m = re.match(r"^([a-zA-Z0-9_-]+)(?:\(([^)]*)\))?$", type_str.strip())
    if not m:
        return type_str.strip(), {}

    cls = m.group(1)
    abbrev = m.group(2) or ""
    attrs: dict[str, str] = {}

    if cls not in ENTITY_TYPES:
        return cls, attrs

    if cls == "TIMEX3" and abbrev:
        full_type = ABBREV_TO_TIMEX3_TYPE.get(abbrev, abbrev)
        attrs["type"] = full_type
    elif cls == "d" and abbrev:
        val = ABBREV_TO_CERTAINTY.get(abbrev)
        if val:
            attrs["certainty"] = val
    elif abbrev:
        val = ABBREV_TO_STATE.get(abbrev)
        if val:
            attrs["state"] = val

    return cls, attrs


def parse_tanl_entities(
    output_text: str, original_text: str,
) -> tuple[list[Entity], list[str]]:
    """Parse TANL-annotated text into Entity objects with CharSpan.

    Returns ``(entities, warnings)``.
    """
    warnings: list[str] = []
    entities: list[Entity] = []

    stripped_parts: list[str] = []
    stripped_pos = 0
    last_end = 0

    for m in ENTITY_TAG_RE.finditer(output_text):
        before = output_text[last_end:m.start()]
        stripped_parts.append(before)
        stripped_pos += len(before)

        entity_text = m.group(1)
        type_str = m.group(2)
        cls, attrs = _parse_type_abbrev(type_str)

        start = stripped_pos
        end = stripped_pos + len(entity_text)

        if cls not in ENTITY_TYPES:
            warnings.append(f"Unknown entity type: {cls} (text='{entity_text}')")
        elif not entity_text.strip():
            warnings.append(f"Empty entity text for type {cls}")
        else:
            entities.append(Entity(
                text=entity_text,
                label=cls,
                span=CharSpan(start=start, end=end),
                attributes=attrs,
            ))

        stripped_parts.append(entity_text)
        stripped_pos = end
        last_end = m.end()

    remaining = output_text[last_end:]
    stripped_parts.append(remaining)

    # Validate: stripped text should match original
    stripped_text = "".join(stripped_parts)
    if stripped_text != original_text:
        if stripped_text.split() == original_text.split():
            warnings.append("Minor whitespace differences between stripped output and original")
        else:
            diff_len = abs(len(stripped_text) - len(original_text))
            warnings.append(
                f"Text mismatch: stripped={len(stripped_text)} chars, "
                f"original={len(original_text)} chars (diff={diff_len})"
            )

    return entities, warnings
