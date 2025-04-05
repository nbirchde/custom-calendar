import requests
from icalendar import Calendar, Event
import re
import os
import shutil
import datetime  # Adding datetime import for timestamp
import random    # For random value to ensure uniqueness
import string    # For generating random strings
import subprocess

# Mapping complet des cours - original calendar
original_course_mapping = {
    "INFOH3000": "RO",         # Recherche Opérationnelle
    "INFOH303": "BD",          # Base de données
    "INFOF307": "GL",          # Génie Logiciel
    "ELECH310": "DE",          # Digital Electronics
    "TRANH3001": "Éthique"     # Éthique
}

# Mapping complet des cours - friend's calendar
friend_course_mapping = {
    "ELECH310": "ELECH310",    # Digital Electronics
    "ELECH312": "ELECH312",    # Power Electronics
    "ELECH313": "ELECH313",    # Instrumentation
    "ELECH3002": "ELECH3002",  # Instrumentation et Automatique
    "ELECH314": "ELECH314",    # Advanced Instrumentation
    "MATHH304": "MATHH304",    # Automatique (Control Systems)
    "MECAH305": "MECAH305",    # Fluid mechanics II
    "TRANH3001": "TRANH3001",  # Ethics
    "BINGF3004": "BINGF3004"   # Scientific English
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

def get_git_revision():
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('ascii').strip()[:8]
    except:
        return 'nogit'

def update_calendar(ics_url, output_dir, course_mapping, prefix="custom_calendar"):
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
        filename = f"{prefix}_{course_name}_{event_type}.ics"
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
    
    # Write debugging information to a file
    with open("debug_info.txt", "w") as debug_file:
        # Log the current Git commit
        try:
            git_commit = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
            debug_file.write(f"Current Git commit: {git_commit}\n")
        except Exception as e:
            debug_file.write(f"Error getting Git commit: {str(e)}\n")
        
        # Log environment information
        debug_file.write(f"Current directory: {os.getcwd()}\n")
        debug_file.write(f"Directory contents: {os.listdir()}\n")
        debug_file.write(f"Environment variables: {os.environ}\n")
        
        # Force unique output for each run
        debug_file.write(f"Run timestamp: {datetime.datetime.now().isoformat()}\n")
        debug_file.write(f"Random identifier: {''.join(random.choices(string.ascii_uppercase + string.digits, k=32))}\n")
    
    # Ensure the output directory exists and is empty
    if os.path.exists(output_dir):
        for file_name in os.listdir(output_dir):
            file_path = os.path.join(output_dir, file_name)
            if os.path.isfile(file_path):
                os.remove(file_path)
    else:
        os.makedirs(output_dir)

    # Process your calendar
    your_calendar_url = "webcal://cloud.timeedit.net/be_ulb/web/etudiant/ri69j598Y63161QZd6Qtjk5QZ58l18oo6Z971ZnyQ751k07Q247k398F70650Z3E55028C01F2t5B75EDCC98B771Q.ics"
    update_calendar(your_calendar_url, output_dir, original_course_mapping, "custom_calendar")
    
    # Process your friend's calendar
    friend_calendar_url = "webcal://cloud.timeedit.net/be_ulb/web/etudiant/ri666XQZ699Z5QQv2902X2t6y7Y790n39Y1963gQY074Z70ZQdj7150jZ3mQk9n0k1EA8C4966n0oAn54FC664B22jA777Ft04F245847BED5004.ics"
    update_calendar(friend_calendar_url, output_dir, friend_course_mapping, "friend_calendar")

if __name__ == "__main__":
    process_all_calendars()