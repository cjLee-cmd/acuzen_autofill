"""Command-line entry point for MedDRA autofill batch processing."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional

from meddra_autofill.execution.playwright_worker import PlaywrightWorker
from meddra_autofill.ingestion.excel_ingestion import ExcelIngestor
from meddra_autofill.ingestion.normalizer import RecordNormalizer
from meddra_autofill.mapping.ui_mapping import DEFAULT_MAPPING
from meddra_autofill.observability.logger import configure_logging
from meddra_autofill.observability.reporting import persist_report
from meddra_autofill.orchestration.orchestrator import Orchestrator
from meddra_autofill.validation.rules import CaseValidator
from meddra_autofill.models import records_from_iterable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MedDRA autofill batch processor")
    parser.add_argument("input_path", help="Path to CSV/Excel file containing case records")
    parser.add_argument(
        "--log",
        dest="log_path",
        default=None,
        help="Optional path for JSONL execution logs",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Execute without real browser automation",
    )
    parser.add_argument(
        "--report-json",
        dest="report_json",
        default=None,
        help="Optional path to store processing summary as JSON",
    )
    parser.add_argument(
        "--meddra-level",
        dest="meddra_level",
        default="PT",
        help="Default MedDRA level to apply when source data is missing",
    )
    parser.add_argument(
        "--meddra-version",
        dest="meddra_version",
        default="MOCK-1.0",
        help="Default MedDRA version to apply when source data is missing",
    )
    parser.add_argument(
        "--target-url",
        dest="target_url",
        default="ui/mock_form.html",
        help="URL 또는 파일 경로 (html) – Playwright가 접속할 대상",
    )
    return parser.parse_args()


def main(_: Optional[list[str]] = None) -> int:
    args = parse_args()
    configure_logging(args.log_path)
    logger = logging.getLogger("runner")

    input_path = Path(args.input_path)
    logger.info("Loading records", extra={"path": str(input_path)})

    ingestor = ExcelIngestor()
    raw_rows = ingestor.load_rows(input_path)
    normalizer = RecordNormalizer(
        default_meddra_level=args.meddra_level,
        default_meddra_version=args.meddra_version,
    )
    normalized_rows = normalizer.normalize_rows(raw_rows)
    records = records_from_iterable(normalized_rows)

    validator = CaseValidator()
    results = validator.validate_many(records)

    worker = PlaywrightWorker(
        mapping=DEFAULT_MAPPING,
        dry_run=args.dry_run,
        target_url=args.target_url,
        logger=logging.getLogger("worker"),
    )
    orchestrator = Orchestrator(worker=worker, logger=logging.getLogger("orchestrator"))

    report = orchestrator.run(results)

    logger.info(
        "Processing finished",
        extra={
            "success": report.success_count,
            "validation_errors": len(report.validation_errors),
            "failed_jobs": len(report.failed_jobs),
            "requeued": report.retry_count,
        },
    )

    if report.validation_errors:
        logger.warning("Validation errors encountered")
        for validation in report.validation_errors:
            logger.warning(validation.summary())

    if args.report_json:
        persist_report(report, args.report_json)

    if report.failed_jobs:
        logger.error("Some jobs failed permanently: %s", [job.record.case_id for job in report.failed_jobs])
        return 1

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
