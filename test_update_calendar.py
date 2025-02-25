import unittest
import os
import shutil
from unittest.mock import patch, MagicMock
from icalendar import Calendar, Event, vDatetime
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
        self.assertEqual(unescape_ics("test\\\\ text"), "test text")  # Nous supprimons tous les backslashes
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
    def test_update_calendar_basic(self, mock_get):
        """Test de base pour la création de calendriers"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        
        cal = Calendar()
        cal.add('prodid', '-//Test Calendar//')
        cal.add('version', '2.0')
        
        event = Event()
        event.add('summary', 'INFOH3000 - Théorie')
        event.add('dtstart', datetime.now())
        event.add('dtend', datetime.now() + timedelta(hours=2))
        event.add('location', 'Salle: H.1302, Campus')
        event.add('uid', '12345')
        event.add('dtstamp', datetime.now())
        cal.add_component(event)
        
        mock_response.text = cal.to_ical().decode('utf-8')
        mock_get.return_value = mock_response
        
        test_dir = "test_calendars"
        
        try:
            update_calendar("https://example.com/calendar.ics", test_dir)
            
            self.assertTrue(os.path.exists(test_dir))
            files = os.listdir(test_dir)
            self.assertGreater(len(files), 0)
            
            with open(os.path.join(test_dir, files[0]), 'rb') as f:
                test_cal = Calendar.from_ical(f.read())
                events = [e for e in test_cal.walk() if e.name == 'VEVENT']
                self.assertEqual(len(events), 1)
                
        finally:
            if os.path.exists(test_dir):
                shutil.rmtree(test_dir)

    @patch('update_calendar.requests.get')
    def test_calendar_sync(self, mock_get):
        """Test de synchronisation avec TimeEdit"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        
        # Créer un calendrier initial
        initial_cal = Calendar()
        initial_cal.add('prodid', '-//Test Calendar//')
        initial_cal.add('version', '2.0')
        
        # Ajouter un événement initial
        initial_event = Event()
        initial_event.add('summary', 'INFOH3000 - Théorie')
        initial_event.add('dtstart', datetime.now())
        initial_event.add('dtend', datetime.now() + timedelta(hours=2))
        initial_event.add('location', 'Salle: H.1302, Campus')
        initial_event.add('uid', '12345')
        initial_event.add('dtstamp', datetime.now())
        initial_cal.add_component(initial_event)
        
        # Premier appel - calendrier initial
        mock_response.text = initial_cal.to_ical().decode('utf-8')
        mock_get.return_value = mock_response
        
        test_dir = "test_calendars"
        try:
            # Première mise à jour
            update_calendar("https://example.com/calendar.ics", test_dir)
            
            # Vérifier le contenu initial
            files = os.listdir(test_dir)
            initial_events = []
            for f in files:
                with open(os.path.join(test_dir, f), 'rb') as cal_file:
                    cal = Calendar.from_ical(cal_file.read())
                    initial_events.extend([e for e in cal.walk() if e.name == 'VEVENT'])
            
            # Créer un calendrier mis à jour
            updated_cal = Calendar()
            updated_cal.add('prodid', '-//Test Calendar//')
            updated_cal.add('version', '2.0')
            
            # Modifier l'événement existant
            updated_event = Event()
            updated_event.add('summary', 'INFOH3000 - Théorie')
            updated_event.add('dtstart', datetime.now() + timedelta(days=1))  # Nouvelle date
            updated_event.add('dtend', datetime.now() + timedelta(days=1, hours=2))
            updated_event.add('location', 'Salle: H.1309, Campus')  # Nouvelle salle
            updated_event.add('uid', '12345')
            updated_event.add('dtstamp', datetime.now())
            updated_cal.add_component(updated_event)
            
            # Ajouter un nouvel événement
            new_event = Event()
            new_event.add('summary', 'INFOH3000 - Exercices')
            new_event.add('dtstart', datetime.now() + timedelta(days=2))
            new_event.add('dtend', datetime.now() + timedelta(days=2, hours=2))
            new_event.add('location', 'Salle: H.1302, Campus')
            new_event.add('uid', '12346')
            new_event.add('dtstamp', datetime.now())
            updated_cal.add_component(new_event)
            
            # Deuxième appel - calendrier mis à jour
            mock_response.text = updated_cal.to_ical().decode('utf-8')
            
            # Deuxième mise à jour
            update_calendar("https://example.com/calendar.ics", test_dir)
            
            # Vérifier les mises à jour
            files = os.listdir(test_dir)
            updated_events = []
            for f in files:
                with open(os.path.join(test_dir, f), 'rb') as cal_file:
                    cal = Calendar.from_ical(cal_file.read())
                    updated_events.extend([e for e in cal.walk() if e.name == 'VEVENT'])
            
            # Vérifications
            self.assertGreater(len(updated_events), len(initial_events), "De nouveaux événements devraient être ajoutés")
            
            # Vérifier que l'événement mis à jour a bien été modifié
            updated_theory = None
            for event in updated_events:
                if event.get('uid') == '12345':
                    updated_theory = event
                    break
            
            self.assertIsNotNone(updated_theory, "L'événement original devrait toujours exister")
            self.assertEqual(clean_location(updated_theory.get('location')), 'H.1309', 
                           "La localisation devrait être mise à jour")
            
        finally:
            if os.path.exists(test_dir):
                shutil.rmtree(test_dir)

    @patch('update_calendar.requests.get')
    def test_event_filtering(self, mock_get):
        """Test du filtrage des événements"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        
        cal = Calendar()
        cal.add('prodid', '-//Test Calendar//')
        cal.add('version', '2.0')
        
        # Ajouter un événement Info (devrait être ignoré)
        info_event = Event()
        info_event.add('summary', 'Info: Test announcement')
        info_event.add('dtstart', datetime.now())
        info_event.add('uid', 'info123')
        cal.add_component(info_event)
        
        # Ajouter un événement valide
        valid_event = Event()
        valid_event.add('summary', 'INFOH3000 - Théorie')
        valid_event.add('dtstart', datetime.now())
        valid_event.add('uid', 'valid123')
        cal.add_component(valid_event)
        
        # Ajouter un événement non reconnu
        unknown_event = Event()
        unknown_event.add('summary', 'UNKNOWN1234 - Something')
        unknown_event.add('dtstart', datetime.now())
        unknown_event.add('uid', 'unknown123')
        cal.add_component(unknown_event)
        
        mock_response.text = cal.to_ical().decode('utf-8')
        mock_get.return_value = mock_response
        
        test_dir = "test_calendars"
        try:
            update_calendar("https://example.com/calendar.ics", test_dir)
            
            # Vérifier que seul l'événement valide a été traité
            events = []
            for f in os.listdir(test_dir):
                with open(os.path.join(test_dir, f), 'rb') as cal_file:
                    cal = Calendar.from_ical(cal_file.read())
                    events.extend([e for e in cal.walk() if e.name == 'VEVENT'])
            
            self.assertEqual(len(events), 1, "Seul l'événement valide devrait être présent")
            self.assertEqual(events[0].get('uid'), 'valid123', 
                           "L'événement conservé devrait être l'événement valide")
            
        finally:
            if os.path.exists(test_dir):
                shutil.rmtree(test_dir)

if __name__ == '__main__':
    unittest.main()