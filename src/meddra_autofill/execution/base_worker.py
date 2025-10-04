"""Worker abstractions for UI automation."""
from __future__ import annotations

import abc
import logging
from typing import Optional

from ..mapping.ui_mapping import UIFieldMapping
from ..queue.job_queue import JobItem


class BaseUIWorker(abc.ABC):
    """Base class for UI automation workers."""

    def __init__(self, mapping: UIFieldMapping, logger: Optional[logging.Logger] = None) -> None:
        self.mapping = mapping
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    @abc.abstractmethod
    def process_job(self, job: JobItem) -> bool:
        """Run the job.

        Returns True when successful, False when a retryable failure occurred.
        Permanent failures should raise an exception for the orchestrator to handle.
        """

    def selector(self, field_name: str) -> str:
        return self.mapping.selector_for(field_name)


__all__ = ["BaseUIWorker"]
