"""
Ingestion service - handles FIR/CDR text ingestion and case clearing.
Implements the three-phase pipeline with graph_builder write.
"""
from services.pretrained.pipeline import PretrainedPipeline
from services.graph_builder import GraphBuilder
from services import audit
from services.common import schemas
from utils import neo4j_driver as db

# Initialize pretrained pipeline and graph builder
_pipeline = PretrainedPipeline()
_graph_builder = GraphBuilder()


def run_ingestion(case_id: str, fir_text: str, cdr_text: str, append_mode: bool = False) -> dict:
    """Run the ingestion pipeline on FIR and CDR text"""
    if not fir_text.strip() and not cdr_text.strip():
        return {"ok": False, "error": "Paste at least one of the FIR or CDR text blocks."}

    # Phase 1: Extract raw entities (no DB access)
    raw_extraction = _pipeline.extract_raw(fir_text, cdr_text)

    # Phase 2: Resolve entities centrally
    resolved = _pipeline.resolve(raw_extraction, case_id, append_mode)

    # Phase 3: Extract relationships using resolved IDs
    relationships = _pipeline.extract_relationships(raw_extraction, resolved, fir_text + cdr_text)

    # Clear existing data if not in append mode (after extraction succeeds)
    if not append_mode:
        try:
            db.clear_case(case_id)
            audit.clear(case_id)
        except Exception as e:
            return {"ok": False, "error": f"Failed to clear case data: {str(e)}"}

    # Write graph using graph_builder
    try:
        stats = _graph_builder.write_graph(
            case_id=case_id,
            resolved=resolved,
            relationships=relationships,
            cdr_calls=raw_extraction.cdr_calls,
            transactions=raw_extraction.transactions,
            append_mode=append_mode
        )
    except Exception as e:
        return {"ok": False, "error": f"Failed to write graph: {str(e)}"}

    # Return summary
    return {
        "ok": True,
        "people": resolved.get("people", []),
        "locations": resolved.get("locations", []),
        "organizations": resolved.get("organizations", []),
        "vehicles": resolved.get("vehicles", []),
        "phones": resolved.get("phones", []),
        "bank_accounts": resolved.get("bank_accounts", []),
        "tabular_cdr_detected": _pipeline.cdr_extractor.is_tabular(cdr_text)[0] if cdr_text else False,
        "tabular_numbers_parsed": len(_pipeline.cdr_extractor.parse_rows(cdr_text, ";")) if cdr_text and _pipeline.cdr_extractor.is_tabular(cdr_text)[0] else 0,
        "entities_written": sum(stats["entities"].values()),
        "relationships_written": stats["relationships"],
        "cdr_calls_written": stats["cdr_calls"],
        "transactions_written": stats["transactions"]
    }


