"""Core data models for MedDRA autofill automation."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Iterable, List, Optional


@dataclass(slots=True)
class CaseRecord:
    """Represents a single case row to be entered into the target UI."""

    case_id: str
    reporter_type: Optional[str] = None
    onset_date: Optional[date] = None
    reaction_reported_term: Optional[str] = None
    meddra_level: Optional[str] = None
    meddra_term_text: Optional[str] = None
    meddra_code: Optional[str] = None
    meddra_version: Optional[str] = None
    seriousness: Optional[str] = None
    suspect_drug: Optional[str] = None
    dose_text: Optional[str] = None
    outcome: Optional[str] = None
    narrative: Optional[str] = None
    raw_payload: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Dict[str, str]) -> "CaseRecord":
        """Create a case record from a raw dictionary, preserving original values."""
        record = cls(
            case_id=str(payload.get("case_id", "")).strip(),
            reporter_type=_clean(payload.get("reporter_type")),
            reaction_reported_term=_clean(payload.get("reaction_reported_term")),
            meddra_level=_clean(payload.get("meddra_level")),
            meddra_term_text=_clean(payload.get("meddra_term_text")),
            meddra_code=_clean(payload.get("meddra_code")),
            meddra_version=_clean(payload.get("meddra_version")),
            seriousness=_clean(payload.get("seriousness")),
            suspect_drug=_clean(payload.get("suspect_drug")),
            dose_text=_clean(payload.get("dose_text")),
            outcome=_clean(payload.get("outcome")),
            narrative=_clean(payload.get("narrative")),
            raw_payload=payload,
        )

        onset_date_raw = _clean(payload.get("onset_date"))
        if onset_date_raw:
            record.onset_date = _parse_date(onset_date_raw)

        return record


@dataclass(slots=True)
class ValidationResult:
    """Outcome of validating a case record."""

    record: CaseRecord
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.is_valid and not self.warnings:
            return f"{self.record.case_id}: valid"
        if self.is_valid:
            joined = "; ".join(self.warnings)
            return f"{self.record.case_id}: valid with warnings - {joined}"
        joined = "; ".join(self.errors)
        return f"{self.record.case_id}: invalid - {joined}"


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    trimmed = str(value).strip()
    return trimmed or None


def _parse_date(value: str) -> Optional[date]:
    from datetime import datetime

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def records_from_iterable(items: Iterable[Dict[str, str]]) -> List[CaseRecord]:
    """Convert an iterable of dictionaries into case records."""
    return [CaseRecord.from_dict(item) for item in items]
