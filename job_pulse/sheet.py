"""Append new jobs to a Google Sheet and read existing keys for dedup.
The sheet is the single source of truth: the script only ever appends
rows, so manual tracking columns are never overwritten."""

import json
import os
import time

import gspread

HEADER = [
    "Company",
    "Role",
    "Location",
    "Work Type",
    "Posted",
    "Discovered",
    "Apply Link",
    "Job Key",
    "Status",
    "Applied Date",
    "Notes",
    "Resume",
    "Classification",
    "Classification Reason",
]
KEY_COL = HEADER.index("Job Key") + 1


def open_sheet():
    creds = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    client = gspread.service_account_from_dict(creds)
    # Why: Google Sheets occasionally returns transient 503s under load —
    # retrying with backoff avoids failing an entire scan over a blip.
    last_error = None
    for attempt in range(4):
        try:
            ws = client.open_by_key(os.environ["SHEET_ID"]).sheet1
            current_header = ws.row_values(1)
            print(f"ACTUAL SHEET HEADER: {current_header!r}")
            print(f"EXPECTED HEADER:     {HEADER!r}")

            if not current_header:
                ws.append_row(HEADER)
            elif current_header != HEADER:
                if current_header == HEADER[: len(current_header)]:
                    ws.update(values=[HEADER], range_name="A1:N1")
                else:
                    raise ValueError(
                        "Sheet header does not match the expected Job Pulse schema. "
                        "Use a new sheet or migrate the header before scanning."
                    )
            return ws
        except gspread.exceptions.APIError as e:
            last_error = e
            wait = 2**attempt
            print(
                f"Sheets API error (attempt {attempt + 1}/4), retrying in {wait}s: {e}"
            )
            time.sleep(wait)
    raise last_error


def existing_keys(ws) -> set[str]:
    return set(ws.col_values(KEY_COL)[1:])


def append_jobs(ws, rows: list[list[str]]) -> None:
    if rows:
        # Why: inserting at row 2 keeps the newest postings on top while
        # existing rows shift down intact, so manual Status/Notes entries
        # stay attached to their jobs. One batched insert stays inside the
        # Sheets API write quota of 60 calls per minute.
        ws.insert_rows(rows, row=2, value_input_option="USER_ENTERED")
