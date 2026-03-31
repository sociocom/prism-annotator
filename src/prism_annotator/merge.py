"""Merge relation extraction results onto entity base."""

from __future__ import annotations

from prism_annotator.models import AnnotatedDocument, Relation


def merge_relations(
    entity_docs: list[AnnotatedDocument],
    *relation_doc_lists: list[AnnotatedDocument],
) -> list[AnnotatedDocument]:
    """Merge relation phases onto entity base documents.

    Entity documents provide the entities; relation documents provide the
    relations. Relations are matched by ``doc_id``.
    """
    rel_by_id: dict[str, list[Relation]] = {}
    for rel_docs in relation_doc_lists:
        for rdoc in rel_docs:
            rel_by_id.setdefault(rdoc.doc_id, []).extend(rdoc.relations)

    merged: list[AnnotatedDocument] = []
    for edoc in entity_docs:
        rels = rel_by_id.get(edoc.doc_id, [])
        merged.append(AnnotatedDocument(
            doc_id=edoc.doc_id,
            text=edoc.text,
            entities=list(edoc.entities),
            relations=rels,
            raw_output=edoc.raw_output,
        ))
    return merged
