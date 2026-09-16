"""
Rebuild the ULB TimeEdit feed into per-course, per-activity .ics files.

Each output file is meant to be subscribed to separately (one colour per file
in Google / Apple Calendar). A merged file with everything is also written.

Configuration lives at the top of this file:
- SOURCE_ICS_URL: the public TimeEdit feed (no login needed).
- COURSES: allowlist of course codes -> short display name.
- GROUP_FILTERS: keep only the student's group when a course splits sessions.
"""

import os
import re
from typing import Dict, Iterable, Optional, Tuple

import requests
from icalendar import Calendar, Event

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

# Public "Horaire par cours" view (sid=10). Object ids are the 2026-27 course
# objects found via objects.html search. Date range covers the whole academic
# year so the second semester appears automatically once TimeEdit publishes it.
TIMEEDIT_BASE = "https://cloud.timeedit.net/be_ulb/web/public/ri.ics"
TIMEEDIT_SID = 10
TIMEEDIT_PERIOD = "20260801.x,20270930.x"
TIMEEDIT_OBJECT_IDS = {
    "PROJH402": 182287,
    "INFOH512": 179321,
    "INFOF409": 179275,
    "INFOH417": 179310,
    "ELECH417": 177920,
    "INFOF403": 179271,
    "STAGH501": 183410,
    "MEMOH504": 180375,
}

# Course code -> short label used in event titles and calendar names.
COURSES: Dict[str, str] = {
    "PROJH402": "Computing Project",
    "INFOH512": "AI Trends",
    "INFOF409": "Multi-Agent Learning",
    "INFOH417": "Database Systems",
    "ELECH417": "Comm Networks",
    "INFOF403": "Compilers",
    "STAGH501": "Internship",
    "MEMOH504": "Master Thesis",
}

# (course code, activity type) -> tokens; keep an event only if its summary
# contains at least one token. Used when a course has several parallel groups.
# ELECH417 labs run three groups (B-INFO:3, M-IRELE:1, M-IRIFS:1 + electives);
# the M-IRIFS group is the informatics master one.
GROUP_FILTERS: Dict[Tuple[str, str], Tuple[str, ...]] = {
    ("ELECH417", "Lab"): ("M-IRIFS",),
}

OUTPUT_DIR = "calendars"
FILE_PREFIX = "custom_calendar"
MERGED_NAME = "all"
REFRESH_TTL = "PT6H"


def build_source_url() -> str:
    objects = ",".join(f"{oid}.5" for oid in TIMEEDIT_OBJECT_IDS.values())
    return (
        f"{TIMEEDIT_BASE}?sid={TIMEEDIT_SID}"
        f"&p={TIMEEDIT_PERIOD.replace(',', '%2C')}"
        f"&objects={objects.replace(',', '%2C')}"
    )


SOURCE_ICS_URL = build_source_url()

# --------------------------------------------------------------------------- #
# Parsing helpers
# --------------------------------------------------------------------------- #


def unescape_ics(text) -> str:
    """Un-escape ICS text: backslash-comma, backslash-semicolon, backslash-n."""
    if not text:
        return ""
    text = str(text)
    placeholder = chr(0xE000)
    text = text.replace("\\\\", placeholder)
    text = text.replace("\\,", ",")
    text = text.replace("\\;", ";")
    text = text.replace("\\n", "\n")
    text = text.replace(placeholder, "\\")
    text = text.replace("\\", "")
    return text


def get_event_type(summary: str) -> str:
    """Return a normalized activity label, or '' when unrecognized."""
    s = summary.lower()
    if "théorie" in s or "theorie" in s or "theory" in s:
        return "Theory"
    if "travaux pratiques" in s or "labo" in s or "lab" in s:
        return "Lab"
    if "exercices" in s or "exercise" in s:
        return "Exercises"
    if "projet" in s or "project" in s:
        return "Project"
    if "séminaire" in s or "seminar" in s:
        return "Seminar"
    if "examen" in s or "exam" in s:
        return "Exam"
    return ""


def clean_location(location) -> str:
    """Keep the first room only, without the 'Salle:' prefix."""
    if not location:
        return ""
    location = unescape_ics(str(location)).split(",")[0].strip()
    if location.startswith("Salle: "):
        location = location[7:]
    return location


def extract_course_code(summary: str) -> Optional[str]:
    match = re.search(r"\b([A-Z]{4}[A-Z]?\d{3}[A-Z0-9]*)\b", summary)
    return match.group(1) if match else None


def extract_course_name(description) -> str:
    """First line of DESCRIPTION holds the full course title in TimeEdit feeds."""
    if not description:
        return ""
    desc = unescape_ics(str(description)).strip()
    lines = [ln.strip() for ln in desc.splitlines() if ln.strip()]
    if not lines:
        return ""
    first = re.sub(r"\s+", " ", lines[0])
    # Skip TimeEdit's date-range line on untitled events.
    if re.match(r"^\d{2}/\d{2}/\d{4}", first):
        return ""
    return first


def extract_teacher(summary: str) -> str:
    match = re.search(r"Enseignant:\s*([^,]+)", summary)
    return match.group(1).strip() if match else ""


def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", value.lower().strip())
    return re.sub(r"_+", "_", value).strip("_")


def get_display_name(course_code: str, fallback_name: str) -> str:
    if course_code in COURSES:
        return COURSES[course_code]
    return fallback_name.strip() if fallback_name else course_code


