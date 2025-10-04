"""Playwright-based UI worker implementation (scaffold)."""
from __future__ import annotations

import logging
from contextlib import ExitStack
from pathlib import Path
from typing import Optional

from .base_worker import BaseUIWorker
from ..queue.job_queue import JobItem


class PlaywrightWorker(BaseUIWorker):
    """Processes jobs using Playwright automation.

    The default behaviour runs in dry-run mode when Playwright is not installed or
    when `dry_run=True` is provided. Dry-run simply logs the intended actions.
    """

    def __init__(
        self,
        *args,
        dry_run: bool = False,
        target_url: Optional[str] = None,
        submit_selector: str = "button[type=submit]",
        success_selector: Optional[str] = "#status",
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.dry_run = dry_run
        self.target_url = target_url
        self.submit_selector = submit_selector
        self.success_selector = success_selector

    def process_job(self, job: JobItem) -> bool:
        record = job.record
        self.logger.info("Processing job", extra={"job_id": record.case_id})

        if self.dry_run:
            self._log_actions(record)
            return True

        if not self.target_url:
            raise RuntimeError("PlaywrightWorker requires 'target_url' when dry_run is False")

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.logger.warning(
                "Playwright not available; falling back to dry-run for job %s", record.case_id
            )
            self._log_actions(record)
            return True

        with ExitStack() as stack:
            playwright = stack.enter_context(sync_playwright())
            browser = stack.enter_context(playwright.chromium.launch(headless=True))
            page = stack.enter_context(browser.new_page())
            page.goto(self._resolve_target_url(self.target_url))
            page.wait_for_load_state("networkidle")
            self._fill_form(page, job)
            self._capture_proof(page, record.case_id)
        return True

    # --- internal helpers -------------------------------------------------

    def _log_actions(self, record) -> None:
        for field_name, value in record.raw_payload.items():
            if value:
                selector = self.selector(field_name) if field_name in self.mapping.field_to_selector else "<unmapped>"
                self.logger.debug(
                    "Would input %r into %s", value, selector, extra={"job_id": record.case_id}
                )

    def _fill_form(self, page, job: JobItem) -> None:  # pragma: no cover - requires Playwright
        record = job.record
        for field_name, selector in self.mapping.field_to_selector.items():
            value = getattr(record, field_name, None)
            if value is None:
                continue
            self.logger.debug(
                "Filling field %s with value %s", field_name, value, extra={"job_id": record.case_id}
            )
            if field_name == "seriousness":
                if str(value).lower() == "serious":
                    page.check(selector)
                else:
                    page.uncheck(selector)
            elif selector.startswith("textarea"):
                page.fill(selector, str(value))
            elif selector.startswith("select"):
                page.select_option(selector, str(value))
            else:
                page.fill(selector, str(value))
            page.wait_for_timeout(200)  # TODO: replace with toast/response wait

        page.click(self.submit_selector)
        page.wait_for_load_state("networkidle")
        if self.success_selector:
            page.wait_for_selector(self.success_selector, state="visible")

    def _capture_proof(self, page, job_id: str) -> None:  # pragma: no cover - requires Playwright
        screenshot_dir = Path("artifacts/screenshots")
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = screenshot_dir / f"{job_id}.png"
        page.screenshot(path=screenshot_path, full_page=True)
        self.logger.info(
            "Saved screenshot",
            extra={"job_id": job_id, "screenshot": str(screenshot_path)},
        )

    def _resolve_target_url(self, target: str) -> str:
        if target.startswith("http://") or target.startswith("https://") or target.startswith("file://"):
            return target
        path = Path(target).expanduser().resolve()
        return path.as_uri()


__all__ = ["PlaywrightWorker"]
