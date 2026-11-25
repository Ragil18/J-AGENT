"""Live Active Job Discovery Engine (100% Free Public ATS & Remote APIs).

Automatically discovers fresh, active openings prioritized by:
  Priority #1: Healthcare, HealthTech, Diagnostics & Clinical Data
  Cross-Industry: PropTech, FinTech, AI Automation, Data Analytics & BI

Uses zero-cost public endpoints (no API keys required):
  - Greenhouse Public Boards API (boards-api.greenhouse.io)
  - Lever Public Postings API (api.lever.co)
  - Remotive Free Remote Jobs API (remotive.com/api/remote-jobs)

Applies strict Experience (0-4 yrs) and Location (India / Global Remote) filters.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [JOB_FINDER %(levelname)s] %(message)s")
logger = logging.getLogger("job_finder")

# ====================================================================
# Curated Public ATS Boards (Priority #1 Healthcare + Cross-Industry)
# ====================================================================

GREENHOUSE_BOARDS = [
    # Priority #1: Healthcare & HealthTech
    ("flatironhealth", "Flatiron Health", "Healthcare"),
    ("tempus", "Tempus AI", "Healthcare"),
    ("oscar", "Oscar Health", "Healthcare"),
    ("komodohealth", "Komodo Health", "Healthcare"),
    ("cedar", "Cedar", "Healthcare"),
    ("hingehealth", "Hinge Health", "Healthcare"),
    ("ro", "Ro", "Healthcare"),
    ("verily", "Verily Life Sciences", "Healthcare"),
    ("color", "Color Health", "Healthcare"),
    ("invitae", "Invitae", "Healthcare"),
    # Cross-Industry: FinTech, AI, SaaS
    ("razorpay", "Razorpay", "FinTech"),
    ("stripe", "Stripe", "FinTech"),
    ("scaleai", "Scale AI", "AI"),
    ("databricks", "Databricks", "Data/AI"),
]

LEVER_BOARDS = [
    # Priority #1: Healthcare & HealthTech
    ("ro", "Ro", "Healthcare"),
    ("color", "Color Health", "Healthcare"),
    ("includedhealth", "Included Health", "Healthcare"),
    # Cross-Industry
    ("nobroker", "NoBroker", "PropTech"),
]

TARGET_ROLE_KEYWORDS = [
    "data analyst",
    "business intelligence",
    "bi developer",
    "bi analyst",
    "power bi",
    "analytics",
    "data operations",
    "operations analyst",
    "automation",
    "ai engineer",
    "python",
    "sql",
    "etl",
    "data engineer",
    "clinical data",
    "healthcare",
    "ehr",
    "computer vision",
    "reporting analyst",
]

EXCLUDED_SENIOR_TITLES = [
    "principal",
    "staff ",
    "director",
    "vice president",
    "vp ",
    "vp,",
    "head of",
    "chief ",
    "senior manager",
    "sr. manager",
    "sr manager",
    "architect",
    "distinguished",
    "fellow",
    "lead ",
    "manager,",
    "engineering manager",
]

ACCEPTED_LOCATIONS = [
    "india",
    "chennai",
    "bengaluru",
    "bangalore",
    "hyderabad",
    "pune",
    "mumbai",
    "noida",
    "gurgaon",
    "gurugram",
    "delhi",
    "remote",
    "worldwide",
    "anywhere",
    "global",
    "apac",
]

US_ONLY_BLOCKERS = [
    "us only",
    "u.s. only",
    "united states only",
    "must be located in the us",
    "must reside in the u.s",
    "us citizenship",
    "u.s. citizen",
    "security clearance",
    "remote - us",
    "remote (us)",
    "remote, us",
    "us - remote",
    "usa remote",
]


def is_role_relevant(title: str) -> bool:
    """Return True if title matches target analytics/automation/healthcare roles and isn't executive/lead."""
    t = title.lower()
    if any(bad in t for bad in EXCLUDED_SENIOR_TITLES):
        return False
    return any(kw in t for kw in TARGET_ROLE_KEYWORDS)


def is_location_compatible(location: str, description: str = "") -> bool:
    """Return True if location is India or Global Remote (excludes US-only onsite/remote)."""
    loc = (location or "").lower()
    desc = (description or "")[:1500].lower()

    # Reject explicit US-only constraints
    if any(b in loc for b in US_ONLY_BLOCKERS) or any(b in desc for b in US_ONLY_BLOCKERS):
        return False

    # Accept explicit India or Global Remote
    if any(ok in loc for ok in ACCEPTED_LOCATIONS):
        # Double-check "Remote" isn't US-state-locked like "Remote - New York, US"
        if "remote" in loc and any(us in loc for us in ["united states", ", us", "(us)", "usa", "new york", "california", "texas", "boston", "san francisco", "chicago"]):
            return False
        return True

    return False


def fetch_greenhouse_jobs(max_age_days: int = 21) -> List[Dict[str, Any]]:
    """Fetch active jobs from public Greenhouse ATS boards."""
    discovered: List[Dict[str, Any]] = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    for slug, company, industry in GREENHOUSE_BOARDS:
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
        try:
            resp = requests.get(url, timeout=8)
            if resp.status_code != 200:
                continue
            jobs = resp.json().get("jobs", [])
            for job in jobs:
                title = job.get("title", "")
                location = (job.get("location") or {}).get("name", "")
                abs_url = job.get("absolute_url", "")
                updated_at = job.get("updated_at", "")

                if not abs_url or not is_role_relevant(title):
                    continue
                if not is_location_compatible(location):
                    continue

                # Freshness filter
                if updated_at:
                    try:
                        dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                        if dt < cutoff:
                            continue
                    except Exception:
                        pass

                discovered.append({
                    "company": company,
                    "industry": industry,
                    "priority": 1 if industry == "Healthcare" else 2,
                    "title": title,
                    "location": location,
                    "url": abs_url,
                    "source": "Greenhouse",
                    "updated_at": updated_at,
                })
        except Exception as e:
            logger.debug(f"Greenhouse board '{slug}' skipped: {e}")

    return discovered


