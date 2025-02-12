import requests
from icalendar import Calendar, Event
import re
import os
import shutil

# Mapping: course code -> Name
course_mapping = {
    "INFOH3000": "RO",
    "ELECH310": "DE",
    "INFOH303": "BD",
    "TRANH3001": "Éthique",
    "INFOF307": "GL"
}

def unescape_ics(text):
    """Un-escape ICS text properly handling backslash escapes."""
    if not text:
        return ""
    # First replace \\ with temporary marker
    text = text.replace("\\\\", "\uE000")
    # Then handle other escapes
    text = text.replace("\\,", ",")
    text = text.replace("\\;", ";")
    text = text.replace("\\n", "\n")
    # Finally restore \\ and remove any remaining single \
    text = text.replace("\uE000", "\\")
    text = text.replace("\\", "")
    return text

def get_event_type(summary):
    """Return appropriate event type label."""
    summary_lower = summary.lower()
    if "théorie" in summary_lower:
        return "th"
    elif "travaux pratiques" in summary_lower:
        return "Labo"
    elif "exercices" in summary_lower:
        return "ex"
    return ""

def clean_location(location):
    """Extract just the room number and name."""
    if not location:
        return ""
    location = location.split(",")[0].strip()
    if location.startswith("Salle: "):
        location = location[7:]
    return location

def clean_faculty_info(text):
    """Remove faculty-related text."""
    if not text:
        return text
    # Remove Electromécanique references
    text = re.sub(r'Electromécanique [0-9]+', '', text)
    # Remove all B-IRCI related text including Informatique suffix
    text = re.sub(r'B-IRCI:?\d*\s*-?\s*[^,]*', '', text)
    # Remove other faculty codes
    text = re.sub(r'B-[A-Z]+:[0-9]+', '', text)
    # Clean up any remaining artifacts
    text = re.sub(r'\s*,\s*,\s*', ', ', text)
    text = re.sub(r'\s*-?\s*$', '', text)
    return text.strip()

def update_calendar(ics_url, output_dir):
    # Clean output directory first
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)
    
    # Convert "webcal" to "https"
    if ics_url.startswith("webcal://"):
        ics_url = "https://" + ics_url[len("webcal://"):]
    
    response = requests.get(ics_url)
    response.raise_for_status()
    
    old_cal = Calendar.from_ical(response.text)
    calendars = {}

    # Create a new calendar for each (course, event type) combination
    for component in old_cal.walk():
        if component.name == "VEVENT":
            # Get raw summary and unescape it
            summary_raw = str(component.get("summary", ""))
            summary_unescaped = unescape_ics(summary_raw)
            
            # Skip info events
            if summary_unescaped.startswith("Info:"):
                continue
            
            # Look for course code in unescaped summary
            course_code = None
            for code in course_mapping:
                if code in summary_unescaped:
                    course_code = code
                    break
            
            if course_code:
                # Get the clean course name
                course_name = course_mapping[course_code]
                
                # Get event type (théorie, exercices, or Labo)
                event_type = get_event_type(summary_unescaped)
                
                # Build new clean summary (without faculty tokens)
                parts = [course_name]
                if event_type:
                    parts.append(event_type)
                new_summary = clean_faculty_info(", ".join(parts))
                
                # Create a new calendar if it doesn't exist
                # Use original name format for the key to maintain filename consistency
                original_name = summary_unescaped.split(',')[0].strip()
                cal_key = (original_name, event_type)
                if cal_key not in calendars:
                    new_cal = Calendar()
                    for prop in ['VERSION', 'PRODID', 'CALSCALE', 'METHOD']:
                        if prop in old_cal:
                            new_cal.add(prop, old_cal[prop])
                    calendars[cal_key] = new_cal
                
                new_event = Event()
                new_event.add("summary", new_summary)
                new_event.add("dtstart", component["dtstart"].dt)
                new_event.add("dtend", component["dtend"].dt)
                
                # Clean up location
                location = clean_location(component.get("location", ""))
                if location:
                    new_event.add("location", location)
                
                # Copy other essential properties
                for prop in ["UID", "DTSTAMP", "LAST-MODIFIED"]:
                    if prop in component:
                        new_event.add(prop, component[prop])
                
                calendars[cal_key].add_component(new_event)
    
    # Write each calendar to a separate file using original naming scheme
    for (original_name, event_type), cal in calendars.items():
        filename = f"custom_calendar_{original_name}_{event_type}.ics"
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "wb") as f:
            f.write(cal.to_ical())
    
    print(f"Processed {len(calendars)} calendars")

if __name__ == "__main__":
    ics_url = "webcal://cloud.timeedit.net/be_ulb/web/etudiant/ri69j598Y63161QZd6Qtjk5QZ58l18oo6Z971ZnyQ751k07Q247k398F70650Z3E55028C01F2t5B75EDCC98B771Q.ics"
    output_dir = "calendars"
    update_calendar(ics_url, output_dir)