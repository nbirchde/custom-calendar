import os
import re
from typing import Optional, Tuple

import requests
from icalendar import Calendar, Event

SOURCE_ICS_URL = "webcal://cloud.timeedit.net/be_ulb/web/etudiant/ri66jQ18564Z61Q5d68tjk51y5Zl81oo6Z9Y1ZnQQ871k07Q247k358164F63Z6A5A2315FEF9t8A08F10E8B87BFQ6.ics"

def unescape_ics(text):
    """Un-escape ICS text properly handling backslash escapes."""
    if not text:
        return ""
    text = text.replace("\\\\", "\uE000")
    text = text.replace("\\,", ",")
    text = text.replace("\\;", ";")
    text = text.replace("\\n", "\n")
    text = text.replace("\uE000", "\\")
    text = text.replace("\\", "")
    return text

def get_event_type(summary):
    """Return normalized event type label."""
    summary_lower = summary.lower()
    if "théorie" in summary_lower or "theory" in summary_lower:
        return "Theory"
    if "travaux pratiques" in summary_lower or "labo" in summary_lower or "lab" in summary_lower:
        return "Lab"
    if "exercices" in summary_lower or "exercise" in summary_lower:
        return "Exercises"
    if "projet" in summary_lower or "project" in summary_lower:
        return "Project"
    if "séminaire" in summary_lower or "seminar" in summary_lower:
        return "Seminar"
    return ""

def clean_location(location):
    """Extract just the room number and name."""
    if not location:
        return ""
    location = location.split(",")[0].strip()
    if location.startswith("Salle: "):
        location = location[7:]
    return location

def extract_course_code(summary: str) -> Optional[str]:
    match = re.search(r"\b([A-Z]{4,}\d{2,}[A-Z0-9]*)\b", summary)
    if match:
        return match.group(1)
    return None


def extract_course_name(description: str) -> str:
    """
    Try to extract explicit course name from DESCRIPTION first line.
    Example: "Techniques of Artificial Intelligence \nEnseignant: ..."
    """
    if not description:
        return ""
    desc = unescape_ics(str(description)).strip()
    first_line = desc.splitlines()[0].strip() if desc.splitlines() else ""
    first_line = re.sub(r"\s+", " ", first_line)
    return first_line


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value

def update_calendar(ics_url, output_dir, prefix="custom_calendar"):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    print(f"Processing calendar from {ics_url}")
    
    # Handle local files for testing
    if ics_url.startswith('file://'):
        local_path = ics_url[7:]  # Remove file:// prefix
        with open(local_path, 'r') as f:
            calendar_data = f.read()
    else:
        if ics_url.startswith("webcal://"):
            ics_url = "https://" + ics_url[len("webcal://"):]
        response = requests.get(ics_url)
        response.raise_for_status()
        calendar_data = response.text
    
    old_cal = Calendar.from_ical(calendar_data)
    calendars: dict[Tuple[str, str], Calendar] = {}
    processed_events = 0
    skipped_events = 0

    for component in old_cal.walk():
        if component.name == "VEVENT":
            summary_raw = str(component.get("summary", "")).strip()
            summary_unescaped = unescape_ics(summary_raw)
            
            if summary_unescaped.startswith("Info:"):
                skipped_events += 1
                continue
            
            course_code = extract_course_code(summary_unescaped)
            if not course_code:
                print(f"Skipping unknown course: {summary_unescaped}")
                skipped_events += 1
                continue

            description = str(component.get("description", ""))
            course_name = extract_course_name(description) or course_code
            
            event_type = get_event_type(summary_unescaped)
            if not event_type:
                print(f"Skipping event without recognized type: {summary_unescaped}")
                skipped_events += 1
                continue
            
            # One subscription per course + activity type
            cal_key = (course_code, event_type)
            if cal_key not in calendars:
                new_cal = Calendar()
                new_cal.add('prodid', f'-//Custom Calendar//{course_code} {event_type}//')
                new_cal.add('version', '2.0')
                new_cal.add('calscale', 'GREGORIAN')
                new_cal.add('method', 'PUBLISH')
                new_cal.add('x-wr-calname', f'{course_code} - {event_type}')
                new_cal.add('x-wr-timezone', 'Europe/Brussels')
                calendars[cal_key] = new_cal
            
            new_event = Event()
            new_event.add("summary", f"{course_code} - {course_name} ({event_type})")
            
            for date_prop in ["dtstart", "dtend"]:
                if date_prop in component:
                    new_event.add(date_prop, component[date_prop].dt)
            
            location = clean_location(component.get("location", ""))
            if location:
                new_event.add("location", location)
            
            for prop in ["UID", "DTSTAMP", "LAST-MODIFIED"]:
                if prop in component:
                    new_event.add(prop, component[prop])

            if "description" in component:
                new_event.add("description", component["description"])
            
            calendars[cal_key].add_component(new_event)
            processed_events += 1
    
    for (course_code, event_type), cal in calendars.items():
        filename = f"{prefix}_{course_code}_{slugify(event_type)}.ics"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, "wb") as f:
            f.write(cal.to_ical())
        print(f"Created {filename}")
    
    print(f"\nSummary:")
    print(f"- Processed events: {processed_events}")
    print(f"- Skipped events: {skipped_events}")
    print(f"- Created calendars: {len(calendars)}")

def process_all_calendars():
    output_dir = "calendars"
    
    # Ensure the output directory exists and is empty
    if os.path.exists(output_dir):
        for file_name in os.listdir(output_dir):
            file_path = os.path.join(output_dir, file_name)
            if os.path.isfile(file_path):
                os.remove(file_path)
    else:
        os.makedirs(output_dir)

    update_calendar(SOURCE_ICS_URL, output_dir, "custom_calendar")

if __name__ == "__main__":
    process_all_calendars()