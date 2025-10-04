"""Job orchestration for MedDRA autofill automation."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable, List

from ..execution.base_worker import BaseUIWorker
from ..models import CaseRecord, ValidationResult
from ..queue.job_queue import JobItem, JobQueue


@dataclass(slots=True)
class ProcessingReport:
    success_count: int = 0
    retry_count: int = 0
    failed_jobs: List[JobItem] = field(default_factory=list)
    validation_errors: List[ValidationResult] = field(default_factory=list)

    @property
    def total_attempted(self) -> int:
        return self.success_count + self.retry_count + len(self.failed_jobs)


class Orchestrator:
    """Coordinates validation, queueing, and worker execution."""

    def __init__(
        self,
        worker: BaseUIWorker,
        queue: JobQueue | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.worker = worker
        self.queue = queue or JobQueue()
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    def enqueue_valid(self, validation_results: Iterable[ValidationResult]) -> ProcessingReport:
        report = ProcessingReport()
        for result in validation_results:
            if result.is_valid:
                self.queue.enqueue(result.record)
            else:
                report.validation_errors.append(result)
        return report

    def run(self, validation_results: Iterable[ValidationResult]) -> ProcessingReport:
        report = self.enqueue_valid(validation_results)

        while True:
            job = self.queue.dequeue()
            if job is None:
                break
            try:
                success = self.worker.process_job(job)
            except Exception as exc:  # pragma: no cover - runtime failure path
                self.logger.exception("Job failed permanently: %s", exc, extra={"job_id": job.record.case_id})
                report.failed_jobs.append(job)
                continue

            if success:
                report.success_count += 1
                continue

            report.retry_count += 1
            self.queue.requeue(job, "worker requested retry")

        report.failed_jobs.extend(self.queue.dead_letter)
        return report


__all__ = ["Orchestrator", "ProcessingReport"]
