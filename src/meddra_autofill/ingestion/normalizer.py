"""Normalize raw ingestion rows to the CaseRecord schema."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List


@dataclass(slots=True)
class RecordNormalizer:
    """Transforms heterogeneous source columns into canonical field names."""

    default_meddra_level: str = "PT"
    default_meddra_version: str = "MOCK-1.0"
    alias_map: Dict[str, List[str]] = field(
        default_factory=lambda: {
            "reaction_reported_term": ["reaction_reported_term", "reaction_term", "reported_term"],
            "meddra_term_text": ["meddra_term_text", "meddra_text", "reaction_term"],
            "meddra_code": ["meddra_code", "reaction_code", "llt_code", "pt_code"],
            "seriousness": ["seriousness", "serious"],
            "suspect_drug": ["suspect_drug", "drug_name", "medicinal_product"],
            "dose_text": ["dose_text", "dose", "dose_information"],
            "outcome": ["outcome", "reaction_outcome"],
            "onset_date": ["onset_date", "reaction_onset_date"],
            "narrative": ["narrative", "case_narrative", "summary"],
        }
    )

    def normalize_rows(self, rows: Iterable[dict[str, str]]) -> List[dict[str, str]]:
        return [self.normalize_row(row) for row in rows]

    def normalize_row(self, row: dict[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = dict(row)

        def _resolve(field: str) -> str | None:
            for alias in self.alias_map.get(field, []):
                value = row.get(alias)
                if value:
                    return str(value).strip()
            return None

        reaction_term = _resolve("reaction_reported_term")
        if reaction_term:
            normalized.setdefault("reaction_reported_term", reaction_term)
            normalized.setdefault("meddra_term_text", reaction_term)
        meddra_code = _resolve("meddra_code")
        if meddra_code:
            normalized.setdefault("meddra_code", meddra_code)

        normalized.setdefault("meddra_level", self.default_meddra_level)
        normalized.setdefault("meddra_version", self.default_meddra_version)

        seriousness = _resolve("seriousness")
        if seriousness:
            seriousness_clean = seriousness.strip().lower()
            if seriousness_clean.startswith("serious"):
                normalized.setdefault("seriousness", "Serious")
            elif seriousness_clean.startswith("non"):
                normalized.setdefault("seriousness", "Non-serious")
            else:
                normalized.setdefault("seriousness", seriousness.strip())

        suspect_drug = _resolve("suspect_drug")
        if suspect_drug:
            normalized.setdefault("suspect_drug", suspect_drug)

        dose_text = _resolve("dose_text")
        if dose_text:
            normalized.setdefault("dose_text", dose_text)

        outcome = _resolve("outcome")
        if outcome:
            normalized.setdefault("outcome", outcome)

        onset_date = _resolve("onset_date")
        if onset_date:
            normalized.setdefault("onset_date", onset_date)

        narrative = _resolve("narrative")
        if narrative:
            normalized.setdefault("narrative", narrative)
        elif row.get("indication"):
            normalized.setdefault("narrative", str(row["indication"]).strip())

        return normalized


__all__ = ["RecordNormalizer"]
