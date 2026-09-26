"""
Unified ingestion router - single endpoint for all file uploads (PDF, TXT, CDR Excel, Financial Excel).

No text areas — only file uploads.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional

from services import ingest as ingest_service
from services import cases as case_service

router = APIRouter()


class FileIngestResponse(BaseModel):
    ok: bool
    entities_written: int
    relationships_written: int
    cdr_calls_written: int
    transactions_written: int
    error: Optional[str] = None


@router.post("/cases/{case_id}/ingest/files", response_model=FileIngestResponse)
async def ingest_files(
    case_id: str,
    files: list[UploadFile] = File(...),
    append_mode: bool = Form(False)
):
    """
    Unified ingestion endpoint for all file types.

    Accepts multiple files in a single request.
    Each file must have explicit file type via filename extension:
    - PDF: .pdf
    - TXT: .txt
    - CDR Excel: .csv, .xlsx, .xls (detected as CDR format)
    - Financial Excel: .csv, .xlsx, .xls (detected as financial format)

    **No text fields — only file uploads.**

    Files are processed in a single batch with centralized entity resolution.
    """
    try:
        case_service.require_case(case_id)

        valid_extensions = {
            "pdf": {".pdf"},
            "txt": {".txt", ".text", ".log"},
            "cdr": {".csv", ".xlsx", ".xls", ".tsv"},
            "financial": {".csv", ".xlsx", ".xls", ".tsv"}
        }

        # Map extensions to file types
        def detect_file_type(filename: str) -> str:
            """Detect file type from extension"""
            filename_lower = filename.lower()

            # Check each type
            for file_type, extensions in valid_extensions.items():
                for ext in extensions:
                    if filename_lower.endswith(ext):
                        return file_type

            # Default fallback based on content
            if "cdr" in filename_lower or "call" in filename_lower:
                return "cdr"
            elif "financial" in filename_lower or "transaction" in filename_lower or "bank" in filename_lower:
                return "financial"
            elif "fir" in filename_lower or "report" in filename_lower or "narrative" in filename_lower:
                return "txt"
            else:
                # If cannot determine, guess based on extension
                if filename_lower.endswith(".pdf"):
                    return "pdf"
                elif filename_lower.endswith(".txt") or filename_lower.endswith(".text"):
                    return "txt"
                else:
                    # Default to TXT for safety
                    return "txt"

        # Build file list with auto-detected types
        file_data_list = []
        total_size = 0

        for file in files:
            if not file.filename:
                raise HTTPException(400, "All uploaded files must have a filename")

            file_bytes = await file.read()
            total_size += len(file_bytes)

            # Detect file type
            file_type = detect_file_type(file.filename)

            file_data_list.append({
                "bytes": file_bytes,
                "file_type": file_type,
                "filename": file.filename
            })

        # Check total size (50MB limit for batch)
        if total_size > 50 * 1024 * 1024:
            raise HTTPException(400, "Total file size exceeds 50MB limit")

        # Ingest all files in single batch
        result = ingest_service.load_and_ingest_files(
            case_id=case_id,
            files=file_data_list,
            append_mode=append_mode
        )

        if not result.get("ok"):
            raise HTTPException(400, result.get("error", "Unknown error"))

        # Convert to response model
        return FileIngestResponse(
            ok=True,
            entities_written=result.get("entities_written", 0),
            relationships_written=result.get("relationships_written", 0),
            cdr_calls_written=result.get("cdr_calls_written", 0),
            transactions_written=result.get("transactions_written", 0)
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Internal error: {str(e)}")


@router.post("/cases/{case_id}/ingest/file", response_model=FileIngestResponse)
async def ingest_single_file(
    case_id: str,
    file: UploadFile = File(...),
    append_mode: bool = Form(False)
):
    """
    Single file upload endpoint (convenience wrapper for /cases/{id}/ingest/files).
    """
    return await ingest_files(case_id, [file], append_mode)


# REMOVED: text-only ingestion endpoint
# @router.post("/cases/{case_id}/ingest") - no longer needed


@router.post("/cases/{case_id}/clear")
def clear_case(case_id: str):
    """Wipe this case's entities/graph/audit trail — the case itself stays,
    ready for a fresh ingestion. To remove the case entirely, use
    DELETE /cases/{case_id} instead."""
    try:
        case_service.require_case(case_id)
        result = ingest_service.clear_case_data(case_id)
        if not result.get("ok"):
            raise HTTPException(400, result.get("error", "Clear failed"))
        return result
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))