# custom-calendar

Rebuilds the ULB TimeEdit timetable into one `.ics` file per course and
activity type, so each can be subscribed to separately with its own colour
in Google Calendar or Apple Calendar. A GitHub Action refreshes the files
every 6 hours.

## Subscribe

Use the raw GitHub URL of a file under [calendars/](calendars):

```
https://raw.githubusercontent.com/nbirchde/custom-calendar/main/calendars/<file>.ics
```

Google Calendar: Other calendars → `+` → From URL → paste. Google refreshes
URL subscriptions roughly once a day. Apple Calendar: File → New Calendar
Subscription.

`custom_calendar_all.ics` contains every course in one file.

## How it works

`update_calendar.py`:

- fetches the public TimeEdit "Horaire par cours" feed for the course object
  ids listed in `TIMEEDIT_OBJECT_IDS` (no login required)
- drops holidays, untitled break days and courses not in `COURSES`
- keeps only the student's group for split sessions (`GROUP_FILTERS`)
- writes `calendars/custom_calendar_<CODE>_<type>.ics` plus a merged file

## New academic year

1. Find each course's object id: open
   `https://cloud.timeedit.net/be_ulb/web/public/ri1Q50.html`, search the
   mnemonic, and read `data-idonly` for the entry ending in the new year
   (or query `objects.html?sid=10&types=5&partajax=t&search_text=<CODE>`).
2. Update `TIMEEDIT_OBJECT_IDS`, `TIMEEDIT_PERIOD`, `COURSES` and
   `GROUP_FILTERS`.
3. Push. The workflow runs on changes to the script and on schedule.

## Run locally

```
python -m pip install requests icalendar
python -m unittest -v
python update_calendar.py
```
