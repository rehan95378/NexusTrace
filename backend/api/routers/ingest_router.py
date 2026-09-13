from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
import tempfile
from pathlib import Path
from ..auth import get_user_from_token

router = APIRouter(prefix="/ingest", tags=["ingest"])

# Hard cap on upload size. Read the file in chunks and abort past this so a very
# large (or malicious) file can't exhaust memory in the demo API.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MiB
_CHUNK = 1024 * 1024


async def _read_capped(file: UploadFile) -> bytes:
    """Read an upload up to MAX_UPLOAD_BYTES, raising 413 if it exceeds it."""
    buf = bytearray()
    while True:
        chunk = await file.read(_CHUNK)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                413,
                f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB upload limit",
            )
    return bytes(buf)


@router.post("/upload")
async def upload_report(file: UploadFile = File(...), _user=Depends(get_user_from_token)):
    """Accept a report file (CSV/JSON/PDF), ingest it, run the extraction
    pipeline, and write results to the graph.

    Returns a summary of what was extracted.
    """
    if not file.filename:
        raise HTTPException(400, "No filename")

    tmp_path = None
    try:
        # Save uploaded file to a temp directory (size-capped).
        from pipeline.ingestion.loader import load_file
        from pipeline.run_stages import run_stages
        from pipeline.graph.writer import get_driver, write_entities, write_relationships
        from pipeline.analytics.analyzer import compute_analytics

        content = await _read_capped(file)
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
            tmp.write(content)
            tmp.flush()
            tmp_path = tmp.name

        # Ingest the single file
        records = load_file(tmp_path)

        # Stages 2-8 via the shared runner (identical to the CLI pipeline).
        staged = run_stages(records)
        graph_entities = staged["graph_entities"]
        graph_rels = staged["graph_relationships"]
        review_items = staged["review_items"]

        # Write verified items to the graph. In seed mode (no Neo4j) this is
        # reflected in the in-memory graph instead, so the demo still works.
        written_to = "neo4j"
        try:
            driver = get_driver()
            write_entities(graph_entities, driver)
            write_relationships(graph_rels, driver)
            compute_analytics(driver)
        except Exception:
            from api.graph_service import merge_ingested
            merge_ingested(graph_entities, graph_rels)
            written_to = "in-memory"

        return {
            "success": True,
            "entities": len(graph_entities),
            "relationships": len(graph_rels),
            "review_queue": len(review_items),
            "written_to": written_to,
            "message": (
                f"Extracted {len(graph_entities)} entities and "
                f"{len(graph_rels)} relationships; "
                f"{len(review_items)} low-confidence item(s) routed to review"
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Ingestion failed: {str(e)}")
    finally:
        if tmp_path and Path(tmp_path).exists():
            Path(tmp_path).unlink()  # cleanup
