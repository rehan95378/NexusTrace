"""NexusTrace extraction pipeline CLI runner.

Rehearses the full extraction flow end-to-end:

    ingest -> clean/split -> extract -> resolve -> build relationships -> write to Neo4j -> analytics

Run:
    ./venv/bin/python -m pipeline.run_pipeline [--write-neo4j] [--clear]

Flags:
  --write-neo4j  Write results to Neo4j instead of just printing
  --clear        Clear Neo4j graph before writing (use with --write-neo4j)

Prints a concise summary: entity counts per type, total relationship count,
and the top-5 highest-confidence relationships.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

# Project root (repo layout => this file lives at <root>/pipeline/run_pipeline.py).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"

_WRITE_NEO4J = "--write-neo4j" in sys.argv
_CLEAR_NEO4J = "--clear" in sys.argv


def _entity_counts(entities: list[dict]) -> Counter:
    return Counter(e.get("type") for e in entities)


def _run() -> None:
    from pipeline.ingestion.loader import ingest_directory
    from pipeline.run_stages import run_stages

    raw_dir = Path(RAW_DIR)
    if not raw_dir.is_dir():
        print(f"[run_pipeline] data/raw not found at {raw_dir}")
        return

    records = ingest_directory(raw_dir)
    print(f"[run_pipeline] ingested {len(records)} record(s)")

    # Stages 2-8 run through the shared runner (same path the ingest API uses).
    staged = run_stages(records)
    resolved: list[dict] = staged["resolved"]
    final_rels: list[dict] = staged["relationships"]
    graph_entities: list[dict] = staged["graph_entities"]
    graph_rels: list[dict] = staged["graph_relationships"]
    review_items: list[dict] = staged["review_items"]

    print(f"[run_pipeline] resolved to {len(resolved)} canonical entity(ies)")
    print(
        f"[run_pipeline] {len(graph_rels)} verified relationship(s) -> graph; "
        f"{len(review_items)} low-confidence item(s) -> review queue"
    )

    # Stage 6 + 7 (optional): Write verified items to Neo4j and compute analytics
    if _WRITE_NEO4J:
        try:
            from pipeline.graph.writer import get_driver, write_entities, write_relationships, clear_graph
            from pipeline.analytics.analyzer import compute_analytics

            driver = get_driver()
            if _CLEAR_NEO4J:
                print("[run_pipeline] clearing Neo4j graph...")
                clear_graph(driver)
            print(f"[run_pipeline] writing {len(graph_entities)} verified entities to Neo4j...")
            write_entities(graph_entities, driver)
            print(f"[run_pipeline] writing {len(graph_rels)} verified relationships to Neo4j...")
            write_relationships(graph_rels, driver)
            print("[run_pipeline] computing analytics (centrality, anomalies)...")
            analytics = compute_analytics(driver)
            print(f"[run_pipeline] analytics: {analytics}")
        except Exception as e:
            print(f"[run_pipeline] Neo4j write failed: {e}")
            return

    # ------------ summary ------------
    print("\n=== NexusTrace extraction pipeline summary ===")
    print("Entity counts per type:")
    if resolved:
        for etype, n in sorted(_entity_counts(resolved).items()):
            print(f"  {etype:<14} {n}")
    else:
        print("  (none)")
    print(f"Relationships: {len(final_rels)} total "
          f"({len(graph_rels)} verified in graph, {len(review_items)} in review queue)")
    if graph_rels:
        print("\nTop-5 highest-confidence verified relationships:")
        ranked = sorted(
            graph_rels,
            key=lambda r: (float(r.get("confidence") or 0.0),
                           int(r.get("weight") or 0)),
            reverse=True,
        )[:5]
        for r in ranked:
            conf = float(r.get("confidence") or 0.0)
            print(f"  {r['source']} --[{r['type']}]--> {r['target']} ({conf:.2f})")
    if review_items:
        print(f"\nReview queue ({len(review_items)} items awaiting analyst review). "
              f"See `GET /review` in the API.")


if __name__ == "__main__":
    _run()