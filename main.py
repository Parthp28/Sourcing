"""Fetch registered career boards concurrently and append new US candidates."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from job_pulse.fetchers import FETCHERS
from job_pulse.filters import Decision, classify_job
from job_pulse.sheet import append_jobs, existing_keys, open_sheet

MAX_WORKERS = 24
PACIFIC_TIME = ZoneInfo("America/Los_Angeles")


def fetch_company(company: dict[str, Any]):
    fetcher = FETCHERS.get(company["ats"])
    if not fetcher:
        raise ValueError(f"unknown ATS {company['ats']}")
    return fetcher(company["name"], company["token"])


def main() -> None:
    with open("config/companies.yaml", encoding="utf-8") as source:
        companies = yaml.safe_load(source)["companies"]

    worksheet = open_sheet()
    seen = existing_keys(worksheet)

    now_utc = datetime.now(timezone.utc)
    discovered = now_utc.astimezone(PACIFIC_TIME).strftime("%Y-%m-%d %H:%M:%S")
    cutoff = (now_utc - timedelta(days=21)).strftime("%Y-%m-%d")

    new_rows: list[list[str]] = []
    errors = 0
    scanned_jobs = 0
    decisions = {decision.value: 0 for decision in Decision}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(fetch_company, company): company for company in companies
        }

        for future in as_completed(futures):
            company = futures[future]

            try:
                jobs = future.result()
            except Exception as error:
                errors += 1
                print(f"error {company['name']}: {error}")
                continue

            scanned_jobs += len(jobs)

            for job in jobs:
                if not job.job_id or not job.url or job.key in seen:
                    continue

                if job.posted and job.posted < cutoff:
                    continue

                result = classify_job(
                    job.title,
                    job.location,
                    job.description,
                )
                decisions[result.decision.value] += 1

                if result.decision == Decision.INELIGIBLE:
                    continue

                seen.add(job.key)
                new_rows.append(
                    [
                        job.company,
                        job.title,
                        job.location,
                        job.work_type,
                        job.posted,
                        discovered,
                        f'=HYPERLINK("{job.url}", "Apply")',
                        job.key,
                        "",
                        "",
                        "",
                        "",
                        result.decision.value,
                        result.reason,
                    ]
                )

            print(f"{company['name']}: {len(jobs)} postings")

    new_rows.sort(
        key=lambda row: (row[4], row[5]),
        reverse=True,
    )
    append_jobs(worksheet, new_rows)

    print(
        f"done: {len(companies)} boards, "
        f"{scanned_jobs} postings, "
        f"{len(new_rows)} new candidates, "
        f"{errors} errors, "
        f"decisions={decisions}"
    )


if __name__ == "__main__":
    main()
