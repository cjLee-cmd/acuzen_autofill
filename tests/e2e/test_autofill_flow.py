"""End-to-end test scenario for the MedDRA autofill workflow."""
from __future__ import annotations

import json
import sqlite3
import sys
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

# Ensure project modules are importable
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))
if str(ROOT_DIR / "src") not in sys.path:
    sys.path.append(str(ROOT_DIR / "src"))

from scripts import mock_server  # noqa: E402

DB_PATH = ROOT_DIR / "artifacts/mock_cases.db"
DATA_PATH = ROOT_DIR / "Raw_Data/MedDRA_________100__.csv"
PORT = 8000
BASE_URL = f"http://127.0.0.1:{PORT}/"


def _start_server() -> tuple[mock_server.ThreadingHTTPServer, threading.Thread]:
    mock_server.init_db()
    server = mock_server.ThreadingHTTPServer(("127.0.0.1", PORT), mock_server.CaseRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.7)  # allow server to bind
    return server, thread


def _stop_server(server: mock_server.ThreadingHTTPServer, thread: threading.Thread) -> None:
    server.shutdown()
    thread.join(timeout=5)
    server.server_close()


def _reset_db() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()


def run_scenario() -> None:
    """Execute the E2E scenario: upload file, submit case, verify DB."""
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Test data file not found: {DATA_PATH}")

    _reset_db()
    server, thread = _start_server()

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(BASE_URL)

            file_input = page.locator("#fileInput")
            file_input.set_input_files(str(DATA_PATH))

            page.wait_for_selector("tbody tr.record-row", timeout=10000)

            # Select the first record and verify form population
            first_row = page.locator("tbody tr.record-row").first
            first_row.click()
            case_id = page.locator("#caseId").input_value()
            if not case_id:
                raise AssertionError("Form did not populate Case ID after selecting a record")

            # Submit the form and wait for status feedback
            page.click("button[type=submit]")
            page.wait_for_selector("#status:not([hidden])", timeout=10000)
            page.wait_for_function(
                "() => document.querySelector('#status').textContent.includes('Saved case')",
                timeout=10000,
            )
            status_text = page.locator("#status").inner_text()

            # Verify the row is marked as saved
            saved_row = page.locator("tbody tr.record-row.is-saved")
            saved_row.wait_for(timeout=5000)

            browser.close()

        # Validate DB contents against the source CSV first row
        with DATA_PATH.open("r", encoding="utf-8-sig") as handle:
            header = handle.readline().strip().split(",")
            first_data_line = handle.readline().strip().split(",")
            source_row = dict(zip(header, first_data_line))

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM cases WHERE case_id = ?", (source_row["case_id"],)).fetchone()
            if row is None:
                raise AssertionError("Case not found in database after submission")
            db_record = dict(row)

        mismatches = {}
        expected = {
            "reaction_reported_term": source_row.get("reaction_term"),
            "meddra_level": "PT",
            "meddra_term_text": source_row.get("reaction_term"),
            "meddra_code": source_row.get("reaction_code"),
            "meddra_version": "MOCK-1.0",
            "onset_date": source_row.get("onset_date"),
            "seriousness": source_row.get("seriousness"),
            "suspect_drug": source_row.get("drug_name"),
            "dose_text": source_row.get("dose", ""),
            "outcome": source_row.get("outcome"),
            "narrative": source_row.get("indication", ""),
        }
        for key, expected_value in expected.items():
            db_value = db_record.get(key)
            if (expected_value or "") != (db_value or ""):
                mismatches[key] = {"expected": expected_value, "actual": db_value}

        if mismatches:
            raise AssertionError(f"Database values did not match expected fields: {json.dumps(mismatches, ensure_ascii=False)}")

        print("E2E scenario passed: upload, submit, and DB verification succeeded.")
    finally:
        _stop_server(server, thread)


if __name__ == "__main__":  # pragma: no cover
    run_scenario()
