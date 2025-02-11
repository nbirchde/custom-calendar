import requests
from icalendar import Calendar, Event
import re

# Mapping: course code -> (New Name, Color)
course_mapping = {
    "INFOH3000": ("Recherche opérationnelle", "#1E90FF"),
    "ELECH310": ("Digital electronics", "#FF4500"),
    "INFOH303": ("Bases de données", "#32CD32"),
    "TRANH3001": ("Epistémologie des sciences et éthique de l'ingénieur", "#8A2BE2"),
    "INFOF307": ("Génie logiciel et gestion de projets", "#FFA500")
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
        return "théorie"
    elif "travaux pratiques" in summary_lower:
        return "Labo"
    elif "exercices" in summary_lower:
        return "exercices"
    return ""

def clean_location(location):
    """Extract just the room number and name."""
    if not location:
        return ""
    location = location.split(",")[0].strip()
    if location.startswith("Salle: "):
        location = location[7:]
    return location

def update_calendar(ics_url, output_file):
    # Convert "webcal" to "https"
    if ics_url.startswith("webcal://"):
        ics_url = "https://" + ics_url[len("webcal://"):]
    
    response = requests.get(ics_url)
    response.raise_for_status()
    
    old_cal = Calendar.from_ical(response.text)
    new_cal = Calendar()
    
    # Copy over required properties
    for prop in ['VERSION', 'PRODID', 'CALSCALE', 'METHOD']:
        if prop in old_cal:
            new_cal.add(prop, old_cal[prop])
    
    # Debug counter
    processed = 0
    
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
                    processed += 1
                    break
            
            if course_code:
                new_event = Event()
                
                # Get the clean course name and color
                course_name, color = course_mapping[course_code]
                
                # Get event type (théorie, exercices, or Labo)
                event_type = get_event_type(summary_unescaped)
                
                # Find faculty token (B-IRCI)
                faculty_token = None
                for token in summary_unescaped.split(','):
                    token = token.strip()
                    if "B-IRCI:" in token:
                        faculty_token = token
                        break
                
                # Build new clean summary
                parts = [course_name]
                if event_type:
                    parts.append(event_type)
                if faculty_token:
                    parts.append(faculty_token)
                new_summary = ", ".join(parts)
                
                new_event.add("summary", new_summary)
                new_event.add("dtstart", component["dtstart"].dt)
                new_event.add("dtend", component["dtend"].dt)
                
                # Clean up location
                location = clean_location(component.get("location", ""))
                if location:
                    new_event.add("location", location)
                
                # Set color (lighter for exercises/labs)
                new_event.add("X-APPLE-CALENDAR-COLOR", color)
                
                # Copy other essential properties
                for prop in ["UID", "DTSTAMP", "LAST-MODIFIED"]:
                    if prop in component:
                        new_event.add(prop, component[prop])
                
                new_cal.add_component(new_event)
            else:
                # If no course code found, keep original event unchanged
                new_cal.add_component(component)
    
    print(f"Matched and processed {processed} events")
    
    with open(output_file, "wb") as f:
        f.write(new_cal.to_ical())

if __name__ == "__main__":
    ics_url = "webcal://cloud.timeedit.net/be_ulb/web/etudiant/ri69j598Y63161QZd6Qtjk5QZ58l18oo6Z971ZnyQ751k07Q247k398F70650Z3E55028C01F2t5B75EDCC98B771Q.ics"
    output_file = "custom_calendar.ics"
    update_calendar(ics_url, output_file)