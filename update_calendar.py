import requests
from icalendar import Calendar

# Mapping: course code -> (New Name, Color)
course_mapping = {
    "INFO-H3000": ("Recherche opérationnelle", "#1E90FF"),
    "ELEC-H310": ("Digital electronics", "#FF4500"),
    "INFO-H303": ("Bases de données", "#32CD32"),
    "TRAN-H3001": ("Epistémologie des sciences et éthique de l'ingénieur", "#8A2BE2"),
    "INFO-F307": ("Génie logiciel et gestion de projets", "#FFA500")
}

def update_calendar(ics_url, output_file):
    # Convert "webcal" to "https"
    if ics_url.startswith("webcal://"):
        ics_url = "https://" + ics_url[len("webcal://"):]
    
    response = requests.get(ics_url)
    response.raise_for_status()
    cal = Calendar.from_ical(response.text)

    for component in cal.walk():
        if component.name == "VEVENT":
            summary = component.get("summary")
            if summary:
                for code, (new_name, color) in course_mapping.items():
                    if code in summary:
                        component["summary"] = new_name
                        # Add a custom color property (Apple Calendar may not use this, but it's available)
                        component["X-COLOR"] = color
                        break

    with open(output_file, "wb") as f:
        f.write(cal.to_ical())

if __name__ == "__main__":
    ics_url = "webcal://cloud.timeedit.net/be_ulb/web/etudiant/ri69j598Y63161QZd6Qtjk5QZ58l18oo6Z971ZnyQ751k07Q247k398F70650Z3E55028C01F2t5B75EDCC98B771Q.ics"
    output_file = "custom_calendar.ics"
    update_calendar(ics_url, output_file)