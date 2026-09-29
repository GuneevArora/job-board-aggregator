from pathlib import Path
import json
import re
from collections import Counter

INPUT_FILE = Path("scripts/output/all_jobs.json")
OUTPUT_FILE = Path("scripts/output/all_jobs_filtered.json")
REPORT_FILE = Path("scripts/output/filter_report.json")
REJECTED_FILE = Path("scripts/output/rejected_titles.json")

ALLOWED_LEVELS = {"entry", "new_grad"}

# ============================================================
# Canada location classification
# ============================================================

CANADA_PROVINCES = {
    "alberta": "AB",
    "british columbia": "BC",
    "manitoba": "MB",
    "new brunswick": "NB",
    "newfoundland and labrador": "NL",
    "newfoundland": "NL",
    "nova scotia": "NS",
    "ontario": "ON",
    "prince edward island": "PE",
    "quebec": "QC",
    "saskatchewan": "SK",
    "northwest territories": "NT",
    "nunavut": "NU",
    "yukon": "YT",
}

CANADA_ABBREVIATIONS = set(CANADA_PROVINCES.values())

CANADIAN_CITIES = {
    "toronto", "ottawa", "mississauga", "brampton", "hamilton", "waterloo",
    "kitchener", "cambridge", "london", "windsor", "kingston", "burlington",
    "markham", "richmond hill", "vaughan", "oshawa", "guelph", "barrie",
    "st. catharines", "st catharines", "montreal", "montréal", "québec",
    "quebec city", "laval", "longueuil", "gatineau", "sherbrooke",
    "trois-rivieres", "vancouver", "burnaby", "richmond", "surrey",
    "victoria", "kelowna", "abbotsford", "coquitlam", "langley",
    "calgary", "edmonton", "red deer", "lethbridge", "winnipeg",
    "halifax", "dartmouth", "moncton", "fredericton", "saint john",
    "st. john's", "st john's", "saskatoon", "regina", "yellowknife",
    "whitehorse", "iqaluit",
}


def classify_location(location):
    text = str(location or "").strip()
    low = text.lower()

    if not text:
        return "non_canada", None

    # Explicit U.S. location wins.
    if re.search(
        r"\b(usa|u\.s\.a|u\.s\.|united states|united states of america)\b",
        low,
    ):
        return "non_canada", None

    # Explicit Canada.
    if re.search(r"\bcanada\b", low):
        return "canada", None

    # Province names.
    for province, abbreviation in CANADA_PROVINCES.items():
        if re.search(rf"\b{re.escape(province)}\b", low):
            return "canada", abbreviation

    # Province abbreviations, using original capitalization to reduce
    # accidental matches.
    for token in re.findall(r"(?<![A-Za-z])([A-Z]{2})(?![A-Za-z])", text):
        if token in CANADA_ABBREVIATIONS:
            return "canada", token

    # Known Canadian cities.
    for city in CANADIAN_CITIES:
        if re.search(rf"\b{re.escape(city)}\b", low):
            return "canada", None

    # Bare "Remote" is not assumed to be Canadian.
    return "non_canada", None


# ============================================================
# Experience classification
# ============================================================

INTERN_PATTERNS = [
    r"\bintern(ship)?\b",
    r"\bco[- ]?op\b",
    r"\bcooperative education\b",
]

NEW_GRAD_PATTERNS = [
    r"\bnew grad(uate)?\b",
    r"\brecent grad(uate)?\b",
    r"\bgraduate program(me)?\b",
    r"\bgraduate engineer\b",
    r"\bearly career\b",
    r"\bentry[- ]level\b",
    r"\bentry level\b",
]

SENIOR_PATTERNS = [
    r"\bsenior\b",
    r"\bsr\.?\b",
    r"\blead\b",
    r"\bstaff\b",
    r"\bprincipal\b",
    r"\bdirector\b",
    r"\bmanager\b",
    r"\bvice president\b",
    r"\bvp\b",
]

MID_PATTERNS = [
    r"\bmid[- ]level\b",
    r"\bmid level\b",
    r"\bintermediate\b",
    r"\bengineer\s*(ii|2|iii|3|iv|4)\b",
    r"\bdeveloper\s*(ii|2|iii|3|iv|4)\b",
    r"\blevel\s*[234]\b",
    r"\bl[234]\b",
]

ENTRY_PATTERNS = [
    r"\bjunior\b",
    r"\bjr\.?\b",
    r"\bassociate\b",
    r"\bapprentice\b",
    r"\btrainee\b",
    r"\bgraduate\b",
    r"\bengineer\s*i\b",
    r"\bdeveloper\s*i\b",
    r"\bscientist\s*i\b",
    r"\banalyst\s*i\b",
    r"\blevel\s*1\b",
    r"\bl1\b",
]


