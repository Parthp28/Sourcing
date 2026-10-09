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

    last_error = None
    for attempt in range(4):
        try:
            ws = client.open_by_key(os.environ["SHEET_ID"]).sheet1

            # Always enforce the expected header.
            # This only updates row 1 and does not touch job/application data.
            current_header = ws.row_values(1)

            if current_header != HEADER:
                print("Sheet header differs from expected schema. Fixing row 1...")
                ws.update(values=[HEADER], range_name="A1:N1")

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
