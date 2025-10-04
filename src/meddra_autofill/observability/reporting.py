"""Utilities to persist processing reports."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable

from ..models import ValidationResult
from ..queue.job_queue import JobItem
from ..orchestration.orchestrator import ProcessingReport


def report_to_dict(report: ProcessingReport) -> Dict[str, Any]:
    return {
        "success_count": report.success_count,
        "retry_count": report.retry_count,
        "failed_jobs": [job.record.case_id for job in report.failed_jobs],
        "validation_errors": [validation_to_dict(item) for item in report.validation_errors],
    }


def validation_to_dict(result: ValidationResult) -> Dict[str, Any]:
    return {
        "case_id": result.record.case_id,
        "is_valid": result.is_valid,
        "errors": list(result.errors),
        "warnings": list(result.warnings),
    }


def failed_jobs_to_dict(jobs: Iterable[JobItem]) -> Dict[str, Any]:
    return {
        job.record.case_id: {
            "attempts": job.attempts,
            "errors": list(job.error_messages),
        }
        for job in jobs
    }


def persist_report(report: ProcessingReport, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = report_to_dict(report)
    payload["failed_job_details"] = failed_jobs_to_dict(report.failed_jobs)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


__all__ = ["persist_report", "report_to_dict"]
