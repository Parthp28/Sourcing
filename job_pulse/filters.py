"""High-recall classification for public job postings."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from enum import StrEnum

TAG_RE = re.compile(r"<[^>]+>")


class Decision(StrEnum):
    APPLY = "Apply"
    REVIEW = "Review"
    INELIGIBLE = "Ineligible"


@dataclass(frozen=True)
class Classification:
    decision: Decision
    reason: str


ROLE_TERMS = (
    "software engineer",
    "software developer",
    "software development engineer",
    "backend engineer",
    "back-end engineer",
    "full stack",
    "fullstack",
    "platform engineer",
    "infrastructure engineer",
    "systems engineer",
    "site reliability engineer",
    "data engineer",
    "analytics engineer",
    "machine learning engineer",
    "ml engineer",
    "artificial intelligence engineer",
    "ai engineer",
    "research engineer",
    "sde",
    "swe",
)
HARD_SENIOR_TERMS = (
    "senior",
    "staff",
    "principal",
    "distinguished",
    "lead",
    "manager",
    "director",
    "head of",
    "architect",
    "vice president",
)
NON_ENGINEERING_TERMS = (
    "sales",
    "marketing",
    "recruiter",
    "designer",
    "customer support",
)
REVIEW_LEVEL_RE = re.compile(r"\b(?:engineer|developer)\s+(?:ii|2)\b", re.I)


def classify_role(title: str) -> Classification:
    text = " ".join(title.lower().split())
    if not any(term in text for term in ROLE_TERMS):
        return Classification(Decision.INELIGIBLE, "title outside target role families")
    if any(term in text for term in NON_ENGINEERING_TERMS):
        return Classification(Decision.INELIGIBLE, "non-engineering title")
    if any(term in text for term in HARD_SENIOR_TERMS):
        return Classification(Decision.INELIGIBLE, "senior or leadership title")
    if REVIEW_LEVEL_RE.search(text):
        return Classification(Decision.REVIEW, "level II title requires review")
    return Classification(Decision.APPLY, "target role family")


US_STATES = (
    "alabama",
    "alaska",
    "arizona",
    "arkansas",
    "california",
    "colorado",
    "connecticut",
    "delaware",
    "florida",
    "georgia",
    "hawaii",
    "idaho",
    "illinois",
    "indiana",
    "iowa",
    "kansas",
    "kentucky",
    "louisiana",
    "maine",
    "maryland",
    "massachusetts",
    "michigan",
    "minnesota",
    "mississippi",
    "missouri",
    "montana",
    "nebraska",
    "nevada",
    "new hampshire",
    "new jersey",
    "new mexico",
    "new york",
    "north carolina",
    "north dakota",
    "ohio",
    "oklahoma",
    "oregon",
    "pennsylvania",
    "rhode island",
    "south carolina",
    "south dakota",
    "tennessee",
    "texas",
    "utah",
    "vermont",
    "virginia",
    "washington",
    "west virginia",
    "wisconsin",
    "wyoming",
    "district of columbia",
)
US_STATE_CODES_RE = re.compile(
    r"(?:,\s*|\b)(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|"
    r"MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|"
    r"TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)(?:\b|,)",
    re.I,
)
FOREIGN_MARKERS = (
    "united kingdom",
    "canada",
    "india",
    "germany",
    "france",
    "poland",
    "japan",
    "australia",
    "netherlands",
    "singapore",
    "ireland",
    "israel",
    "spain",
    "sweden",
    "norway",
    "denmark",
    "finland",
    "lithuania",
    "estonia",
    "south korea",
    "united arab emirates",
    "brazil",
    "mexico",
    "argentina",
    "switzerland",
    "austria",
    "italy",
    "portugal",
    "belgium",
    "china",
    "taiwan",
    "hong kong",
    "philippines",
    "indonesia",
    "vietnam",
    "thailand",
    "new zealand",
    "colombia",
    "chile",
    "nigeria",
    "egypt",
    "turkey",
    "hungary",
    "czechia",
    "czech republic",
    "romania",
    "bulgaria",
    "serbia",
    "croatia",
    "greece",
    "ukraine",
    "russia",
    "pakistan",
    "bangladesh",
    "sri lanka",
    "malaysia",
    "emea",
    "apac",
    "latam",
    "london",
    "toronto",
    "vancouver",
    "montreal",
    "bangalore",
    "bengaluru",
    "hyderabad",
    "pune",
    "mumbai",
    "delhi",
    "chennai",
    "gurgaon",
    "dublin",
    "paris",
    "berlin",
    "munich",
    "amsterdam",
    "tokyo",
    "sydney",
    "melbourne",
    "tel aviv",
    "warsaw",
    "zurich",
    "seoul",
    "sao paulo",
    "mexico city",
    "dubai",
    "oslo",
    "stockholm",
    "copenhagen",
    "madrid",
    "barcelona",
    "vilnius",
    "krakow",
    "lisbon",
    "budapest",
    "prague",
    "bucharest",
)
US_MARKERS_RE = re.compile(
    r"\b(?:united states(?: of america)?|u\.s\.a\.?|usa|us[- ]only|"
    r"remote[- ]us|us[- ]remote)\b",
    re.I,
)


def classify_location(location: str) -> Classification:
    raw = " ".join((location or "").split())
    text = raw.lower()
    if not text:
        return Classification(Decision.REVIEW, "missing location")
    if any(marker in text for marker in FOREIGN_MARKERS):
        return Classification(Decision.INELIGIBLE, "explicit non-US location")
    if US_MARKERS_RE.search(raw):
        return Classification(Decision.APPLY, "explicit US location")
    if any(re.search(rf"\b{re.escape(state)}\b", text) for state in US_STATES):
        return Classification(Decision.APPLY, "recognized US state")
    if US_STATE_CODES_RE.search(raw):
        return Classification(Decision.APPLY, "recognized US state code")
    if "remote" in text:
        return Classification(Decision.REVIEW, "remote geography is ambiguous")
    return Classification(Decision.REVIEW, "location is not explicitly US")


TEMPLATE_SIGNALS = (
    "<job title>",
    "insert date",
    "xxx,xxx",
    "job function>",
    "[option a",
    "[option b",
    "specify education, previous job",
    "begin each bullet with an action",
)
CLEARANCE_SIGNALS = (
    "active security clearance",
    "active clearance",
    "top secret",
    "ts/sci",
    "must be a u.s. citizen",
    "must be a us citizen",
    "u.s. citizenship required",
    "us citizenship required",
    "citizenship required",
    "polygraph",
)
NO_SPONSORSHIP_SIGNALS = (
    "not able to sponsor",
    "unable to sponsor",
    "cannot sponsor",
    "does not sponsor",
    "do not sponsor",
    "no visa sponsorship",
    "not provide visa sponsorship",
    "not sponsor visas",
    "without visa sponsorship",
    "sponsorship is not available",
    "not offer sponsorship",
    "unable to provide sponsorship",
)


def clean_text(value: str) -> str:
    return " ".join(html.unescape(TAG_RE.sub(" ", value or "")).lower().split())


def classify_description(title: str, description: str) -> Classification:
    text = clean_text(f"{title} {description}")
    if any(signal in text for signal in TEMPLATE_SIGNALS):
        return Classification(Decision.INELIGIBLE, "template or unfinished posting")
    if any(signal in text for signal in CLEARANCE_SIGNALS):
        return Classification(
            Decision.INELIGIBLE, "citizenship or active-clearance requirement"
        )
    if any(signal in text for signal in NO_SPONSORSHIP_SIGNALS):
        return Classification(Decision.INELIGIBLE, "explicitly unavailable sponsorship")
    years = [int(value) for value in re.findall(r"\b(\d{1,2})\+?\s+years?\b", text)]
    years = [value for value in years if value <= 20]
    if years and min(years) >= 4:
        return Classification(
            Decision.INELIGIBLE, "minimum experience appears to be 4+ years"
        )
    if years and min(years) >= 2:
        return Classification(
            Decision.REVIEW, "minimum experience appears to be 2-3 years"
        )
    return Classification(Decision.APPLY, "no blocking requirement detected")


def combine(*items: Classification) -> Classification:
    for item in items:
        if item.decision == Decision.INELIGIBLE:
            return item
    reviews = [item.reason for item in items if item.decision == Decision.REVIEW]
    if reviews:
        return Classification(Decision.REVIEW, "; ".join(reviews))
    return Classification(
        Decision.APPLY, "eligible target role with explicit US location"
    )


def classify_job(title: str, location: str, description: str) -> Classification:
    return combine(
        classify_role(title),
        classify_location(location),
        classify_description(title, description),
    )


def is_relevant(title: str) -> bool:
    return classify_role(title).decision != Decision.INELIGIBLE


def is_us(location: str) -> bool:
    return classify_location(location).decision == Decision.APPLY
