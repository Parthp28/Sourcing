"""Test every company in config/companies.yaml against its live API and
rewrite the file keeping only the ones that actually respond with real
job data. Run this locally whenever you want to clean out dead tokens
instead of pruning by hand from error output.

Usage:
    python3 scripts/verify_companies.py

Writes a backup to config/companies.yaml.bak before overwriting, and
prints a summary of what was kept vs dropped.
"""

import shutil
import sys

import requests
import yaml

TIMEOUT = 15
URLS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{}/jobs",
    "lever": "https://api.lever.co/v0/postings/{}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{}",
    "smartrecruiters": "https://api.smartrecruiters.com/v1/companies/{}/postings",
    "workable": "https://apply.workable.com/api/v1/widget/accounts/{}",
    "recruitee": "https://{}.recruitee.com/api/offers/",
}


def check(company: dict) -> tuple[bool, str]:
    ats = company["ats"]
    if ats not in URLS:
        return True, "skipped (non-standard ats, kept as-is)"
    url = URLS[ats].format(company["token"])
    try:
        r = requests.get(url, timeout=TIMEOUT)
        data = r.json()
    except Exception as e:
        return False, f"request failed: {e}"
    if ats == "lever":
        ok = isinstance(data, list)
    else:
        ok = isinstance(data, dict) and data.get("jobs") is not None
    if not ok:
        return False, f"invalid response: {str(data)[:80]}"
    count = len(data) if ats == "lever" else len(data.get("jobs", []))
    if count == 0:
        return False, "0 postings (empty board)"
    return True, f"{count} postings"


def main() -> None:
    path = "config/companies.yaml"
    with open(path) as f:
        cfg = yaml.safe_load(f)
    companies = cfg["companies"]

    kept, dropped = [], []
    for i, c in enumerate(companies, 1):
        ok, detail = check(c)
        status = "OK  " if ok else "DROP"
        print(f"[{i}/{len(companies)}] {status} {c['name']:30} {detail}")
        (kept if ok else dropped).append(c)

    shutil.copy(path, path + ".bak")
    with open(path, "w") as f:
        f.write("# Verified working companies as of last run of verify_companies.py\n")
        f.write("# Backup of the previous file saved to companies.yaml.bak\n\n")
        yaml.safe_dump({"companies": kept}, f, default_flow_style=None, sort_keys=False)

    print(f"\ndone: {len(kept)} kept, {len(dropped)} dropped")
    if dropped:
        print("dropped:", ", ".join(c["name"] for c in dropped))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print(__doc__)
    else:
        main()
