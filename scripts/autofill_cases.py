"""Autofill multiple cases into the mock form using Playwright."""
from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

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
    parser = argparse.ArgumentParser(description="Autofill multiple cases into the mock form")
    parser.add_argument("input_path", nargs="?", default="Raw_Data/MedDRA_________100__.csv")
    parser.add_argument("--count", type=int, default=10, help="Number of rows to submit")
    parser.add_argument("--start", type=int, default=0, help="Zero-based row index to start from")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--headless", action="store_true")
    return parser.parse_args()


def fill_record(page, record) -> None:
    for field_name, selector in DEFAULT_MAPPING.field_to_selector.items():
        value = getattr(record, field_name, None)
        if value is None:
            # ensure checkbox unchecked when seriousness not serious
            if field_name == "seriousness" and page.is_checked(selector):
                page.uncheck(selector)
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
        page.wait_for_timeout(120)

    page.click("button[type=submit]")
    page.wait_for_selector("#status:not([hidden])")
    page.wait_for_timeout(200)


def main() -> int:
    args = parse_args()
    httpd = start_server(args.port)

    try:
        ingestor = ExcelIngestor()
        normalizer = RecordNormalizer()
        rows = ingestor.load_rows(args.input_path)
        if not rows:
            raise RuntimeError("No rows found in input file")

        end_index = min(args.start + args.count, len(rows))
        if args.start >= len(rows):
            raise IndexError(f"Start index {args.start} >= total rows {len(rows)}")

        records = []
        for row in rows[args.start:end_index]:
            normalized = normalizer.normalize_row(row)
            records.extend(records_from_iterable([normalized]))

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=args.headless)
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{args.port}/")
            page.wait_for_load_state("domcontentloaded")

            for record in records:
                fill_record(page, record)
                page.wait_for_timeout(300)
                page.reload()
                page.wait_for_load_state("domcontentloaded")

            browser.close()

        print(f"Submitted {len(records)} cases (case_ids: {[r.case_id for r in records]})")
    finally:
        httpd.shutdown()
        httpd.server_close()
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
