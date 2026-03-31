"""Parse and validate relation extraction output."""

from __future__ import annotations

import re

from prism_annotator.models import Relation
from prism_annotator.schema import BASIC_RELATIONS, TEMPORAL_RELATIONS

_VALID_TYPES = set(TEMPORAL_RELATIONS.keys()) | set(BASIC_RELATIONS.keys()) | {"keyValue"}

_RELATION_RE = re.compile(
    r"^\s*("
    + "|".join(re.escape(t) for t in sorted(_VALID_TYPES, key=len, reverse=True))
    + r")\s*:\s*(e\d+)\s*->\s*(e\d+)\s*$"
)


def parse_relations(
    text: str,
    valid_eids: set[str],
    phase: str,
    entity_labels: dict[str, str] | None = None,
) -> tuple[list[Relation], list[str]]:
    """Parse LLM relation output lines.

    Args:
        text: Raw LLM output.
        valid_eids: Set of valid entity IDs (e.g. ``{"e1", "e2", ...}``).
        phase: ``"time_relation"`` or ``"medical_relation"``.
        entity_labels: Optional mapping ``eid -> label`` for validation.

    Returns ``(relations, warnings)``.
    """
    time_types = set(TEMPORAL_RELATIONS.keys())
    medical_types = set(BASIC_RELATIONS.keys()) | {"keyValue"}
    allowed = time_types if phase == "time_relation" else medical_types

    relations: list[Relation] = []
    warnings: list[str] = []
    seen: set[tuple[str, str, str]] = set()

    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line == "(なし)":
            continue

        m = _RELATION_RE.match(line)
        if not m:
            warnings.append(f"Unparseable line: {line}")
            continue

        rel_type, from_eid, to_eid = m.group(1), m.group(2), m.group(3)

        if rel_type not in allowed:
            warnings.append(f"Wrong phase relation type: {line}")
            continue
        if from_eid not in valid_eids:
            warnings.append(f"Unknown from_eid: {from_eid} in {line}")
            continue
        if to_eid not in valid_eids:
            warnings.append(f"Unknown to_eid: {to_eid} in {line}")
            continue

        # For time relations, to-entity must be TIMEX3
        if phase == "time_relation" and entity_labels and entity_labels.get(to_eid) != "TIMEX3":
            warnings.append(f"to_eid {to_eid} is not TIMEX3: {line}")
            continue

        key = (rel_type, from_eid, to_eid)
        if key in seen:
            continue
        seen.add(key)
        relations.append(Relation(rel_type=rel_type, from_eid=from_eid, to_eid=to_eid))

    return relations, warnings
