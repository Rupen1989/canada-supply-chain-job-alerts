"""
Canada Supply Chain Job Alert
Job discovery and normalization engine.

Search scope:
- All British Columbia
- Chilliwack priority
- Calgary + 70 km
- Public + private employers
- Government + municipal + job boards + recruiters
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]

LOCATIONS_FILE = ROOT / "config" / "locations.json"
TITLES_FILE = ROOT / "config" / "job_titles.json"
SOURCES_FILE = ROOT / "config" / "sources.json"


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0 Safari/537.36"
    )
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def clean_text(text):
    if not text:
        return ""

    return re.sub(r"\s+", " ", text).strip()


def normalize_url(base_url, href):
    if not href:
        return ""

    return urljoin(base_url, href)


def fetch_page(url, timeout=20):
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=timeout,
            allow_redirects=True,
        )

        response.raise_for_status()

        return response.text

    except requests.RequestException as exc:
        print(f"[WARN] Could not fetch {url}: {exc}")
        return None


def extract_links(html, base_url):
    """
    Extract links from a normal HTML job page.

    This intentionally does not assume a specific job-board structure.
    Each source can later receive its own specialized parser.
    """

    soup = BeautifulSoup(html, "html.parser")
    results = []

    for link in soup.find_all("a", href=True):
        title = clean_text(link.get_text(" ", strip=True))
        href = normalize_url(base_url, link.get("href"))

        if not title or not href:
            continue

        results.append(
            {
                "title": title,
                "url": href,
            }
        )

    return results


def looks_like_job(title, job_titles):
    """
    Broad first-pass filter.

    We intentionally keep this broad because the resume matcher
    will perform the more sophisticated scoring later.
    """

    title_lower = title.lower()

    keywords = []

    keywords.extend(job_titles.get("primary", []))
    keywords.extend(job_titles.get("secondary", []))
    keywords.extend(job_titles.get("keywords", []))

    return any(
        keyword.lower() in title_lower
        for keyword in keywords
    )


def classify_source(source):
    source_type = source.get("type", "unknown")

    if source_type == "government":
        return "Public - Government"

    if source_type == "municipal":
        return "Public - Municipal"

    if source_type == "recruiter":
        return "Recruitment Agency"

    if source_type == "job_board":
        return "Job Board"

    return "Private / Other"


def create_job_record(source, link):
    return {
        "title": link["title"],
        "url": link["url"],
        "source": source["name"],
        "source_type": classify_source(source),
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        "location": "",
        "company": "",
        "description": "",
        "salary": "",
    }


def scrape_source(source, job_titles):
    print(f"\n[INFO] Checking: {source['name']}")

    html = fetch_page(source["url"])

    if not html:
        return []

    links = extract_links(html, source["url"])

    jobs = []

    for link in links:

        if looks_like_job(link["title"], job_titles):

            jobs.append(
                create_job_record(
                    source,
                    link,
                )
            )

    print(
        f"[INFO] {source['name']}: "
        f"{len(jobs)} possible jobs discovered"
    )

    return jobs


def deduplicate_jobs(jobs):
    """
    Remove duplicate postings.

    URL is the strongest identifier.
    Normalized title + source is the fallback.
    """

    seen_urls = set()
    seen_fallback = set()

    unique_jobs = []

    for job in jobs:

        url = job.get("url", "").rstrip("/").lower()

        fallback = (
            job.get("source", "").lower(),
            clean_text(job.get("title", "")).lower(),
        )

        if url and url in seen_urls:
            continue

        if fallback in seen_fallback:
            continue

        if url:
            seen_urls.add(url)

        seen_fallback.add(fallback)

        unique_jobs.append(job)

    return unique_jobs


def scrape_all_sources():
    locations = load_json(LOCATIONS_FILE)
    job_titles = load_json(TITLES_FILE)
    sources = load_json(SOURCES_FILE)

    print("==========================================")
    print(" Canada Supply Chain Job Alert")
    print("==========================================")

    print("\nSearch coverage:")
    print("- British Columbia: ALL")
    print("- Chilliwack: PRIORITY")
    print("- Calgary: 70 km radius")

    all_jobs = []

    for category, source_list in sources.items():

        print(f"\n--- {category.upper()} ---")

        for source in source_list:

            jobs = scrape_source(
                source,
                job_titles,
            )

            all_jobs.extend(jobs)

    unique_jobs = deduplicate_jobs(all_jobs)

    print("\n==========================================")
    print(f"Total discovered: {len(all_jobs)}")
    print(f"Unique jobs:      {len(unique_jobs)}")
    print("==========================================")

    return unique_jobs


if __name__ == "__main__":
    jobs = scrape_all_sources()

    output_file = ROOT / "data_jobs_raw.json"

    with open(
        output_file,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            jobs,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\nSaved results to: {output_file}")