def should_keep_event(course_code: str, event_type: str, summary: str) -> bool:
    tokens = GROUP_FILTERS.get((course_code, event_type))
    if not tokens:
        return True
    upper = summary.upper()
    return any(tok.upper() in upper for tok in tokens)


# --------------------------------------------------------------------------- #
# Core
# --------------------------------------------------------------------------- #


def new_calendar(name: str, ident: str) -> Calendar:
    cal = Calendar()
    cal["PRODID"] = f"-//Custom Calendar//{ident}//"
    cal["VERSION"] = "2.0"
    cal["CALSCALE"] = "GREGORIAN"
    cal["METHOD"] = "PUBLISH"
    cal["X-WR-CALNAME"] = name
    cal["X-WR-TIMEZONE"] = "Europe/Brussels"
    cal["X-PUBLISHED-TTL"] = REFRESH_TTL
    cal["REFRESH-INTERVAL;VALUE=DURATION"] = REFRESH_TTL
    return cal


def fetch_source(ics_url: str) -> str:
    if ics_url.startswith("file://"):
        with open(ics_url[7:], "r", encoding="utf-8") as f:
            return f.read()
    if ics_url.startswith("webcal://"):
        ics_url = "https://" + ics_url[len("webcal://"):]
    headers = {"User-Agent": "Mozilla/5.0 (custom-calendar; +https://github.com/nbirchde/custom-calendar)"}
    response = requests.get(ics_url, headers=headers, timeout=60)
    response.raise_for_status()
    return response.text


def update_calendar(ics_url: str, output_dir: str, prefix: str = FILE_PREFIX,
                    courses: Optional[Iterable[str]] = None) -> Dict[str, int]:
    os.makedirs(output_dir, exist_ok=True)
    allowed = set(courses) if courses is not None else set(COURSES)

    print(f"Processing calendar from {ics_url}")
    source = Calendar.from_ical(fetch_source(ics_url))

    calendars: Dict[Tuple[str, str], Calendar] = {}
    merged = new_calendar("ULB 2026-27 (all courses)", MERGED_NAME)
    stats = {"processed": 0, "skipped": 0, "unknown_course": 0}

    for component in source.walk("VEVENT"):
        summary = unescape_ics(component.get("summary", "")).strip()

        if not summary or summary.startswith("Info:"):
            stats["skipped"] += 1
            continue

        course_code = extract_course_code(summary)
        if not course_code:
            print(f"Skipping event without course code: {summary}")
            stats["skipped"] += 1
            continue
        if course_code not in allowed:
            print(f"Skipping course not in allowlist: {course_code} ({summary})")
            stats["unknown_course"] += 1
            stats["skipped"] += 1
            continue

        event_type = get_event_type(summary)
        if not event_type:
            print(f"Skipping event without recognized type: {summary}")
            stats["skipped"] += 1
            continue

        if not should_keep_event(course_code, event_type, summary):
            stats["skipped"] += 1
            continue

        full_name = extract_course_name(component.get("description", "")) or course_code
        display_name = get_display_name(course_code, full_name)
        title = f"{display_name} ({event_type})"

        key = (course_code, event_type)
        if key not in calendars:
            calendars[key] = new_calendar(title, f"{course_code} {event_type}")

        new_event = Event()
        new_event.add("summary", title)
        for date_prop in ("dtstart", "dtend"):
            if date_prop in component:
                new_event.add(date_prop, component[date_prop].dt)

        location = clean_location(component.get("location", ""))
        if location:
            new_event.add("location", location)

        for prop in ("UID", "DTSTAMP", "LAST-MODIFIED"):
            if prop in component:
                new_event.add(prop, component[prop])

        desc_lines = [f"{course_code} - {full_name}"]
        teacher = extract_teacher(summary)
        if teacher:
            desc_lines.append(f"Teacher: {teacher}")
        desc_lines.append(f"TimeEdit: {summary}")
        new_event.add("description", "\n".join(desc_lines))

        calendars[key].add_component(new_event)
        merged.add_component(new_event)
        stats["processed"] += 1

    written = []
    for (course_code, event_type), cal in sorted(calendars.items()):
        filename = f"{prefix}_{course_code}_{slugify(event_type)}.ics"
        with open(os.path.join(output_dir, filename), "wb") as f:
            f.write(cal.to_ical())
        written.append(filename)
        print(f"Created {filename} ({len(cal.subcomponents)} events)")

    merged_file = f"{prefix}_{MERGED_NAME}.ics"
    with open(os.path.join(output_dir, merged_file), "wb") as f:
        f.write(merged.to_ical())
    print(f"Created {merged_file} ({stats['processed']} events)")

    missing = sorted(allowed - {code for code, _ in calendars})
    print("\nSummary:")
    print(f"- Processed events: {stats['processed']}")
    print(f"- Skipped events: {stats['skipped']}")
    print(f"- Created calendars: {len(calendars)} (+ merged)")
    if missing:
        print(f"- Courses with no scheduled events yet: {', '.join(missing)}")
    return stats


def process_all_calendars() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for name in os.listdir(OUTPUT_DIR):
        path = os.path.join(OUTPUT_DIR, name)
        if os.path.isfile(path) and name.endswith(".ics"):
            os.remove(path)
    update_calendar(SOURCE_ICS_URL, OUTPUT_DIR, FILE_PREFIX)


if __name__ == "__main__":
    process_all_calendars()
