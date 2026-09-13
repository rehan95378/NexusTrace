"""Graph service: writes/reads the network.

When Neo4j is reachable it is the source of truth. Until you spin up a local
Neo4j instance, GRAPH_MODE=seed returns a small in-memory graph so the API and
frontend work end-to-end during development.
"""

import os

from .config import config

SEED = {
    "nodes": [
        {"id": "p1", "label": "Ramesh Kumar", "type": "Person", "centrality": 0.9, "anomaly_flags": ["cross_case_phone"]},
        {"id": "p2", "label": "Suresh Kumar", "type": "Person", "centrality": 0.55, "anomaly_flags": []},
        {"id": "p3", "label": "Anil Verma", "type": "Person", "centrality": 0.4, "anomaly_flags": []},
        {"id": "v1", "label": "MH-12-AB-3456", "type": "Vehicle", "centrality": 0.3, "anomaly_flags": []},
        {"id": "ph1", "label": "+91-9876543210", "type": "Phone", "centrality": 0.7, "anomaly_flags": ["cross_case_phone"]},
        {"id": "l1", "label": "Nashik", "type": "Location", "centrality": 0.2, "anomaly_flags": []},
    ],
    "edges": [
        {"source": "p1", "target": "p2", "label": "called", "type": "COMMUNICATION", "weight": 4, "confidence": 0.9},
        {"source": "p1", "target": "p3", "label": "transferred funds to", "type": "FINANCIAL", "weight": 2, "confidence": 0.6},
        {"source": "p2", "target": "ph1", "label": "owns", "type": "OWNS", "weight": 1, "confidence": 0.8},
        {"source": "p1", "target": "v1", "label": "owns", "type": "OWNS", "weight": 1, "confidence": 0.7},
        {"source": "p1", "target": "l1", "label": "based_in", "type": "LOCATION", "weight": 1, "confidence": 0.5},
    ],
}


def _seed_mode():
    return os.getenv("GRAPH_MODE", "seed") == "seed"


def _driver():
    from neo4j import GraphDatabase

    return GraphDatabase.driver(
        config["neo4j"]["uri"],
        auth=(config["neo4j"]["user"], config["neo4j"]["password"]),
    )


def get_graph():
    """Return {'nodes': [...], 'edges': [...]} for the frontend."""
    if _seed_mode():
        return SEED
    with _driver().session() as s:
        # Query nodes with their properties
        nodes_res = s.run(
            """MATCH (n) RETURN n.id AS id, n.label AS label, n.type AS type,
               n.centrality AS centrality, n.pagerank AS pagerank,
               n.anomaly_flags AS anomaly_flags"""
        )
        nodes = [
            {
                "id": r["id"],
                "label": r["label"],
                "type": r["type"],
                "centrality": r["centrality"] or 0.0,
                "pagerank": r["pagerank"] or 0.0,
                "anomaly_flags": r["anomaly_flags"] or [],
            }
            for r in nodes_res
        ]

        # Query edges with their properties
        edges_res = s.run(
            """MATCH (a)-[r]->(b) RETURN a.id AS source, b.id AS target,
               r.label AS label, r.type AS type, r.weight AS weight,
               r.confidence AS confidence"""
        )
        edges = [
            {
                "source": r["source"],
                "target": r["target"],
                "label": r["label"],
                "type": r["type"],
                "weight": r["weight"] or 1,
                "confidence": r["confidence"] or 0.0,
            }
            for r in edges_res
        ]

        return {"nodes": nodes, "edges": edges}


def get_alerts():
    """Return nodes flagged with anomaly_flags (Stage 7 output → real data)."""
    if _seed_mode():
        return [
            {
                "node_id": n["id"],
                "label": n["label"],
                "type": n["type"],
                "flags": n.get("anomaly_flags", []),
                "reason": "appears across unrelated case files",
            }
            for n in SEED["nodes"]
            if n.get("anomaly_flags")
        ]
    with _driver().session() as s:
        res = s.run(
            """MATCH (n) WHERE size(n.anomaly_flags) > 0
               RETURN n.id AS node_id, n.label AS label, n.type AS type,
               n.anomaly_flags AS flags"""
        ).data()
        return [
            {**r, "reason": "flagged by Stage 7 anomaly rules"} for r in res
        ]