def fetch_lever_jobs() -> List[Dict[str, Any]]:
    """Fetch active jobs from public Lever ATS boards."""
    discovered: List[Dict[str, Any]] = []

    for slug, company, industry in LEVER_BOARDS:
        url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
        try:
            resp = requests.get(url, timeout=8)
            if resp.status_code != 200:
                continue
            jobs = resp.json()
            if not isinstance(jobs, list):
                continue
            for job in jobs:
                title = job.get("text", "")
                location = (job.get("categories") or {}).get("location", "")
                abs_url = job.get("hostedUrl", "")

                if not abs_url or not is_role_relevant(title):
                    continue
                if not is_location_compatible(location):
                    continue

                discovered.append({
                    "company": company,
                    "industry": industry,
                    "priority": 1 if industry == "Healthcare" else 2,
                    "title": title,
                    "location": location,
                    "url": abs_url,
                    "source": "Lever",
                    "updated_at": "",
                })
        except Exception as e:
            logger.debug(f"Lever board '{slug}' skipped: {e}")

    return discovered


def fetch_remotive_jobs(limit: int = 25) -> List[Dict[str, Any]]:
    """Fetch live global remote Data / AI / Healthcare openings from Remotive's free public API."""
    discovered: List[Dict[str, Any]] = []
    queries = ["healthcare data", "data analyst", "python automation", "power bi"]

    seen_urls = set()
    for q in queries:
        try:
            resp = requests.get(
                "https://remotive.com/api/remote-jobs",
                params={"search": q, "limit": limit},
                timeout=10,
            )
            if resp.status_code != 200:
                continue
            jobs = resp.json().get("jobs", [])
            for job in jobs:
                title = job.get("title", "")
                company = job.get("company_name", "Remote Company")
                location = job.get("candidate_required_location", "Worldwide")
                abs_url = job.get("url", "")
                desc = job.get("description", "")

                if not abs_url or abs_url in seen_urls:
                    continue
                if not is_role_relevant(title):
                    continue
                if not is_location_compatible(location, desc):
                    continue

                seen_urls.add(abs_url)
                is_hc = any(k in (title + " " + company + " " + desc[:500]).lower() for k in ["health", "clinical", "medical", "patient", "diagnostic", "pharma", "bio"])
                industry = "Healthcare" if is_hc else "Tech / Remote"

                discovered.append({
                    "company": company,
                    "industry": industry,
                    "priority": 1 if is_hc else 2,
                    "title": title,
                    "location": location,
                    "url": abs_url,
                    "source": "Remotive",
                    "updated_at": job.get("publication_date", ""),
                })
        except Exception as e:
            logger.debug(f"Remotive query '{q}' skipped: {e}")

    return discovered


def discover_live_jobs(max_results: int = 20, write_to_jobs_txt: bool = False) -> List[Dict[str, Any]]:
    """Run all free live job finders, deduplicate, and rank with Priority #1 Healthcare first."""
    logger.info("Scanning live public ATS & Remote job boards (Priority #1 Healthcare + Cross-Industry)...")

    all_jobs: List[Dict[str, Any]] = []
    all_jobs.extend(fetch_greenhouse_jobs())
    all_jobs.extend(fetch_lever_jobs())
    all_jobs.extend(fetch_remotive_jobs())

    # Deduplicate by URL
    unique: Dict[str, Dict[str, Any]] = {}
    for j in all_jobs:
        if j["url"] not in unique:
            unique[j["url"]] = j

    # Sort: Priority #1 (Healthcare) first, then newest
    ranked = sorted(
        unique.values(),
        key=lambda x: (x.get("priority", 2), x.get("company", "")),
    )[:max_results]

    logger.info(
        f"Discovered {len(ranked)} live compatible openings "
        f"({sum(1 for j in ranked if j['priority'] == 1)} Healthcare Priority #1, "
        f"{sum(1 for j in ranked if j['priority'] != 1)} Cross-Industry)."
    )

    out_json = Path("output/live_discovered_jobs.json")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(ranked, indent=2), encoding="utf-8")

    if write_to_jobs_txt and ranked:
        lines = [
            f"# Auto-Discovered Live Job Openings ({datetime.now().strftime('%Y-%m-%d %H:%M')})",
            "# Priority #1: Healthcare & HealthTech | Cross-Industry: PropTech, FinTech, AI & Data",
            "",
        ]
        for j in ranked:
            lines.append(f"# [{j['industry']}] {j['company']} - {j['title']} ({j['location']})")
            lines.append(j["url"])
        Path("jobs.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.info(f"Updated jobs.txt with {len(ranked)} verified live job URLs.")

    return ranked


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live Active Job Finder (Free Public ATS APIs)")
    parser.add_argument("--limit", type=int, default=15, help="Maximum jobs to return")
    parser.add_argument("--update-queue", action="store_true", help="Write discovered live URLs to jobs.txt")
    args = parser.parse_args()

    jobs = discover_live_jobs(max_results=args.limit, write_to_jobs_txt=args.update_queue)
    for idx, j in enumerate(jobs, start=1):
        print(f"{idx:2d}. [{j['industry']}] {j['company']} — {j['title']} ({j['location']})\n    {j['url']}")
