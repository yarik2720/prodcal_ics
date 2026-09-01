from datetime import date
import unittest
from unittest.mock import Mock, patch

from prodcal_ics import get_calendar_data, generate_events, parse_xmlcalendar_data


CALENDAR_XML = """<?xml version="1.0" encoding="UTF-8"?>
<calendar year="2026" lang="ru" date="2025.09.30" country="ru">
  <holidays>
    <holiday id="1" title="Новогодние каникулы"/>
  </holidays>
  <days>
    <day d="01.01" t="1" h="1"/>
    <day d="01.02" t="2"/>
    <day d="01.03" t="3"/>
    <day d="01.05" t="1" f="01.03"/>
  </days>
</calendar>
""".encode("utf-8")


class ParseXmlCalendarDataTest(unittest.TestCase):
    def test_parses_named_holidays_weekends_and_shortened_days(self):
        result = parse_xmlcalendar_data(2026, CALENDAR_XML)
        days_off = dict(result["days_off"])

        self.assertEqual(days_off[date(2026, 1, 1)], "Новогодние каникулы")
        self.assertEqual(days_off[date(2026, 1, 4)], "Выходной")
        self.assertEqual(days_off[date(2026, 1, 5)], "Выходной")
        self.assertNotIn(date(2026, 1, 3), days_off)
        self.assertEqual(result["shortened_days"], [date(2026, 1, 2)])

    def test_rejects_unknown_holiday_id(self):
        xml_data = CALENDAR_XML.replace(b'h="1"', b'h="999"', 1)

        with self.assertRaisesRegex(ValueError, "Unknown holiday id"):
            parse_xmlcalendar_data(2026, xml_data)


class GenerateEventsTest(unittest.TestCase):
    def test_creates_named_holiday_and_all_day_shortened_event(self):
        events = generate_events(parse_xmlcalendar_data(2026, CALENDAR_XML))
        events_by_summary = {str(event["summary"]): event for event in events}

        holiday = events_by_summary["Новогодние каникулы"]
        shortened = events_by_summary["Сокращённый рабочий день"]

        self.assertEqual(holiday.decoded("dtstart"), date(2026, 1, 1))
        self.assertEqual(holiday.decoded("dtend"), date(2026, 1, 2))
        self.assertEqual(shortened.decoded("dtstart"), date(2026, 1, 2))
        self.assertEqual(shortened.decoded("dtend"), date(2026, 1, 3))


class GetCalendarDataTest(unittest.TestCase):
    @patch("prodcal_ics.requests.get")
    def test_downloads_xml_calendar(self, requests_get):
        response = Mock(status_code=200, content=CALENDAR_XML)
        requests_get.return_value = response

        result = get_calendar_data(2026)

        self.assertEqual(result["shortened_days"], [date(2026, 1, 2)])
        response.raise_for_status.assert_called_once_with()
        requests_get.assert_called_once_with(
            "https://xmlcalendar.github.io/data/ru/2026/calendar.xml",
            headers={
                "User-Agent": (
                    "prodcal_ics/1.0 "
                    "(+https://github.com/yarik2720/prodcal_ics)"
                )
            },
            allow_redirects=True,
            timeout=30,
        )

    @patch("prodcal_ics.requests.get")
    def test_returns_none_when_year_is_not_published(self, requests_get):
        requests_get.return_value = Mock(status_code=404)

        self.assertIsNone(get_calendar_data(2027))


if __name__ == "__main__":
    unittest.main()
