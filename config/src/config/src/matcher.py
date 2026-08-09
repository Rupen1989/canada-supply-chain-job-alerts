import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PROFILE_FILE = ROOT / "config" / "candidate_profile.json"


def load_profile():
    with open(PROFILE_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def normalize(text):
    if not text:
        return ""

    return re.sub(r"\s+", " ", text.lower()).strip()


def keyword_matches(text, keywords):
    text = normalize(text)

    matches = []

    for keyword in keywords:
        if normalize(keyword) in text:
            matches.append(keyword)

    return matches


def calculate_score(job):
    profile = load_profile()

    title = normalize(job.get("title", ""))
    description = normalize(job.get("description", ""))
    location = normalize(job.get("location", ""))

    combined_text = f"{title} {description}"

    score = 0
    reasons = []

    # ---------------------------------------------------------
    # TITLE MATCH — highest importance
    # ---------------------------------------------------------

    for role in profile["target_roles"]:

        if normalize(role) in title:

            score += 30

            reasons.append(
                f"Target role: {role}"
            )

            break

    # ---------------------------------------------------------
    # EXPERIENCE MATCH
    # ---------------------------------------------------------

    category_weights = {
        "leadership": 10,
        "supply_chain": 15,
        "inventory": 10,
        "operations": 10,
        "technology": 5,
        "3pl": 10
    }

    for category, keywords in profile["experience_keywords"].items():

        matches = keyword_matches(
            combined_text,
            keywords
        )

        if matches:

            score += category_weights.get(
                category,
                5
            )

            reasons.append(
                f"{category}: "
                + ", ".join(matches[:5])
            )

    # ---------------------------------------------------------
    # INDUSTRY MATCH
    # ---------------------------------------------------------

    industry_matches = keyword_matches(
        combined_text,
        profile["preferred_industries"]
    )

    if industry_matches:

        score += 5

        reasons.append(
            "Industry: "
            + ", ".join(industry_matches[:4])
        )

    # ---------------------------------------------------------
    # LOCATION
    # ---------------------------------------------------------

    bc_locations = [
        "british columbia",
        "bc",
        "vancouver",
        "burnaby",
        "richmond",
        "surrey",
        "delta",
        "langley",
        "abbotsford",
        "chilliwack",
        "coquitlam",
        "kelowna",
        "kamloops",
        "victoria",
        "nanaimo",
        "prince george"
    ]

    calgary_locations = [
        "calgary",
        "airdrie",
        "cochrane",
        "okotoks",
        "chestermere"
    ]

    if any(city in location for city in bc_locations):

        score += 10

        reasons.append(
            "British Columbia location"
        )

    elif any(city in location for city in calgary_locations):

        score += 10

        reasons.append(
            "Calgary-area location"
        )

    # Cap score at 100

    score = min(score, 100)

    return {
        **job,
        "match_score": score,
        "match_reasons": reasons
    }


def rank_jobs(jobs):

    scored_jobs = [
        calculate_score(job)
        for job in jobs
    ]

    return sorted(
        scored_jobs,
        key=lambda job: job["match_score"],
        reverse=True
    )


if __name__ == "__main__":

    input_file = ROOT / "data_jobs_raw.json"
    output_file = ROOT / "data_jobs_scored.json"

    if not input_file.exists():

        print(
            "No scraped job file found."
        )

        raise SystemExit(1)

    with open(
        input_file,
        "r",
        encoding="utf-8"
    ) as file:

        jobs = json.load(file)

    ranked_jobs = rank_jobs(jobs)

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            ranked_jobs,
            file,
            indent=2,
            ensure_ascii=False
        )

    print(
        f"Scored {len(ranked_jobs)} jobs."
    )

    print("\nTop matches:")

    for job in ranked_jobs[:10]:

        print(
            f"{job['match_score']:>3}% | "
            f"{job['title']} | "
            f"{job['source']}"
        )
