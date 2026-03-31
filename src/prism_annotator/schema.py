"""PRISM entity types, relation types, and attribute definitions (v8)."""

from __future__ import annotations

# ── Entity Types ──────────────────────────────────────────────────────────────

ENTITY_TYPES: dict[str, str] = {
    "d": "Diseases/Symptoms",
    "a": "Anatomical parts",
    "f": "Features/Measurements",
    "c": "Change",
    "TIMEX3": "Time expression",
    "t-test": "Test name",
    "t-key": "Test item",
    "t-val": "Test value",
    "m-key": "Medication name",
    "m-val": "Medication value",
    "r": "Remedy",
    "cc": "Clinical context",
    "p": "Pending",
}

# ── Attribute Definitions ─────────────────────────────────────────────────────

CERTAINTY_VALUES = ("positive", "suspicious", "negative", "general")
STATE_VALUES = ("scheduled", "executed", "negated", "other")
TIMEX3_TYPE_VALUES = ("DATE", "TIME", "DURATION", "SET", "AGE", "MED", "MISC")

# Mapping: entity_type -> {attribute_name: allowed_values}
ENTITY_ATTRIBUTES: dict[str, dict[str, tuple[str, ...]]] = {
    "d": {"certainty": CERTAINTY_VALUES},
    "a": {},
    "f": {},
    "c": {},
    "TIMEX3": {"type": TIMEX3_TYPE_VALUES},
    "t-test": {"state": STATE_VALUES},
    "t-key": {"state": STATE_VALUES},  # optional
    "t-val": {},
    "m-key": {"state": STATE_VALUES},
    "m-val": {"state": STATE_VALUES},  # optional
    "r": {"state": STATE_VALUES},
    "cc": {"state": STATE_VALUES},
    "p": {},
}

# Which attributes are required (vs. optional) per entity type
REQUIRED_ATTRIBUTES: dict[str, set[str]] = {
    "d": {"certainty"},
    "TIMEX3": {"type"},
    "t-test": {"state"},
    "m-key": {"state"},
    "r": {"state"},
    "cc": {"state"},
}

# ── Relation Types ────────────────────────────────────────────────────────────

BASIC_RELATIONS: dict[str, str] = {
    "changeSbj": "Subject of change (<c> → target entity)",
    "changeRef": "Reference point of change (<c> → baseline)",
    "featureSbj": "Subject of feature (<f> → target entity)",
    "subRegion": "Spatial containment (<a>/<d> → contained entity)",
    "keyValue": "Test/medication key-value pair (key → val)",
}

TEMPORAL_RELATIONS: dict[str, str] = {
    "timeOn": "At that time point",
    "timeBefore": "Ended before that time",
    "timeAfter": "Started after that time",
    "timeBegin": "Began at that time",
    "timeEnd": "Ended at that time",
}
