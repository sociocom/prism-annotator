"""Post-processing: validate and clean extraction results."""

from __future__ import annotations

import logging
from collections import Counter

from prism_annotator.models import AnnotatedDocument, Entity
from prism_annotator.schema import (
    ENTITY_ATTRIBUTES,
    ENTITY_TYPES,
    REQUIRED_ATTRIBUTES,
)

logger = logging.getLogger(__name__)


def correct_entity(ent: Entity) -> list[str]:
    """Fix known LLM hallucination errors in-place. Returns list of corrections made."""
    corrections: list[str] = []
    cls = ent.label
    if cls not in ENTITY_TYPES or not ent.attributes:
        return corrections

    allowed = ENTITY_ATTRIBUTES.get(cls, {})
    for attr_name, attr_val in list(ent.attributes.items()):
        if attr_name not in allowed or not isinstance(attr_val, str):
            continue
        if attr_val not in allowed[attr_name]:
            if attr_name == "state" and attr_val in ("positive", "suspicious", "negative", "general"):
                fixed = "other"
                ent.attributes[attr_name] = fixed
                corrections.append(
                    f"[{cls}] '{ent.text}': "
                    f"corrected {attr_name}='{attr_val}' -> '{fixed}'"
                )
    return corrections


def correct_results(results: list[AnnotatedDocument]) -> int:
    """Apply corrections to all results. Returns total number of corrections."""
    total = 0
    for doc in results:
        for ent in doc.entities:
            for msg in correct_entity(ent):
                logger.info("Correction: %s (doc=%s)", msg, doc.doc_id)
                total += 1
    return total


def validate_entity(ent: Entity) -> list[str]:
    """Validate a single entity against the PRISM schema. Returns warnings."""
    warnings: list[str] = []
    cls = ent.label

    if cls not in ENTITY_TYPES:
        warnings.append(f"Unknown entity type: {cls}")
        return warnings

    attrs = ent.attributes

    for attr_name in REQUIRED_ATTRIBUTES.get(cls, set()):
        if attr_name not in attrs:
            warnings.append(
                f"[{cls}] '{ent.text}': missing required attribute '{attr_name}'"
            )

    allowed = ENTITY_ATTRIBUTES.get(cls, {})
    for attr_name, attr_val in attrs.items():
        if attr_name not in allowed:
            warnings.append(
                f"[{cls}] '{ent.text}': unexpected attribute '{attr_name}'"
            )
            continue
        if isinstance(attr_val, str) and attr_val not in allowed[attr_name]:
            warnings.append(
                f"[{cls}] '{ent.text}': invalid value '{attr_val}' "
                f"for attribute '{attr_name}' (allowed: {allowed[attr_name]})"
            )

    return warnings


def validate_document(doc: AnnotatedDocument) -> list[str]:
    """Validate all entities in a document."""
    all_warnings: list[str] = []
    for ent in doc.entities:
        all_warnings.extend(validate_entity(ent))
    return all_warnings


def validate_results(results: list[AnnotatedDocument]) -> dict[str, int]:
    """Validate all results and return warning counts by type."""
    warning_counter: Counter[str] = Counter()
    for doc in results:
        for w in validate_document(doc):
            category = w.split(":")[0] if ":" in w else w
            warning_counter[category] += 1
            logger.warning("Validation: %s (doc=%s)", w, doc.doc_id)
    return dict(warning_counter)


def compute_statistics(results: list[AnnotatedDocument]) -> dict[str, int]:
    """Compute entity type and relation distribution across all results."""
    entity_counts: Counter[str] = Counter()
    relation_counts: Counter[str] = Counter()
    total_entities = 0
    total_relations = 0

    for doc in results:
        for ent in doc.entities:
            entity_counts[ent.label] += 1
            total_entities += 1
        for rel in doc.relations:
            relation_counts[rel.rel_type] += 1
            total_relations += 1

    stats: dict[str, int] = {
        "total_documents": len(results),
        "total_entities": total_entities,
    }
    for cls in sorted(entity_counts):
        stats[f"entity_{cls}"] = entity_counts[cls]
    if total_relations:
        stats["total_relations"] = total_relations
        for name in sorted(relation_counts):
            stats[f"relation_{name}"] = relation_counts[name]
    return stats
