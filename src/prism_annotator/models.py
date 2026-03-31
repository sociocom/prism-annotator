"""Native data model: CharSpan, Entity, Relation, AnnotatedDocument.

Entity IDs are positional: ``entities[0]`` is always ``e1``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CharSpan:
    """Character-level span in the source text."""

    start: int
    end: int

    def to_dict(self) -> dict:
        return {"start": self.start, "end": self.end}

    @classmethod
    def from_dict(cls, d: dict) -> CharSpan:
        return cls(start=d["start"], end=d["end"])


@dataclass
class Entity:
    """A single extracted entity."""

    text: str
    label: str
    span: CharSpan | None = None
    attributes: dict[str, str | list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d: dict = {"text": self.text, "label": self.label}
        if self.span is not None:
            d["span"] = self.span.to_dict()
        if self.attributes:
            d["attributes"] = self.attributes
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Entity:
        span = CharSpan.from_dict(d["span"]) if "span" in d else None
        return cls(
            text=d["text"],
            label=d["label"],
            span=span,
            attributes=d.get("attributes", {}),
        )


@dataclass
class Relation:
    """A directed relation between two entities (by entity ID)."""

    rel_type: str
    from_eid: str
    to_eid: str

    def to_dict(self) -> dict:
        return {
            "rel_type": self.rel_type,
            "from_eid": self.from_eid,
            "to_eid": self.to_eid,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Relation:
        return cls(
            rel_type=d["rel_type"],
            from_eid=d["from_eid"],
            to_eid=d["to_eid"],
        )


@dataclass
class AnnotatedDocument:
    """A document with extracted entities and relations.

    ``raw_output`` stores the raw LLM output — the primary artefact
    from which entities or relations are parsed.
    """

    doc_id: str
    text: str
    entities: list[Entity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    raw_output: str | None = None

    def to_dict(self) -> dict:
        d: dict = {
            "doc_id": self.doc_id,
            "text": self.text,
            "entities": [e.to_dict() for e in self.entities],
        }
        if self.relations:
            d["relations"] = [r.to_dict() for r in self.relations]
        if self.raw_output is not None:
            d["raw_output"] = self.raw_output
        return d

    @classmethod
    def from_dict(cls, d: dict) -> AnnotatedDocument:
        return cls(
            doc_id=d["doc_id"],
            text=d["text"],
            entities=[Entity.from_dict(e) for e in d.get("entities", [])],
            relations=[Relation.from_dict(r) for r in d.get("relations", [])],
            raw_output=d.get("raw_output"),
        )



# ── Batch I/O helpers ───────────────────────────────────────────────────────


def save_results(docs: list[AnnotatedDocument], path: Path) -> None:
    """Write a list of annotated documents to *results.json*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"documents": [doc.to_dict() for doc in docs]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_results(path: Path) -> list[AnnotatedDocument]:
    """Read annotated documents from *results.json*."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [AnnotatedDocument.from_dict(d) for d in payload["documents"]]


def append_result(doc: AnnotatedDocument, path: Path) -> None:
    """Append one document as an NDJSON line (crash-safe incremental write)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(doc.to_dict(), ensure_ascii=False) + "\n")


def load_results_ndjson(path: Path) -> list[AnnotatedDocument]:
    """Read annotated documents from an NDJSON file."""
    docs: list[AnnotatedDocument] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                docs.append(AnnotatedDocument.from_dict(json.loads(line)))
    return docs


def finalise_results(ndjson_path: Path) -> list[AnnotatedDocument]:
    """Read all documents from incremental NDJSON."""
    return load_results_ndjson(ndjson_path)
