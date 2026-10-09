"""Fetch job postings from public ATS JSON endpoints. Each fetcher returns
a list of Job objects for one company. All endpoints are unauthenticated
public job board APIs, so a plain GET is enough and no browser is needed."""

from dataclasses import dataclass
from datetime import datetime, timezone

import requests

TIMEOUT = 20
HEADERS = {"User-Agent": "job-pulse/1.0"}


@dataclass
class Job:
    company: str
    title: str
    location: str
    work_type: str
    posted: str
    url: str
    job_id: str
    description: str = ""

    @property
    def key(self) -> str:
        # Why: company + ATS job id is stable across runs and unique enough
        # for dedup, while URLs sometimes gain tracking params and titles repeat.
        return f"{self.company}:{self.job_id}"


def _work_type(location: str, title: str, explicit: str = "") -> str:
    text = f"{explicit} {location} {title}".lower()
    if "remote" in text:
        return "Remote"
    if "hybrid" in text:
        return "Hybrid"
    return "Onsite"


def _iso_date(ts_ms: int | None) -> str:
    if not ts_ms:
        return ""
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def fetch_greenhouse(company: str, token: str) -> list[Job]:
    # Why: content=true makes the response larger but is the only way the
    # list endpoint returns first_published, the real posting date.
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
    data = requests.get(url, headers=HEADERS, timeout=TIMEOUT).json()
    jobs = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        jobs.append(Job(
            company=company,
            title=j.get("title", ""),
            location=loc,
            work_type=_work_type(loc, j.get("title", "")),
            posted=(j.get("first_published") or j.get("updated_at") or "")[:10],
            url=j.get("absolute_url", ""),
            job_id=str(j.get("id", "")),
            description=j.get("content", "") or "",
        ))
    return jobs


def fetch_lever(company: str, token: str) -> list[Job]:
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    data = requests.get(url, headers=HEADERS, timeout=TIMEOUT).json()
    # Why: Lever returns an error dict instead of a list for unknown tokens,
    # so failing here with the message beats a confusing attribute error.
    if isinstance(data, dict):
        raise ValueError(f"lever token '{token}' invalid: {data}")
    jobs = []
    for j in data:
        loc = (j.get("categories") or {}).get("location", "") or ""
        jobs.append(Job(
            company=company,
            title=j.get("text", ""),
            location=loc,
            work_type=_work_type(loc, j.get("text", ""), j.get("workplaceType", "")),
            posted=_iso_date(j.get("createdAt")),
            url=j.get("hostedUrl", ""),
            job_id=str(j.get("id", "")),
            description=(j.get("descriptionPlain", "") or "") + " " + " ".join(
                (li.get("content", "") or "") for li in (j.get("lists") or [])),
        ))
    return jobs


def fetch_ashby(company: str, token: str) -> list[Job]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
    data = requests.get(url, headers=HEADERS, timeout=TIMEOUT).json()
    jobs = []
    for j in data.get("jobs", []):
        loc = j.get("location", "") or ""
        explicit = "remote" if j.get("isRemote") else ""
        jobs.append(Job(
            company=company,
            title=j.get("title", ""),
            location=loc,
            work_type=_work_type(loc, j.get("title", ""), explicit),
            posted=(j.get("publishedAt") or "")[:10],
            url=j.get("jobUrl", "") or j.get("applyUrl", ""),
            job_id=str(j.get("id", "")),
            description=j.get("descriptionHtml", "") or "",
        ))
    return jobs


def fetch_workday(company: str, token: str) -> list[Job]:
    """token format: "tenant/site", e.g. "amazon/UK".
    Why: Workday has no public discovery endpoint — the tenant and site
    slugs must be read out of the company's actual careers page URL
    (https://<tenant>.wdN.myworkdayjobs.com/<site>/...), then entered
    here manually. The shard number (wd1, wd3, wd5...) varies per tenant
    and isn't guessable, so this tries the common ones in turn."""
    if "/" not in token:
        raise ValueError(f"workday token '{token}' must be 'tenant/site'")
    tenant, site = token.split("/", 1)
    payload = {"appliedFacets": {}, "limit": 100, "offset": 0, "searchText": ""}
    last_error = None
    for shard in ("wd1", "wd3", "wd5"):
        url = f"https://{tenant}.{shard}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
        try:
            r = requests.post(url, json=payload, headers=HEADERS, timeout=TIMEOUT)
            data = r.json()
            if "jobPostings" in data:
                jobs = []
                for j in data["jobPostings"]:
                    loc = j.get("locationsText", "") or ""
                    path = j.get("externalPath", "")
                    jobs.append(Job(
                        company=company,
                        title=j.get("title", ""),
                        location=loc,
                        work_type=_work_type(loc, j.get("title", "")),
                        posted=(j.get("startDate") or "")[:10],
                        url=f"https://{tenant}.{shard}.myworkdayjobs.com/{site}{path}",
                        job_id=path.split("_")[-1] if "_" in path else path,
                    ))
                return jobs
            last_error = str(data)[:100]
        except Exception as e:
            last_error = str(e)[:100]
    raise ValueError(f"workday tenant '{tenant}/{site}' failed on all shards: {last_error}")


