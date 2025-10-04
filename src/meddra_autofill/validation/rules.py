"""Validation rule set for case records."""
from __future__ import annotations

from datetime import date
from typing import Iterable, List

from ..models import CaseRecord, ValidationResult


class CaseValidator:
    """Validates records against PoC MedDRA autofill rules."""

    REQUIRED_FIELDS = ("case_id", "reaction_reported_term", "meddra_level", "onset_date")
    ALLOWED_MEDDRA_LEVELS = {"LLT", "PT"}
    MIN_ONSET_DATE = date(1970, 1, 1)

    def __init__(self, today: date | None = None) -> None:
        self.today = today or date.today()

    def validate(self, record: CaseRecord) -> ValidationResult:
        errors: List[str] = []
        warnings: List[str] = []

        for field_name in self.REQUIRED_FIELDS:
            value = getattr(record, field_name)
            if not value:
                errors.append(f"Missing required field '{field_name}'")

        if record.onset_date:
            if record.onset_date < self.MIN_ONSET_DATE:
                errors.append(
                    f"onset_date {record.onset_date.isoformat()} is earlier than {self.MIN_ONSET_DATE.isoformat()}"
                )
            if record.onset_date > self.today:
                errors.append(
                    f"onset_date {record.onset_date.isoformat()} is in the future (>{self.today.isoformat()})"
                )
        elif record.raw_payload.get("onset_date"):
            errors.append(
                f"onset_date '{record.raw_payload['onset_date']}' could not be parsed; expected YYYY-MM-DD"
            )

        if record.meddra_level and record.meddra_level.upper() not in self.ALLOWED_MEDDRA_LEVELS:
            errors.append(
                f"meddra_level '{record.meddra_level}' must be one of {sorted(self.ALLOWED_MEDDRA_LEVELS)}"
            )

        has_text = bool(record.meddra_term_text)
        has_code = bool(record.meddra_code)
        if has_text != has_code:
            errors.append("meddra_term_text and meddra_code must be provided together")

        if record.narrative and len(record.narrative) > 4000:
            errors.append("narrative exceeds 4000 character limit")

        seriousness_value = record.seriousness or ""
        if seriousness_value and seriousness_value.lower() not in {"serious", "non-serious"}:
            warnings.append(
                f"seriousness '{seriousness_value}' not recognized; expected 'Serious' or 'Non-serious'"
            )

        return ValidationResult(record=record, is_valid=not errors, errors=errors, warnings=warnings)

    def validate_many(self, records: Iterable[CaseRecord]) -> List[ValidationResult]:
        return [self.validate(record) for record in records]


__all__ = ["CaseValidator"]
