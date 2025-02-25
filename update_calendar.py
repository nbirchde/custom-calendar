import requests
from icalendar import Calendar, Event
import re
import os
import shutil

# Mapping complet des cours
course_mapping = {
    "INFOH3000": "RO",         # Recherche Opérationnelle
    "INFOH303": "BD",          # Base de données
    "INFOF307": "GL",          # Génie Logiciel
    "ELECH310": "DE",          # Digital Electronics
    "TRANH3001": "Éthique"     # Éthique
}

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
    text = re.sub(r'Electromécanique [0-9]+', '', text)
    text = re.sub(r'B-IRCI:?\d*\s*-?\s*[^,]*', '', text)
    text = re.sub(r'B-[A-Z]+:[0-9]+', '', text)
    text = re.sub(r'\s*,\s*,\s*', ', ', text)
    text = re.sub(r'\s*-?\s*$', '', text)
    text = re.sub(r',\s*$', '', text)  # Supprime la virgule finale
    return text.strip()

def update_calendar(ics_url, output_dir):
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
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
    calendars = {}
    processed_events = 0
    skipped_events = 0

    for component in old_cal.walk():
        if component.name == "VEVENT":
            summary_raw = str(component.get("summary", ""))
            summary_unescaped = unescape_ics(summary_raw)
            
            if summary_unescaped.startswith("Info:"):
                skipped_events += 1
                continue
            
            # Trouver le code du cours dans le résumé
            course_code = None
            course_name = None
            
            # Chercher une correspondance exacte dans le mapping
            for code, name in course_mapping.items():
                if code in summary_unescaped:
                    course_code = code
                    course_name = name
                    break
            
            if not course_name:
                print(f"Skipping unknown course: {summary_unescaped}")
                skipped_events += 1
                continue
            
            event_type = get_event_type(summary_unescaped)
            if not event_type:
                print(f"Skipping event without recognized type: {summary_unescaped}")
                skipped_events += 1
                continue
            
            # Créer une clé unique pour ce cours et ce type d'événement
            cal_key = (course_name, event_type)
            if cal_key not in calendars:
                new_cal = Calendar()
                new_cal.add('prodid', f'-//Custom Calendar//{course_name} {event_type}//')
                new_cal.add('version', '2.0')
                calendars[cal_key] = new_cal
            
            # Créer le nouvel événement
            new_event = Event()
            new_event.add("summary", f"{course_name} {event_type}")
            
            # Copier les dates
            for date_prop in ["dtstart", "dtend"]:
                if date_prop in component:
                    new_event.add(date_prop, component[date_prop].dt)
            
            # Nettoyer et ajouter l'emplacement
            location = clean_location(component.get("location", ""))
            if location:
                new_event.add("location", location)
            
            # Copier les propriétés essentielles
            for prop in ["UID", "DTSTAMP", "LAST-MODIFIED"]:
                if prop in component:
                    new_event.add(prop, component[prop])
            
            calendars[cal_key].add_component(new_event)
            processed_events += 1
    
    # Écrire chaque calendrier dans un fichier séparé
    for (course_name, event_type), cal in calendars.items():
        filename = f"custom_calendar_{course_name}_{event_type}.ics"
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "wb") as f:
            f.write(cal.to_ical())
        print(f"Created {filename}")
    
    print(f"\nSummary:")
    print(f"- Processed events: {processed_events}")
    print(f"- Skipped events: {skipped_events}")
    print(f"- Created calendars: {len(calendars)}")

if __name__ == "__main__":
    ics_url = "webcal://cloud.timeedit.net/be_ulb/web/etudiant/ri69j598Y63161QZd6Qtjk5QZ58l18oo6Z971ZnyQ751k07Q247k398F70650Z3E55028C01F2t5B75EDCC98B771Q.ics"
    output_dir = "calendars"
    update_calendar(ics_url, output_dir)