def matches_any(text, patterns):
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def classify_experience(title, job=None):
    low = str(title or "").strip().lower()

    if matches_any(low, INTERN_PATTERNS):
        return "intern"

    if matches_any(low, NEW_GRAD_PATTERNS):
        return "new_grad"

    # Senior indicators take precedence over junior/associate.
    if matches_any(low, SENIOR_PATTERNS):
        return "senior"

    if matches_any(low, MID_PATTERNS):
        return "mid"

    if matches_any(low, ENTRY_PATTERNS):
        return "entry"

    # Unknown title level is treated as mid rather than entry.
    return "mid"


# ============================================================
# Target technical roles
# ============================================================

TARGET_PATTERNS = {
    "Software/Engineering": [
        r"\bsoftware engineer\b",
        r"\bsoftware developer\b",
        r"\bsoftware development engineer\b",
        r"\bapplication developer\b",
        r"\bapplication engineer\b",
        r"\bbackend engineer\b",
        r"\bbackend developer\b",
        r"\bback[- ]end engineer\b",
        r"\bback[- ]end developer\b",
        r"\bfrontend engineer\b",
        r"\bfrontend developer\b",
        r"\bfront[- ]end engineer\b",
        r"\bfront[- ]end developer\b",
        r"\bfull[- ]stack engineer\b",
        r"\bfull[- ]stack developer\b",
        r"\bweb developer\b",
        r"\bweb engineer\b",
        r"\bmobile developer\b",
        r"\bmobile engineer\b",
        r"\bios developer\b",
        r"\bandroid developer\b",
        r"\bdeveloper\b",
    ],

    "AI/ML": [
        r"\bmachine learning\b",
        r"\bmachine learning engineer\b",
        r"\bmachine learning developer\b",
        r"\bml engineer\b",
        r"\bmlops\b",
        r"\bai engineer\b",
        r"\bartificial intelligence\b",
        r"\bai/ml\b",
        r"\bcomputer vision\b",
        r"\bnlp engineer\b",
        r"\bnatural language processing\b",
    ],

    "Data": [
        r"\bdata engineer\b",
        r"\bdata scientist\b",
        r"\bdata analyst\b",
        r"\bbi analyst\b",
        r"\bbusiness intelligence analyst\b",
        r"\banalytics analyst\b",
        r"\banalytics engineer\b",
        r"\bdatabase analyst\b",
        r"\bdatabase developer\b",
        r"\bdata platform\b",
        r"\bbig data\b",
    ],

    "Cloud/DevOps/Platform": [
        r"\bcloud engineer\b",
        r"\bcloud developer\b",
        r"\bcloud support\b",
        r"\bcloud operations\b",
        r"\bcloud administrator\b",
        r"\bcloud infrastructure\b",
        r"\bdevops\b",
        r"\bdevsecops\b",
        r"\bsite reliability\b",
        r"\bsre\b",
        r"\bplatform engineer\b",
        r"\bplatform developer\b",
        r"\binfrastructure engineer\b",
        r"\binfrastructure analyst\b",
        r"\binfrastructure support\b",
        r"\bsystems engineer\b",
        r"\bsystems administrator\b",
        r"\bsystems analyst\b",
        r"\bbuild engineer\b",
        r"\brelease engineer\b",
        r"\bdeployment engineer\b",
    ],

    "Solutions Architecture": [
        r"\bjunior solutions architect\b",
        r"\bjunior solution architect\b",
        r"\bassociate solutions architect\b",
        r"\bassociate solution architect\b",
        r"\bsolutions architect\s*i\b",
        r"\bsolution architect\s*i\b",
        r"\bassociate cloud architect\b",
        r"\bjunior cloud architect\b",
        r"\bcloud architect\s*i\b",
        r"\bassociate technical architect\b",
        r"\bjunior technical architect\b",
        r"\btechnical architect\s*i\b",

        # Architecture titles that explicitly identify a technical domain.
        r"\bsolutions architect\b(?=.*\b(software|cloud|technical|platform|technology|solutions)\b)",
        r"\bsolution architect\b(?=.*\b(software|cloud|technical|platform|technology|solutions)\b)",
        r"\btechnical architect\b",
        r"\bcloud architect\b",
    ],

    "IT/Technical": [
        r"\bit support\b",
        r"\bit analyst\b",
        r"\bit technician\b",
        r"\bit administrator\b",
        r"\btechnical analyst\b",
        r"\btechnology analyst\b",
        r"\btechnical support\b",
        r"\btechnical support engineer\b",
        r"\btechnical support specialist\b",
        r"\btechnical support technician\b",
        r"\btechnical support representative\b",
        r"\bl1 support\b",
        r"\blevel 1 support\b",
        r"\blevel 1 technical support\b",
        r"\bapplication support\b",
        r"\bapplication support analyst\b",
        r"\bproduction support\b",
        r"\bsystems support\b",
        r"\bsystems support analyst\b",
        r"\bservice desk\b",
        r"\bhelp desk\b",
        r"\btechnical operations analyst\b",
        r"\btechnology operations\b",
        r"\bnetwork administrator\b",
        r"\bnetwork support\b",
    ],

    "Security": [
        r"\bsecurity engineer\b",
        r"\bsecurity analyst\b",
        r"\bcybersecurity\b",
        r"\bcyber security\b",
        r"\binformation security\b",
        r"\bsecurity operations\b",
        r"\bsoc analyst\b",
        r"\bsecurity operations center\b",
        r"\bapplication security\b",
        r"\bcloud security\b",
        r"\bsecurity support\b",
    ],

    "QA/Test": [
        r"\bqa engineer\b",
        r"\bqa analyst\b",
        r"\bquality assurance\b",
        r"\btest engineer\b",
        r"\btest analyst\b",
        r"\bsoftware tester\b",
        r"\bautomation engineer\b",
        r"\btest automation\b",
        r"\bsdet\b",
        r"\bquality engineer\b",
        r"\bsoftware test developer\b",
    ],

    "Embedded/Hardware": [
        r"\bembedded software\b",
        r"\bembedded engineer\b",
        r"\bembedded developer\b",
        r"\bfirmware engineer\b",
        r"\bfirmware developer\b",
        r"\bembedded systems\b",
        r"\bcomputer engineering\b",
    ],
}