def clear_case_data(case_id: str) -> dict:
    """Wipe this case's entities/graph/audit trail — the case itself stays"""
    try:
        db.clear_case(case_id)
        audit.clear(case_id)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def load_and_ingest_files(case_id: str, files: list[dict], append_mode: bool = False) -> dict:
    """
    Load and ingest multiple files (PDF, TXT, CDR, financial) in a single batch.

    Args:
        case_id: Case identifier
        files: List of file dicts with keys: 'bytes', 'file_type', 'filename'
        append_mode: Whether to append to existing case or clear first

    Returns:
        Dict with ingestion results
    """
    from services.loaders import (
        PDFFileLoader, TXTFileLoader, CDRFileLoader, FinancialFileLoader
    )

    loaders = {
        "pdf": PDFFileLoader(),
        "txt": TXTFileLoader(),
        "cdr": CDRFileLoader(),
        "financial": FinancialFileLoader()
    }

    all_raw_extractions = []
    combined_text = ""
    all_cdr_calls = []
    all_transactions = []

    # Phase 1: Load and extract each file
    for file_info in files:
        file_type = file_info.get("file_type")
        file_bytes = file_info.get("bytes")
        filename = file_info.get("filename", "")

        if file_type not in loaders:
            return {"ok": False, "error": f"Unsupported file type: {file_type}"}

        try:
            loader = loaders[file_type]
            result = loader.load_from_bytes(file_bytes)
            result["metadata"]["filename"] = filename

            if file_type in ["pdf", "txt"]:
                combined_text += f"\n\n{result['text']}"
                raw_extraction = _pipeline.extract_raw(result['text'], "")
            elif file_type == "cdr":
                if result.get("is_tabular", False):
                    # Tabular CDR: extract phone numbers and calls
                    raw_extraction = _pipeline.extract_raw("", result.get("text", ""))
                    all_cdr_calls.extend(raw_extraction.cdr_calls)
                else:
                    # Narrative CDR: treat as text
                    combined_text += f"\n\n{result['text']}"
                    raw_extraction = _pipeline.extract_raw(result['text'], "")
            elif file_type == "financial":
                # Extract transactions from financial data
                from services.pretrained.financial_extractor import FinancialExtractor
                fin_extractor = FinancialExtractor()
                transactions = fin_extractor.extract_transactions_from_tabular(result.get("data", []))
                all_transactions.extend(transactions)
                raw_extraction = schemas.RawExtraction(
                    entities={"bank_accounts": fin_extractor.extract_accounts(result.get("data", []))},
                    cdr_calls=[],
                    transactions=transactions,
                    source_metadata=result["metadata"]
                )

            all_raw_extractions.append(raw_extraction)

        except Exception as e:
            return {"ok": False, "error": f"Failed to load {filename}: {str(e)}"}

    # Combine all raw extractions for resolution
    combined_raw = _combine_raw_extractions(all_raw_extractions)

    # Phase 2: Centralized resolution
    resolved = _pipeline.resolve(combined_raw, case_id, append_mode)

    # Phase 3: Relationship extraction from combined text
    relationships = []
    if combined_text.strip():
        relationships = _pipeline.extract_relationships(combined_raw, resolved, combined_text)

    # Clear existing data if not in append mode
    if not append_mode:
        try:
            db.clear_case(case_id)
            audit.clear(case_id)
        except Exception as e:
            return {"ok": False, "error": f"Failed to clear case data: {str(e)}"}

    # Collect source file info for entity attribution
    source_files = [f.get("filename", "unknown") for f in files if f.get("filename")]
    source_file = ", ".join(source_files) if source_files else None

    # Write graph
    try:
        stats = _graph_builder.write_graph(
            case_id=case_id,
            resolved=resolved,
            relationships=relationships,
            cdr_calls=all_cdr_calls,
            transactions=all_transactions,
            append_mode=append_mode,
            source_file=source_file
        )
    except Exception as e:
        return {"ok": False, "error": f"Failed to write graph: {str(e)}"}

    return {
        "ok": True,
        "entities_written": sum(stats["entities"].values()),
        "relationships_written": stats["relationships"],
        "cdr_calls_written": stats["cdr_calls"],
        "transactions_written": stats["transactions"]
    }


def _combine_raw_extractions(raw_extractions: list) -> schemas.RawExtraction:
    """Combine multiple raw extractions into one"""
    if not raw_extractions:
        from services.common import schemas
        return schemas.RawExtraction(
            entities={},
            cdr_calls=[],
            transactions=[],
            source_metadata={"type": "combined"}
        )

    combined_entities = {
        "people": [],
        "locations": [],
        "organizations": [],
        "vehicles": [],
        "phones": [],
        "bank_accounts": []
    }

    all_cdr_calls = []
    all_transactions = []

    for raw in raw_extractions:
        for key in combined_entities:
            if key in raw.entities:
                combined_entities[key].extend(raw.entities[key])
        all_cdr_calls.extend(raw.cdr_calls)
        all_transactions.extend(raw.transactions)

    # Deduplicate entities
    for key in combined_entities:
        combined_entities[key] = list(set(combined_entities[key]))

    from services.common import schemas
    return schemas.RawExtraction(
        entities=combined_entities,
        cdr_calls=all_cdr_calls,
        transactions=all_transactions,
        source_metadata={"type": "combined", "count": len(raw_extractions)}
    )
