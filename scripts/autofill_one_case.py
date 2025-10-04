"""Run Playwright to autofill the mock form and persist into SQLite via the server."""
from __future__ import annotations

import argparse
import threading
import time
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from meddra_autofill.ingestion.excel_ingestion import ExcelIngestor
from meddra_autofill.ingestion.normalizer import RecordNormalizer
from meddra_autofill.mapping.ui_mapping import DEFAULT_MAPPING
from meddra_autofill.models import records_from_iterable
from scripts import mock_server


def start_server(port: int) -> mock_server.ThreadingHTTPServer:
    mock_server.init_db()
    httpd = mock_server.ThreadingHTTPServer(("127.0.0.1", port), mock_server.CaseRequestHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.5)
    return httpd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Autofill one case into the mock form")
    parser.add_argument("input_path", help="CSV/Excel file path", nargs="?", default="Raw_Data/MedDRA_________100__.csv")
    parser.add_argument("--index", type=int, default=0, help="Zero-based row index to submit")
    parser.add_argument("--port", type=int, default=8000, help="Port for the local server")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    httpd = start_server(args.port)

    try:
        ingestor = ExcelIngestor()
        normalizer = RecordNormalizer()
        rows = ingestor.load_rows(args.input_path)
        if not rows:
            raise RuntimeError("No rows found in input file")
        if args.index >= len(rows):
            raise IndexError(f"Row index {args.index} is out of range for {len(rows)} records")

        normalized_row = normalizer.normalize_row(rows[args.index])
        record = records_from_iterable([normalized_row])[0]

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=args.headless)
            page = browser.new_page()
            target = f"http://127.0.0.1:{args.port}/"
            page.goto(target)
            page.wait_for_load_state("domcontentloaded")

            for field_name, selector in DEFAULT_MAPPING.field_to_selector.items():
                value = getattr(record, field_name, None)
                if value is None:
                    continue
                text = str(value)
                if field_name == "seriousness":
                    if text.lower().startswith("serious"):
                        page.check(selector)
                    else:
                        if page.is_checked(selector):
                            page.uncheck(selector)
                elif selector.startswith("textarea"):
                    page.fill(selector, text)
                elif selector.startswith("select"):
                    try:
                        page.select_option(selector, label=text)
                    except Exception:
                        page.select_option(selector, value=text)
                else:
                    page.fill(selector, text)
                page.wait_for_timeout(150)

            page.click("button[type=submit]")
            page.wait_for_selector("#status:not([hidden])")
            page.wait_for_timeout(500)
            browser.close()

        print(f"Submitted case {record.case_id} to http://127.0.0.1:{args.port}/")
    finally:
        httpd.shutdown()
        httpd.server_close()
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
