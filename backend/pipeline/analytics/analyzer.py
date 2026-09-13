"""Stage 7 - Analytics & Anomaly Detection.

Read a subgraph from Neo4j, compute centrality metrics and anomaly flags in
NetworkX, then write results back to Neo4j node properties.

This is where the "AI" insight happens: identify influential nodes and flag
suspicious patterns.
"""

import os
from typing import Optional


def compute_analytics(driver=None) -> dict:
    """Read graph from Neo4j, compute centrality + anomalies, write back results.

    Returns a dict summarizing what was computed.
    """
    if not driver:
        from pipeline.graph.writer import get_driver
        driver = get_driver()

    import networkx as nx

    # Read all nodes and edges from Neo4j
    with driver.session() as s:
        nodes_res = s.run("MATCH (n) RETURN n.id AS id, n.label AS label, n.type AS type")
        nodes = {r["id"]: r for r in nodes_res}

        edges_res = s.run(
            "MATCH (a)-[r]->(b) RETURN a.id AS source, b.id AS target, r.weight AS weight, r.type AS rel_type"
        )
        edges = list(edges_res)

    if not nodes or not edges:
        return {"status": "no_data", "nodes_processed": 0}

    # Build a NetworkX graph weighted by confidence/weight
    G = nx.DiGraph()
    for nid, node in nodes.items():
        G.add_node(nid, label=node.get("label"), type=node.get("type"))

    for edge in edges:
        G.add_edge(
            edge["source"],
            edge["target"],
            weight=float(edge.get("weight") or 1),
            rel_type=edge.get("rel_type"),
        )

    # Compute centrality metrics
    centrality = nx.betweenness_centrality(G, weight="weight")
    pagerank = nx.pagerank(G, weight="weight")

    # Anomaly detection: flag nodes with unusually high centrality
    if centrality:
        mean_centrality = sum(centrality.values()) / len(centrality)
        std_dev = (sum((v - mean_centrality) ** 2 for v in centrality.values()) / len(centrality)) ** 0.5
        threshold = mean_centrality + 2 * std_dev if std_dev > 0 else mean_centrality * 1.5
    else:
        threshold = 0

    anomalies = {nid: c for nid, c in centrality.items() if c > threshold}

    # Cross-case detection: same phone/vehicle appearing in multiple independent nodes
    cross_case_flags = _detect_cross_case_identifiers(G, nodes)

    # Write results back to Neo4j
    with driver.session() as s:
        for nid, node in nodes.items():
            flags = []
            if nid in anomalies:
                flags.append("high_centrality")
            if nid in cross_case_flags:
                flags.append("cross_case_identifier")

            s.run(
                """MATCH (n {id: $id})
                   SET n.centrality = $centrality,
                       n.pagerank = $pagerank,
                       n.anomaly_flags = $flags
                """,
                id=nid,
                centrality=round(float(centrality.get(nid, 0)), 4),
                pagerank=round(float(pagerank.get(nid, 0)), 4),
                flags=flags,
            )

    return {
        "status": "ok",
        "nodes_processed": len(nodes),
        "edges_processed": len(edges),
        "anomalies_detected": len(anomalies),
        "cross_case_flags": len(cross_case_flags),
    }


def _detect_cross_case_identifiers(graph, nodes: dict) -> set:
    """Flag Phone/Vehicle nodes that connect to 2+ distinct Person neighbours.

    A phone or vehicle owned/called by many different people is a candidate for
    the same physical identifier appearing across otherwise-unrelated cases —
    the classic cross-case linkage signal. We walk the (directed) networkx
    graph and count distinct Person neighbours for each Phone/Vehicle node.
    """
    flags = set()
    for nid, node in nodes.items():
        if node.get("type") not in ("Phone", "Vehicle"):
            continue
        persons = {
            neighbor
            for neighbor in graph.neighbors(nid)
            if nodes.get(neighbor, {}).get("type") == "Person"
        }
        # also consider people pointing *into* this node (e.g. phone called by)
        persons |= {
            neighbor
            for neighbor in graph.predecessors(nid)
            if nodes.get(neighbor, {}).get("type") == "Person"
        }
        if len(persons) >= 2:
            flags.add(nid)
    return flags