# These exclusions apply to the title before target matching.
# This prevents generic "associate", "analyst", "engineer", etc.
# from admitting unrelated jobs.
EXCLUSION_PATTERNS = [
    r"\bproduct manager\b",
    r"\bproduct management\b",
    r"\bproject manager\b",
    r"\bproject management\b",
    r"\bprogram manager\b",
    r"\bprogram management\b",
    r"\bbusiness development\b",
    r"\bbusiness analyst\b",
    r"\bcustomer success\b",
    r"\bcustomer service\b",
    r"\bcustomer experience\b",
    r"\bsales\b",
    r"\brecruit(er|ing)?\b",
    r"\bmarketing\b",
    r"\bcommunications\b",
    r"\bfinance\b",
    r"\baccounting\b",
    r"\baccountant\b",
    r"\bhuman resources\b",
    r"\badministrative\b",
    r"\badministration\b",
    r"\boperations\b",
    r"\blogistics\b",
    r"\bprocurement\b",
    r"\bwarehouse\b",
    r"\bretail\b",
    r"\bstore associate\b",
    r"\bfront desk\b",
    r"\bpharmacy\b",
    r"\bclinical\b",
    r"\bmedical\b",
    r"\bhealthcare\b",
    r"\bchemist\b",
    r"\bchemistry\b",
    r"\bbiologist\b",
    r"\bbiology\b",
    r"\bmechanical engineer\b",
    r"\bcivil engineer\b",
    r"\belectrical engineer\b",
    r"\bindustrial engineer\b",
    r"\bmanufacturing engineer\b",
    r"\bprocess engineer\b",
    r"\brefrigeration engineer\b",
    r"\bglazier\b",
    r"\bautomotive\b",
    r"\bcreative\b",
    r"\bdesigner\b",
    r"\bproducer\b",
    r"\bcontent\b",
    r"\bwealth\b",
    r"\binvestment\b",
    r"\btrading\b",
]


def classify_target_role(title, job=None):
    low = str(title or "").strip().lower()

    if matches_any(low, EXCLUSION_PATTERNS):
        return []

    matches = []

    for domain, patterns in TARGET_PATTERNS.items():
        if matches_any(low, patterns):
            matches.append(domain)

    # "Associate Architect - Software Developer" is both an architecture
    # and software role because the title explicitly names software.
    if re.search(r"\bassociate architect\b", low) and re.search(
        r"\b(software|developer|cloud|technical|platform|technology)\b", low
    ):
        if "Solutions Architecture" not in matches:
            matches.append("Solutions Architecture")

    return matches


# ============================================================
# Deduplication
# ============================================================

def dedup_key(job):
    """
    Prefer stable job identifiers when present, then URL.

    This removes repeated copies of the same posting from the
    filtered output without changing the scraper's existing
    merge_data.py behavior.
    """
    ats = str(job.get("ats") or "").lower()
    company = str(job.get("company") or "").strip().lower()

    job_id = job.get("id")
    if job_id not in (None, ""):
        return f"id:{ats}:{company}:{job_id}"

    url = str(job.get("url") or "").strip().lower()
    if url:
        return f"url:{url}"

    title = str(job.get("title") or "").strip().lower()
    location = str(job.get("location") or "").strip().lower()

    return f"fallback:{company}:{title}:{location}"