def fetch_amazon(company: str, token: str) -> list[Job]:
    """token is the search query, e.g. "software development engineer".
    Why: amazon.jobs has no board-per-team structure like Greenhouse — it's
    one big searchable index, so the token here is a search phrase instead
    of a company slug, and results are paginated 100 at a time."""
    jobs = []
    offset = 0
    while offset < 300:  # cap at 300 to keep one run fast
        url = "https://www.amazon.jobs/en/search.json"
        params = {
            "base_query": token,
            "country": "USA",
            "result_limit": 100,
            "offset": offset,
            "sort": "recent",
        }
        r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        data = r.json()
        batch = data.get("jobs", [])
        if not batch:
            break
        for j in batch:
            loc = j.get("normalized_location", "") or ""
            path = j.get("job_path", "")
            jobs.append(Job(
                company=company,
                title=j.get("title", ""),
                location=loc,
                work_type=_work_type(loc, j.get("title", "")),
                posted=(j.get("posted_date") or "")[:10],
                url=f"https://www.amazon.jobs{path}" if path else "",
                job_id=str(j.get("id_icims", "") or j.get("job_id", "")),
                description=j.get("description_short", "") or "",
            ))
        offset += 100
    return jobs


def fetch_smartrecruiters(company: str, token: str) -> list[Job]:
    """SmartRecruiters public API — token is the company's SmartRecruiters slug."""
    url = f"https://api.smartrecruiters.com/v1/companies/{token}/postings"
    data = requests.get(url, headers=HEADERS, timeout=TIMEOUT).json()
    jobs = []
    for j in data.get("content", []):
        loc_obj = j.get("location") or {}
        loc = ", ".join(filter(None, [loc_obj.get("city"), loc_obj.get("region"), loc_obj.get("country")]))
        remote = loc_obj.get("remote", False)
        jobs.append(Job(
            company=company,
            title=j.get("name", ""),
            location=loc,
            work_type=_work_type(loc, j.get("name", ""), "remote" if remote else ""),
            posted=(j.get("releasedDate") or j.get("createdOn") or "")[:10],
            url=f"https://jobs.smartrecruiters.com/{token}/{j.get('id', '')}",
            job_id=str(j.get("id", "")),
        ))
    return jobs


def fetch_workable(company: str, token: str) -> list[Job]:
    """Workable public widget API — token is the account subdomain."""
    url = f"https://apply.workable.com/api/v1/widget/accounts/{token}?details=true"
    data = requests.get(url, headers=HEADERS, timeout=TIMEOUT).json()
    jobs = []
    for j in data.get("jobs", []):
        loc = j.get("location", {}).get("location_str", "") if isinstance(j.get("location"), dict) else ""
        jobs.append(Job(
            company=company,
            title=j.get("title", ""),
            location=loc,
            work_type=_work_type(loc, j.get("title", ""), "remote" if j.get("telecommuting") else ""),
            posted=(j.get("published_on") or "")[:10],
            url=j.get("url", "") or j.get("shortlink", ""),
            job_id=str(j.get("id", "") or j.get("shortcode", "")),
            description=j.get("description", "") or "",
        ))
    return jobs


def fetch_recruitee(company: str, token: str) -> list[Job]:
    """Recruitee public API — token is the company's Recruitee subdomain."""
    url = f"https://{token}.recruitee.com/api/offers/"
    data = requests.get(url, headers=HEADERS, timeout=TIMEOUT).json()
    jobs = []
    for j in data.get("offers", []):
        loc = j.get("location", "") or ""
        remote = j.get("remote", False)
        jobs.append(Job(
            company=company,
            title=j.get("title", ""),
            location=loc,
            work_type=_work_type(loc, j.get("title", ""), "remote" if remote else ""),
            posted=(j.get("published_at") or j.get("created_at") or "")[:10],
            url=j.get("careers_url", "") or f"https://{token}.recruitee.com/o/{j.get('slug', '')}",
            job_id=str(j.get("id", "")),
            description=j.get("description", "") or "",
        ))
    return jobs

FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "workday": fetch_workday,
    "amazon": fetch_amazon,
    "smartrecruiters": fetch_smartrecruiters,
    "workable": fetch_workable,
    "recruitee": fetch_recruitee,
}
