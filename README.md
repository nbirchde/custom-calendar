This project rebuilds a TimeEdit `.ics` feed into multiple subscription files (one file per course + activity type), so each can have a different color in your calendar app.

Current source feed:
- ULB TimeEdit student feed configured in `update_calendar.py`

What it does:
- reads all events from the source `.ics`
- extracts course code (example: `INFOH410`)
- extracts explicit course title from event description
- detects activity type (`Theory`, `Lab`, `Exercises`, etc.)
- writes one output `.ics` per `(course code, activity type)` in [calendars/](calendars)

Run:
- `python update_calendar.py`

Tests:
- `python -m unittest -v`