def deduplicate_jobs(jobs):
    """
    Keep the first occurrence of each job.

    If the same job appears multiple times but one copy has more
    complete metadata, prefer that copy.
    """
    unique = {}

    for job in jobs:
        key = dedup_key(job)

        if key not in unique:
            unique[key] = job
            continue

        existing = unique[key]

        existing_score = sum(
            value not in (None, "", [], {})
            for value in existing.values()
        )
        new_score = sum(
            value not in (None, "", [], {})
            for value in job.values()
        )

        if new_score > existing_score:
            unique[key] = job

    return list(unique.values())


# ============================================================
# Main
# ============================================================

def main():
    with INPUT_FILE.open("r", encoding="utf-8") as f:
        jobs = json.load(f)

    filtered_before_dedup = []
    rejected = []

    reason_counts = Counter()
    rejected_titles = Counter()
    input_levels = Counter()
    kept_levels = Counter()
    domain_counts = Counter()

    for job in jobs:
        title = str(job.get("title") or "").strip()
        location = str(job.get("location") or "").strip()

        location_status, province = classify_location(location)
        experience_level = classify_experience(title, job)
        target_domains = classify_target_role(title, job)

        job["is_canada"] = location_status == "canada"
        job["canada_province"] = province
        job["experience_level"] = experience_level
        job["target_domains"] = target_domains
        job["target_role"] = bool(target_domains)

        input_levels[experience_level] += 1

        reasons = []

        if location_status != "canada":
            reasons.append("not_canada")

        if experience_level not in ALLOWED_LEVELS:
            reasons.append(f"level:{experience_level}")

        if not target_domains:
            reasons.append("non_target_role")

        if reasons:
            rejected.append(job)
            rejected_titles[title] += 1

            for reason in reasons:
                reason_counts[reason] += 1
        else:
            filtered_before_dedup.append(job)
            kept_levels[experience_level] += 1

            for domain in target_domains:
                domain_counts[domain] += 1

    filtered_jobs = deduplicate_jobs(filtered_before_dedup)
    duplicates_removed = len(filtered_before_dedup) - len(filtered_jobs)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    OUTPUT_FILE.write_text(
        json.dumps(filtered_jobs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report = {
        "input_jobs": len(jobs),
        "kept_before_dedup": len(filtered_before_dedup),
        "duplicates_removed": duplicates_removed,
        "kept_jobs": len(filtered_jobs),
        "removed_jobs": len(jobs) - len(filtered_jobs),
        "removal_reasons": dict(reason_counts),
        "experience_levels_in_input": dict(input_levels),
        "experience_levels_kept": dict(kept_levels),
        "target_domains_before_dedup": dict(domain_counts),
        "configuration": {
            "allowed_levels": sorted(ALLOWED_LEVELS),
            "canada_only": True,
            "technical_roles_only": True,
            "solutions_architecture_included": True,
            "deduplication_enabled": True,
        },
    }

    REPORT_FILE.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    REJECTED_FILE.write_text(
        json.dumps(
            [
                {"title": title, "count": count}
                for title, count in rejected_titles.most_common()
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=" * 60)
    print("JOB FILTER REPORT")
    print("=" * 60)
    print(f"Input jobs:          {len(jobs):,}")
    print(f"Kept before dedup:   {len(filtered_before_dedup):,}")
    print(f"Duplicates removed:  {duplicates_removed:,}")
    print(f"Final kept jobs:     {len(filtered_jobs):,}")
    print(f"Removed jobs:        {len(jobs) - len(filtered_jobs):,}")

    print("\nRemoval reasons:")
    for reason, count in reason_counts.most_common():
        print(f"  {reason}: {count:,}")

    print("\nExperience levels in input:")
    for level, count in input_levels.most_common():
        print(f"  {level}: {count:,}")

    print("\nKept experience levels:")
    for level, count in kept_levels.most_common():
        print(f"  {level}: {count:,}")

    print("\nTarget domains:")
    for domain, count in domain_counts.most_common():
        print(f"  {domain}: {count:,}")

    print("\nFinal kept jobs:")
    print("-" * 60)

    for job in filtered_jobs[:100]:
        print(
            f"{job.get('title', '')} | "
            f"{job.get('company', '')} | "
            f"{job.get('location', '')} | "
            f"{job.get('experience_level', '')} | "
            f"{', '.join(job.get('target_domains', []))}"
        )

    print("\nTop rejected titles:")
    print("-" * 60)

    for title, count in rejected_titles.most_common(50):
        print(f"{count:4}x  {title}")

    print()
    print(f"Filtered jobs saved to: {OUTPUT_FILE}")
    print(f"Report saved to:        {REPORT_FILE}")
    print(f"Rejected titles saved:  {REJECTED_FILE}")


if __name__ == "__main__":
    main()
