import requests
from icalendar import Calendar, Event
import re
import os
import shutil
import sys
import argparse
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('calendar_update.log')
    ]
)
logger = logging.getLogger(__name__)

# Mapping: course code -> Name
course_mapping = {
    "INFOH3000": "RO",
    "ELECH310": "DE",
    "INFOH303": "BD",
    "TRANH3001": "Éthique",
    "INFOF307": "GL",
    "BINGF3004": "BINGF3004"
}

def unescape_ics(text):
    """Un-escape ICS text properly handling backslash escapes."""
    if not text:
        return ""
    text = text.replace("\\\\", "\uE000")  # temporarily store real backslashes
    text = text.replace("\\,", ",")
    text = text.replace("\\;", ";")
    text = text.replace("\\n", "\n")
    text = text.replace("\uE000", "\\")  # restore real backslashes
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
    text = re.sub(r'\s*,?\s*-?\s*$', '', text)  # Added ? after comma to make it optional
    return text.strip()

def update_calendar(ics_url, output_dir):
    """
    Download and process calendar data from the given URL,
    splitting it into separate files by course and event type.
    
    Args:
        ics_url (str): URL of the .ics calendar file
        output_dir (str): Directory to output the processed calendar files
    
    Returns:
        int: Number of calendar files created
    """
    try:
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        os.makedirs(output_dir)
        
        if ics_url.startswith("webcal://"):
            ics_url = "https://" + ics_url[len("webcal://"):]
        
        logger.info(f"Downloading calendar from {ics_url}")
        try:
            response = requests.get(ics_url, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download calendar: {e}")
            return 0
        
        old_cal = Calendar.from_ical(response.text)
        calendars = {}
        events_processed = 0
        
        logger.info("Processing calendar events...")
        
        for component in old_cal.walk():
            if component.name == "VEVENT":
                events_processed += 1
                summary_raw = str(component.get("summary", ""))
                summary_unescaped = unescape_ics(summary_raw)
                
                if summary_unescaped.startswith("Info:"):
                    continue
                
                course_code = None
                for code in course_mapping:
                    if code in summary_unescaped:
                        course_code = code
                        break
                
                if course_code:
                    course_name = course_mapping[course_code]
                    event_type = get_event_type(summary_unescaped)
                    
                    parts = [course_name]
                    if event_type:
                        parts.append(event_type)
                    new_summary = clean_faculty_info(", ".join(parts))
                    
                    # Create a new calendar if it doesn't exist
                    cal_key = (course_name, event_type)
                    if cal_key not in calendars:
                        new_cal = Calendar()
                        for prop in ['VERSION', 'PRODID', 'CALSCALE', 'METHOD']:
                            if prop in old_cal:
                                new_cal.add(prop, old_cal[prop])
                        calendars[cal_key] = new_cal
                    
                    new_event = Event()
                    new_event.add("summary", new_summary)
                    
                    # Safely copy date properties
                    try:
                        new_event.add("dtstart", component["dtstart"].dt)
                        new_event.add("dtend", component["dtend"].dt)
                    except KeyError as e:
                        logger.warning(f"Missing date property in event: {e}")
                        continue
                    
                    location = clean_location(component.get("location", ""))
                    if location:
                        new_event.add("location", location)
                    
                    # Only copy essential properties, skip colors and categories
                    for prop in ["UID", "DTSTAMP", "LAST-MODIFIED"]:
                        if prop in component:
                            new_event.add(prop, component[prop])
                    
                    calendars[cal_key].add_component(new_event)
        
        # Write each calendar to a separate file
        files_created = 0
        for (course_name, event_type), cal in calendars.items():
            # Create URL-safe filename - replace all non-alphanumeric chars with underscores
            safe_name = re.sub(r'[^a-zA-Z0-9]', '_', course_name)
            safe_type = re.sub(r'[^a-zA-Z0-9]', '_', event_type)
            # Remove multiple consecutive underscores
            safe_name = re.sub(r'_+', '_', safe_name)
            safe_type = re.sub(r'_+', '_', safe_type)
            # Remove leading/trailing underscores
            safe_name = safe_name.strip('_')
            safe_type = safe_type.strip('_')
            
            filename = f"custom_calendar_{safe_name}_{safe_type}.ics"
            filepath = os.path.join(output_dir, filename)
            
            try:
                with open(filepath, "wb") as f:
                    f.write(cal.to_ical())
                files_created += 1
                logger.info(f"Created {filename}")
            except Exception as e:
                logger.error(f"Failed to write {filename}: {e}")
        
        logger.info(f"Processed {events_processed} events into {files_created} calendar files")
        return files_created
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 0

def main():
    """Main function to handle command line arguments."""
    parser = argparse.ArgumentParser(description='Process ULB calendar to separate files by course.')
    parser.add_argument('--url', type=str, 
                       default="webcal://cloud.timeedit.net/be_ulb/web/etudiant/ri69j598Y63161QZd6Qtjk5QZ58l18oo6Z971ZnyQ751k07Q247k398F70650Z3E55028C01F2t5B75EDCC98B771Q.ics",
                       help='URL of the calendar .ics file')
    parser.add_argument('--output', type=str, default="calendars",
                       help='Output directory for calendar files')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    start_time = datetime.now()
    logger.info(f"Starting calendar update at {start_time}")
    
    num_files = update_calendar(args.url, args.output)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    logger.info(f"Calendar update completed in {duration:.2f} seconds, created {num_files} files")
    
    # Create a merged calendar with all events
    merged_file = os.path.join(os.path.dirname(args.output), "custom_calendar.ics")
    try:
        create_merged_calendar(args.output, merged_file)
        logger.info(f"Created merged calendar file: {merged_file}")
    except Exception as e:
        logger.error(f"Failed to create merged calendar: {e}")

def create_merged_calendar(input_dir, output_file):
    """
    Create a single calendar file that combines all the individual calendar files.
    
    Args:
        input_dir (str): Directory containing individual calendar files
        output_file (str): Path to output the merged calendar file
    """
    merged_cal = Calendar()
    merged_cal.add('prodid', '-//ULB Custom Calendar//EN')
    merged_cal.add('version', '2.0')
    
    file_count = 0
    event_count = 0
    
    for filename in os.listdir(input_dir):
        if not filename.endswith('.ics'):
            continue
            
        file_path = os.path.join(input_dir, filename)
        try:
            with open(file_path, 'rb') as f:
                cal = Calendar.from_ical(f.read())
                
                for component in cal.walk():
                    if component.name == "VEVENT":
                        merged_cal.add_component(component)
                        event_count += 1
                        
                file_count += 1
                
        except Exception as e:
            logger.warning(f"Error processing {filename}: {e}")
    
    with open(output_file, 'wb') as f:
        f.write(merged_cal.to_ical())
    
    logger.info(f"Merged {event_count} events from {file_count} files into {output_file}")

if __name__ == "__main__":
    main()