"""Shared extraction-stage runner (Stages 2-8).

The CLI pipeline runner and the ingest HTTP router both execute the same
extract -> resolve -> relationships -> dedupe -> review-split sequence.
Keeping that sequence in one place means the two entry points can't drift.

run_stages(records) -> {
    "resolved":            canonical entities (Stage 4 output),
    "relationships":       deduped relationships across all records (Stage 5),
    "graph_entities":      verified entities that enter the main graph,
    "graph_relationships": verified relationships that enter the main graph,
    "review_items":        low-confidence items routed to the review queue,
}
"""
from __future__ import annotations

from typing import Optional


def run_stages(records: list[dict]) -> dict:
    """Run clean/split -> extract -> resolve -> relationships -> dedupe -> split.

    ``records`` are the unified ingestion contract records (Stage 1 output).
    Returns the summary dict described in the module docstring.
    """
    from pipeline.preprocessing.cleaner import split_sentences
    from pipeline.extraction.extractor import extract_entities
    from pipeline.resolution.resolver import resolve_entities
    from pipeline.relationships.builder import build_relationships
    from pipeline.review.queue import split

    # Stage 2+3: per-record clean/split and extraction.
    all_sentences: list[tuple[str, Optional[str]]] = []  # (sentence, source_doc_id)
    all_entities: list[dict] = []

    for rec in records:
        doc_id = rec.get("source_doc_id")
        text = str(rec.get("raw_content") or "")
        for s in split_sentences(text):
            all_sentences.append((s, doc_id))
        all_entities.extend(extract_entities(rec))

    # Stage 4: resolve entities across ALL records together.
    resolved = resolve_entities(all_entities)

    # Stage 5: build relationships, grouped per source document.
    relationships: list[dict] = []
    for sentence, doc_id in all_sentences:
        relationships.extend(build_relationships([sentence], resolved, doc_id))

    # De-dupe identical (source, target, type) across the accumulated list.
    deduped: dict[tuple, dict] = {}
    for rel in relationships:
        key = (rel["source"], rel["target"], rel["type"])
        if key not in deduped:
            deduped[key] = dict(rel)
        elif rel["confidence"] > deduped[key]["confidence"]:
            deduped[key]["confidence"] = rel["confidence"]
    final_rels = list(deduped.values())

    # Stage 8: route low-confidence items to the review queue. Only verified
    # items enter the main graph.
    routed = split(resolved, final_rels)

    return {
        "resolved": resolved,
        "relationships": final_rels,
        "graph_entities": routed["graph_entities"],
        "graph_relationships": routed["graph_relationships"],
        "review_items": routed["review_items"],
    }