# Custom Calendar

A Python utility for processing ULB (Université Libre de Bruxelles) calendar files into more manageable separate calendars by course and event type.

## Features

- Downloads calendar data from a ULB ICS URL
- Cleans and simplifies event information
- Organizes events into separate calendar files by course and event type
- Creates a merged calendar with all events
- Provides detailed logging
- Supports command-line arguments

## Requirements

- Python 3.6+
- Required packages: `requests`, `icalendar`

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/custom-calendar.git
cd custom-calendar

# Install dependencies
pip install requests icalendar
```

## Usage

```bash
# Run with default settings
python update_calendar.py

# Run with custom URL
python update_calendar.py --url "https://example.com/calendar.ics"

# Run with custom output directory
python update_calendar.py --output "my_calendars"

# Run with verbose logging
python update_calendar.py --verbose
```

## Output

The script creates:
- Individual `.ics` files in the `calendars/` directory (or specified output directory)
- A merged `custom_calendar.ics` file in the root directory

## Testing

Run the tests with:

```bash
python test_update_calendar.py
```

## Course Code Mapping

The script maps course codes to shorter names:

- INFOH3000 → RO (Recherche Opérationnelle)
- ELECH310 → DE (Digital Electronics)
- INFOH303 → BD (Bases de données)
- TRANH3001 → Éthique
- INFOF307 → GL (Génie Logiciel)
- BINGF3004 → BINGF3004

New course codes can be added to the `course_mapping` dictionary in `update_calendar.py`.

## Event Types

Events are categorized as:
- `th` - Theory/lectures
- `Labo` - Practical work
- `ex` - Exercises
