"""Stage 6 - Graph Construction & Storage.

Write resolved entities (Stage 4) and relationships (Stage 5) to Neo4j.
Neo4j is the source of truth; this stage is write-only.

If Neo4j is unavailable, fail loudly (don't silently skip).
"""

import os
from typing import Optional


def get_driver():
    """Get Neo4j driver from config or env. Raises if connection fails."""
    from neo4j import GraphDatabase
    from api.config import config

    uri = os.getenv("NEO4J_URI") or config["neo4j"]["uri"]
    # Accept both spellings of the user var (the .env historically used
    # NEO4J_USERNAME, the README/code used NEO4J_USER). Prefer NEO4J_USER.
    user = (
        os.getenv("NEO4J_USER")
        or os.getenv("NEO4J_USERNAME")
        or config["neo4j"]["user"]
    )
    password = os.getenv("NEO4J_PASSWORD") or config["neo4j"]["password"]

    driver = GraphDatabase.driver(uri, auth=(user, password))
    # Test connection
    with driver.session() as s:
        s.run("RETURN 1")
    return driver


def write_entities(entities: list[dict], driver=None) -> int:
    """Write resolved entities to Neo4j as nodes.

    Returns count of nodes created/updated.
    """
    if not driver:
        driver = get_driver()

    count = 0
    with driver.session() as s:
        for ent in entities:
            canonical_id = ent.get("canonical_id")
            text = ent.get("text")
            etype = ent.get("type")
            confidence = float(ent.get("confidence") or 0.0)
            aliases = ent.get("aliases", [])
            mentions = ent.get("mentions", [])

            # MERGE ensures idempotency (no duplicates on re-run)
            s.run(
                """MERGE (n {id: $id})
                   SET n.label = $label,
                       n.type = $type,
                       n.confidence = $confidence,
                       n.aliases = $aliases,
                       n.mentions = $mentions
                """,
                id=canonical_id,
                label=text,
                type=etype,
                confidence=confidence,
                aliases=aliases,
                mentions=mentions,
            )
            count += 1
    return count


# Relationship types the pipeline actually emits. Anything else is coerced to
# ASSOCIATION so we never inject an arbitrary string into a Cypher relationship
# TYPE (which must be a safe, case-sensitive identifier).
_VALID_REL_TYPES = {"FINANCIAL", "COMMUNICATION", "FAMILY", "ASSOCIATION"}


def _safe_rel_type(raw) -> str:
    """Coerce a relationship type to a whitelisted Cypher type name."""
    rtype = "".join(ch for ch in str(raw or "").upper() if ch.isalnum() or ch == "_")
    return rtype if rtype in _VALID_REL_TYPES else "ASSOCIATION"


def write_relationships(relationships: list[dict], driver=None) -> int:
    """Write relationships to Neo4j as edges.

    Returns count of relationships created/updated.
    """
    if not driver:
        driver = get_driver()

    count = 0
    with driver.session() as s:
        for rel in relationships:
            source_text = rel.get("source")
            target_text = rel.get("target")
            rel_type = _safe_rel_type(rel.get("type", rel.get("source_type")))
            weight = int(rel.get("weight") or 1)
            confidence = float(rel.get("confidence") or 0.0)

            # Find or create the source and target nodes (already created by write_entities)
            s.run(
                f"""MATCH (src {{label: $source_label}})
                    MATCH (tgt {{label: $target_label}})
                    MERGE (src)-[r:{rel_type}]->(tgt)
                    SET r.weight = $weight,
                        r.confidence = $confidence,
                        r.label = $label,
                        r.type = $rel_type
                """,
                source_label=source_text,
                target_label=target_text,
                weight=weight,
                confidence=confidence,
                label=rel.get("source_type", rel_type),
                rel_type=rel_type,
            )
            count += 1
    return count


def clear_graph(driver=None) -> None:
    """Delete all nodes/edges. Use cautiously."""
    if not driver:
        driver = get_driver()

    with driver.session() as s:
        s.run("MATCH (n) DETACH DELETE n")
