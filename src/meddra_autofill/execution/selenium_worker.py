"""Selenium-based UI worker implementation (scaffold)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .base_worker import BaseUIWorker
from ..queue.job_queue import JobItem

try:  # pragma: no cover - optional dependency
    from selenium import webdriver  # type: ignore
    from selenium.common.exceptions import WebDriverException  # type: ignore
    from selenium.webdriver.remote.webdriver import WebDriver  # type: ignore
    from selenium.webdriver.support.ui import Select  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    webdriver = None  # type: ignore
    WebDriver = object  # type: ignore
    WebDriverException = Exception  # type: ignore
    Select = None  # type: ignore


class SeleniumWorker(BaseUIWorker):
    """Processes jobs using Selenium WebDriver.

    This is a scaffold. It assumes the presence of a compatible webdriver binary
    (e.g., chromedriver). When Selenium is unavailable, the worker downgrades to
    logging-only behaviour so the pipeline can still run.
    """

    def __init__(
        self,
        *args,
        driver: Optional[WebDriver] = None,
        headless: bool = True,
        screenshot_dir: str | Path = "artifacts/screenshots",
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._driver = driver
        self.headless = headless
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    def process_job(self, job: JobItem) -> bool:
        record = job.record

        if webdriver is None:
            self.logger.warning(
                "Selenium not available; skipping real automation for job %s", record.case_id
            )
            return True

        driver = self._ensure_driver()
        try:
            self.logger.info("Processing job via Selenium", extra={"job_id": record.case_id})
            self._fill_form(driver, job)
            self._capture_proof(driver, record.case_id)
            return True
        except WebDriverException as exc:  # pragma: no cover - runtime failure path
            self.logger.exception("Selenium failure", extra={"job_id": record.case_id})
            raise RuntimeError(str(exc))

    def _ensure_driver(self) -> WebDriver:
        if self._driver:
            return self._driver
        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        self._driver = webdriver.Chrome(options=options)
        return self._driver

    def _fill_form(self, driver: WebDriver, job: JobItem) -> None:  # pragma: no cover - requires Selenium
        record = job.record
        for field_name, selector in self.mapping.field_to_selector.items():
            value = getattr(record, field_name, None)
            if value is None:
                continue
            element = driver.find_element("css selector", selector)
            if element.tag_name == "select" and Select is not None:
                Select(element).select_by_value(str(value))
            elif element.get_attribute("type") == "checkbox":
                should_check = str(value).lower() == "serious"
                if element.is_selected() != should_check:
                    element.click()
            else:
                element.clear()
                element.send_keys(str(value))

        submit = driver.find_element("css selector", "button[type=submit]")
        submit.click()

    def _capture_proof(self, driver: WebDriver, job_id: str) -> None:  # pragma: no cover - requires Selenium
        screenshot_path = self.screenshot_dir / f"{job_id}.png"
        driver.save_screenshot(str(screenshot_path))
        self.logger.info(
            "Saved screenshot", extra={"job_id": job_id, "screenshot": str(screenshot_path)}
        )


__all__ = ["SeleniumWorker"]
