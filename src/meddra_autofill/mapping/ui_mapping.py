"""UI selector mapping catalog."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class UIFieldMapping:
    field_to_selector: Dict[str, str]

    def selector_for(self, field_name: str) -> str:
        try:
            return self.field_to_selector[field_name]
        except KeyError as exc:
            raise KeyError(f"No selector registered for field '{field_name}'") from exc


DEFAULT_MAPPING = UIFieldMapping(
    field_to_selector={
        "case_id": "#caseId",
        "reaction_reported_term": "input[name=\"reportedTerm\"]",
        "meddra_level": "select#meddraLevel",
        "meddra_term_text": "input[name=\"meddraText\"]",
        "meddra_code": "input[name=\"meddraCode\"]",
        "meddra_version": "input[name=\"meddraVersion\"]",
        "onset_date": "input[name=\"onsetDate\"]",
        "seriousness": "input[name=\"serious\"]",
        "suspect_drug": "input[name=\"suspectDrug\"]",
        "dose_text": "input[name=\"dose\"]",
        "outcome": "select#outcome",
        "narrative": "textarea#narrative",
    }
)

__all__ = ["UIFieldMapping", "DEFAULT_MAPPING"]