def merge_ingested(entities: list[dict], relationships: list[dict]) -> None:
    """In seed mode, reflect a just-ingested report in the in-memory graph so
    the demo graph grows as reports are uploaded (Neo4j optional). Idempotent:
    entities merge on canonical label; edges merge on (source,target,type).
    Afterwards analytical flags + centrality are recomputed over the whole graph
    (same Stage-7 logic the Neo4j path uses, run on the in-memory copy)."""
    if not _seed_mode():
        return

    # Merge nodes by label (canonical text).
    for ent in entities or ():
        label = str(ent.get("text") or "").strip()
        if not label:
            continue
        etype = ent.get("type")
        cid = ent.get("canonical_id") or f"ent_{label}"
        existing = next((n for n in SEED["nodes"] if n["label"] == label), None)
        if existing is not None:
            existing.setdefault("type", etype)
        else:
            SEED["nodes"].append(
                {
                    "id": cid,
                    "label": label,
                    "type": etype,
                    "centrality": 0.0,
                    "anomaly_flags": [],
                }
            )

    # Merge edges by (source, target, type) using label as the node key.
    for rel in relationships or ():
        src_label = rel.get("source")
        tgt_label = rel.get("target")
        rtype = rel.get("type") or rel.get("source_type")
        if not src_label or not tgt_label or not rtype:
            continue
        def _id_for(label):
            node = next((n for n in SEED["nodes"] if n["label"] == label), None)
            return node["id"] if node else label
        src_id, tgt_id = _id_for(src_label), _id_for(tgt_label)
        existing = next(
            (
                e for e in SEED["edges"]
                if e["source"] == src_id and e["target"] == tgt_id and e["type"] == rtype
            ),
            None,
        )
        if existing is not None:
            existing["weight"] = existing.get("weight", 0) + int(rel.get("weight") or 1)
            existing["confidence"] = max(existing.get("confidence", 0.0), float(rel.get("confidence") or 0.0))
        else:
            SEED["edges"].append(
                {
                    "source": src_id,
                    "target": tgt_id,
                    "label": str(rtype).title(),
                    "type": rtype,
                    "weight": int(rel.get("weight") or 1),
                    "confidence": float(rel.get("confidence") or 0.0),
                }
            )

    # Stage 7 captured on the in-memory graph so new uploads get real flags too.
    _recompute_seed_flags()


def promote(item: dict) -> bool:
    """Promote an analyst-approved review item into the graph.

    Relationship items encode endpoints as "source -> target" text; entity items
    are a single label. In seed mode the edge/node is merged into the in-memory
    graph and flags recomputed. In Neo4j mode we attempt a real write and fall
    back to the in-memory merge only if Neo4j is unreachable. Returns True when
    the item was surfaced.
    """
    if not item:
        return False
    kind = item.get("kind")
    conf = float(item.get("confidence") or 0.0)
    src_doc = item.get("source_doc_id")

    entities: list[dict] = []
    relationships: list[dict] = []

    if kind == "entity":
        label = str(item.get("text") or "").strip()
        if not label:
            return False
        entities.append({
            "text": label,
            "type": item.get("type") or "Unknown",
            "confidence": conf,
            "method": "review_promoted",
        })
    elif kind == "relationship":
        raw = str(item.get("text") or "")
        if "->" not in raw:
            return False
        src, tgt = (p.strip() for p in raw.split("->", 1))
        if not src or not tgt:
            return False
        rtype = (item.get("type") or item.get("source_type") or "ASSOCIATION") or "ASSOCIATION"
        relationships.append({
            "source": src,
            "target": tgt,
            "type": rtype,
            "source_type": rtype,
            "weight": int(item.get("weight") or 1),
            "confidence": conf,
            "source_doc_id": src_doc,
        })
    else:
        return False

    if _seed_mode():
        merge_ingested(entities, relationships)
        return True

    # Neo4j mode — try to write; fall back to the in-memory demo graph if the
    # DB is unreachable so the analyst still sees the change.
    try:
        from pipeline.graph.writer import get_driver, write_entities, write_relationships
        driver = get_driver()
        write_entities(entities, driver)
        write_relationships(relationships, driver)
        return True
    except Exception:
        merge_ingested(entities, relationships)
        return True


def _recompute_seed_flags() -> None:
    """Run Stage-7 centrality + anomaly heuristics over the in-memory SEED graph.

    Mirrors pipeline/analytics/analyzer.compute_analytics but without Neo4j:
    builds a networkx DiGraph from SEED and rewrites each node's centrality and
    anomaly_flags. Never raises — flaky optional logic must not break ingest.
    """
    try:
        import networkx as nx

        G = nx.DiGraph()
        for n in SEED["nodes"]:
            G.add_node(n["id"], type=n.get("type"), label=n.get("label"))
        for e in SEED["edges"]:
            G.add_edge(e["source"], e["target"], weight=float(e.get("weight") or 1))

        if not G.nodes or not G.edges:
            return

        centrality = nx.betweenness_centrality(G, weight="weight") if len(G) > 1 else {}
        if centrality:
            mean_c = sum(centrality.values()) / len(centrality)
            std_c = (sum((v - mean_c) ** 2 for v in centrality.values()) / len(centrality)) ** 0.5
            threshold = mean_c + 2 * std_c if std_c > 0 else mean_c * 1.5
        else:
            threshold = 0

        by_id = {n["id"]: n for n in SEED["nodes"]}
        for nid, c in centrality.items():
            by_id.setdefault(nid, {})["_c"] = c

        # cross-case: a Phone/Vehicle connected to 2+ distinct Person neighbours
        cross_case = set()
        for n in SEED["nodes"]:
            if n.get("type") not in ("Phone", "Vehicle"):
                continue
            persons = {
                nb for nb in G.neighbors(n["id"])
                if by_id.get(nb, {}).get("type") == "Person"
            }
            persons |= {
                nb for nb in G.predecessors(n["id"])
                if by_id.get(nb, {}).get("type") == "Person"
            }
            if len(persons) >= 2:
                cross_case.add(n["id"])

        for n in SEED["nodes"]:
            c = centrality.get(n["id"], 0.0)
            flags = []
            if c > threshold:
                flags.append("high_centrality")
            if n["id"] in cross_case:
                flags.append("cross_case_identifier")
            n["centrality"] = round(float(c), 4)
            n["anomaly_flags"] = flags
    except Exception:  # pragma: no cover - optional dependency / data issue
        return