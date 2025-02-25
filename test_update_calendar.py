import unittest
import os
import shutil
from unittest.mock import patch, MagicMock
from icalendar import Calendar, Event
from datetime import datetime, timedelta
from update_calendar import (
    unescape_ics, 
    get_event_type, 
    clean_location, 
    clean_faculty_info,
    update_calendar
)

class TestCalendarFunctions(unittest.TestCase):
    def test_unescape_ics(self):
        self.assertEqual(unescape_ics("test\\, text"), "test, text")
        self.assertEqual(unescape_ics("test\\; text"), "test; text")
        self.assertEqual(unescape_ics("test\\n text"), "test\n text")
        self.assertEqual(unescape_ics("test\\\\ text"), "test\\ text")
        self.assertEqual(unescape_ics(None), "")

    def test_get_event_type(self):
        self.assertEqual(get_event_type("INFOH3000 - Théorie"), "th")
        self.assertEqual(get_event_type("INFOH303 - Travaux pratiques"), "Labo")
        self.assertEqual(get_event_type("INFOH3000 - Exercices"), "ex")
        self.assertEqual(get_event_type("Random event"), "")

    def test_clean_location(self):
        self.assertEqual(clean_location("Salle: H.1302, Campus de la Plaine"), "H.1302")
        self.assertEqual(clean_location("H.1302, Campus"), "H.1302")
        self.assertEqual(clean_location(""), "")
        self.assertEqual(clean_location(None), "")

    def test_clean_faculty_info(self):
        self.assertEqual(clean_faculty_info("RO, Electromécanique 3"), "RO")
        self.assertEqual(clean_faculty_info("BD, B-IRCI:3"), "BD")
        self.assertEqual(clean_faculty_info("GL, B-INFO:3"), "GL")
        self.assertEqual(clean_faculty_info(None), None)

    @patch('update_calendar.requests.get')
    def test_update_calendar(self, mock_get):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        
        # Create a test calendar
        cal = Calendar()
        cal.add('prodid', '-//Test Calendar//')
        cal.add('version', '2.0')
        
        # Add a test event
        event = Event()
        event.add('summary', 'INFOH3000 - Théorie')
        event.add('dtstart', datetime.now())
        event.add('dtend', datetime.now() + timedelta(hours=2))
        event.add('location', 'Salle: H.1302, Campus')
        event.add('uid', '12345')
        event.add('dtstamp', datetime.now())
        cal.add_component(event)
        
        # Set up the mock
        mock_response.text = cal.to_ical().decode('utf-8')
        mock_get.return_value = mock_response
        
        # Create test directory
        test_dir = "test_calendars"
        
        try:
            # Run the function
            update_calendar("https://example.com/calendar.ics", test_dir)
            
            # Check that files were created
            self.assertTrue(os.path.exists(test_dir))
            files = os.listdir(test_dir)
            self.assertGreater(len(files), 0)
            
            # Check content of one file
            with open(os.path.join(test_dir, files[0]), 'rb') as f:
                test_cal = Calendar.from_ical(f.read())
                events = [e for e in test_cal.walk() if e.name == 'VEVENT']
                self.assertEqual(len(events), 1)
                
        finally:
            # Clean up
            if os.path.exists(test_dir):
                shutil.rmtree(test_dir)

if __name__ == '__main__':
    unittest.main()