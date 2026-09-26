"""
Pretrained NLP Pipeline - Three-phase extraction with shared core logic.
"""
from typing import List, Optional
from services.common import schemas
from .entity_extractor import EntityExtractor
from .relationship_extractor import RelationshipExtractor
from .cdr_extractor import CDRParser
from services.common.entity_resolver import EntityResolver
from .nlp_loader import process_text
from utils import neo4j_driver as db


class PretrainedPipeline:
    """Orchestrate pretrained NLP extraction pipeline - three-phase process"""

    def __init__(self):
        self.entity_extractor = EntityExtractor()
        self.relationship_extractor = RelationshipExtractor()
        self.cdr_extractor = CDRParser()
        self.entity_resolver = EntityResolver()

    def run_ingestion(self, fir_text: str, cdr_text: str, append_mode: bool, case_id: str) -> dict:
        """Main ingestion pipeline - three-phase process"""
        fir_text = fir_text or ""
        cdr_text = cdr_text or ""

        # Phase 1: Extract raw entities (no DB access)
        raw_extraction = self.extract_raw(fir_text, cdr_text)

        # Phase 2: Resolve entities centrally
        resolved = self.resolve(raw_extraction, case_id, append_mode)

        # Phase 3: Extract relationships using resolved IDs
        relationships = self.extract_relationships(raw_extraction, resolved, fir_text + cdr_text)

        # Persistence happens outside the pipeline (in graph_builder)
        # Return only the data needed by the API
        return {
            "people": resolved["people"],
            "locations": resolved["locations"],
            "organizations": resolved["organizations"],
            "vehicles": resolved["vehicles"],
            "phones": resolved["phones"],
            "bank_accounts": resolved.get("bank_accounts", []),
            "tabular_cdr_detected": self.cdr_extractor.is_tabular(cdr_text)[0] if cdr_text else False,
            "tabular_numbers_parsed": len(self.cdr_extractor.parse_rows(cdr_text, ";")) if self.cdr_extractor.is_tabular(cdr_text)[0] else 0,
        }

    def extract_raw(self, fir_text: str, cdr_text: str) -> schemas.RawExtraction:
        """Phase 1: Pure extraction - no database access"""
        fir_text = fir_text or ""
        cdr_text = cdr_text or ""

        # Parse tabular CDR first
        tabular_numbers = self._ingest_tabular_cdr(cdr_text)
        cdr_text_for_nlp = "" if tabular_numbers is not None else cdr_text

        # Extract entities from text
        combined_text = f"{fir_text} \n {cdr_text_for_nlp}"
        doc = process_text(combined_text)

        # Extract all entity types using pretrained extractor
        raw_entities = self.entity_extractor.extract_all(combined_text, doc=doc)

        # Build CDR calls from tabular data
        cdr_calls = []
        if tabular_numbers is not None:
            cdr_calls = self._build_cdr_calls_from_rows(tabular_numbers)

        # Extract transactions from financial data in CDR (if present)
        transactions = []
        if "financial" in str(raw_entities).lower():
            # Look for financial data in CDR rows
            if tabular_numbers:
                from .financial_extractor import FinancialExtractor
                financial_extractor = FinancialExtractor()
                transactions = financial_extractor.extract_transactions_from_tabular(tabular_numbers)

        return schemas.RawExtraction(
            entities=raw_entities,
            cdr_calls=cdr_calls,
            transactions=transactions,
            source_metadata={"type": "pretrained"}
        )

    def resolve(self, raw_extraction: schemas.RawExtraction, case_id: str, append_mode: bool) -> dict:
        """Phase 2: Centralized entity resolution"""
        # Get existing entities from Neo4j if appending
        if append_mode:
            known_people = self._get_known_entities(case_id, "Person", "name")
            known_locations = self._get_known_entities(case_id, "Location", "name")
            known_orgs = self._get_known_entities(case_id, "Organization", "name")
            known_vehicles = self._get_known_entities(case_id, "Vehicle", "plate")
            known_phones = self._get_known_entities(case_id, "Phone", "number")
            known_bank_accounts = self._get_known_entities(case_id, "BankAccount", "account_number")
        else:
            known_people = []
            known_locations = []
            known_orgs = []
            known_vehicles = []
            known_phones = []
            known_bank_accounts = []

        resolved_map = {}
        all_people = sorted(set(raw_extraction.entities["people"]), key=lambda n: -len(n.split()))

        # Resolve people with fuzzy matching (preserving current behavior)
        for name in all_people:
            canonical = self.entity_resolver.resolve_person(name, known_people)
            resolved_map[name] = canonical
            if canonical not in known_people:
                known_people.append(canonical)

        # Other entities (no resolution needed)
        for loc in set(raw_extraction.entities["locations"]):
            if loc not in known_locations:
                known_locations.append(loc)

        for org in set(raw_extraction.entities["organizations"]):
            if org not in known_orgs:
                known_orgs.append(org)

        for vehicle in set(raw_extraction.entities["vehicles"]):
            if vehicle not in known_vehicles:
                known_vehicles.append(vehicle)

        for phone in set(raw_extraction.entities["phones"]):
            if phone not in known_phones:
                known_phones.append(phone)

        # Resolve bank accounts (exact match only)
        for account in set(raw_extraction.entities.get("bank_accounts", [])):
            canonical = self.entity_resolver.resolve_exact(account, known_bank_accounts)
            if canonical:
                known_bank_accounts.append(canonical)
            else:
                known_bank_accounts.append(account)

        return {
            "people": known_people,
            "locations": known_locations,
            "organizations": known_orgs,
            "vehicles": known_vehicles,
            "phones": known_phones,
            "bank_accounts": known_bank_accounts,
            "resolved_map": resolved_map
        }

    def extract_relationships(self, raw_extraction: schemas.RawExtraction, resolved: dict, text: str) -> List[schemas.Relationship]:
        """Phase 3: Extract relationships using resolved IDs"""
        # Build document for relationship extraction
        doc = process_text(text) if text else None

        # Create relationship extractor with resolver
        rel_extractor = RelationshipExtractor(self.entity_resolver)

        relationships = []

        if doc:
            for sent in doc.sents:
                # Extract all relationship types
                sent_relationships = rel_extractor.extract_all_from_sentence(
                    sent, resolved
                )
                relationships.extend(sent_relationships)

        # Apply resolved mapping to relationships
        for rel in relationships:
            rel["source"] = resolved["resolved_map"].get(rel["source"], rel["source"])
            rel["target"] = resolved["resolved_map"].get(rel["target"], rel["target"])
            # Fix field names for Pydantic schema
            if "type" in rel and "relationship_type" not in rel:
                rel["relationship_type"] = rel.pop("type")
            # Map "sentence" to "source_sentence"
            if "sentence" in rel and "source_sentence" not in rel:
                rel["source_sentence"] = rel.pop("sentence")

        return [schemas.Relationship(**rel) for rel in relationships]

    def _ingest_tabular_cdr(self, cdr_text: str) -> Optional[List[dict]]:
        """Handle tabular CDR data (no DB writes in pipeline)"""
        is_tabular, delim = self.cdr_extractor.is_tabular(cdr_text)
        if not is_tabular:
            return None

        rows = self.cdr_extractor.parse_rows(cdr_text, delim)
        return rows

    def _build_cdr_calls_from_rows(self, rows: List[dict]) -> List[schemas.CDRCall]:
        """Convert tabular CDR data to CDRCall objects"""
        cdr_calls = []
        for row in rows:
            cdr_calls.append(schemas.CDRCall(
                caller=row.get("caller", ""),
                called=row.get("called", ""),
                timestamp=row.get("timestamp"),
                duration=row.get("duration"),
                source_sentence=row.get("source_sentence")
            ))
        return cdr_calls

    def _get_known_entities(self, case_id: str, label: str, prop: str) -> List[str]:
        """Get existing entities from Neo4j"""
        rows = db.query(
            f"MATCH (n:{label} {{case_id: $case_id}}) RETURN n.{prop} AS v",
            {"case_id": case_id}
        )
        return [r["v"] for r in rows if r["v"] is not None]