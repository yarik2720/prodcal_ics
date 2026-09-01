#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from icalendar import Calendar, Event
import requests

from datetime import date, datetime, timedelta
import argparse
import logging
import hashlib
import xml.etree.ElementTree as ET


XMLCALENDAR_URL = "https://xmlcalendar.github.io/data/ru/{year}/calendar.xml"


def parse_xmlcalendar_data(year, xml_data):
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as error:
        raise ValueError(
            f"Invalid XML received from production calendar source for {year}"
        ) from error

    if root.tag != "calendar" or root.get("year") != str(year):
        raise ValueError(f"Unexpected calendar year in response for {year}")

    holidays_element = root.find("holidays")
    days_element = root.find("days")
    if holidays_element is None or days_element is None:
        raise ValueError(f"Missing holidays or days section in calendar for {year}")

    holiday_titles = {}
    for holiday in holidays_element.findall("holiday"):
        holiday_id = holiday.get("id")
        title = holiday.get("title")
        if not holiday_id or not title:
            raise ValueError(f"Invalid holiday definition in calendar for {year}")
        if holiday_id in holiday_titles:
            raise ValueError(
                f"Duplicate holiday id in calendar for {year}: {holiday_id}"
            )
        holiday_titles[holiday_id] = title

    special_days = {}
    for day_element in days_element.findall("day"):
        date_value = day_element.get("d")
        day_type = day_element.get("t")
        holiday_id = day_element.get("h")

        try:
            month_value, day_value = date_value.split(".")
            calendar_date = date(year, int(month_value), int(day_value))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError(
                f"Invalid day value in calendar for {year}: {date_value}"
            ) from error

        if date_value != calendar_date.strftime("%m.%d"):
            raise ValueError(f"Invalid day format in calendar for {year}: {date_value}")
        if day_type not in {"1", "2", "3"}:
            raise ValueError(
                f"Invalid day type in calendar for {calendar_date}: {day_type}"
            )
        if holiday_id is not None and holiday_id not in holiday_titles:
            raise ValueError(
                f"Unknown holiday id in calendar for {calendar_date}: {holiday_id}"
            )
        if calendar_date in special_days:
            raise ValueError(f"Duplicate day in calendar for {calendar_date}")

        special_days[calendar_date] = {
            "type": day_type,
            "holiday_id": holiday_id,
        }

    days_off = []
    shortened_days = []
    calendar_date = date(year, 1, 1)
    end_date = date(year + 1, 1, 1)

    while calendar_date < end_date:
        special_day = special_days.get(calendar_date)

        if special_day is not None:
            if special_day["type"] == "1":
                summary = holiday_titles.get(
                    special_day["holiday_id"], "Выходной"
                )
                days_off.append((calendar_date, summary))
            elif special_day["type"] == "2":
                shortened_days.append(calendar_date)
        elif calendar_date.weekday() >= 5:
            days_off.append((calendar_date, "Выходной"))

        calendar_date += timedelta(days=1)

    return {"days_off": days_off, "shortened_days": shortened_days}


def get_calendar_data(year):
    url = XMLCALENDAR_URL.format(year=year)

    logging.info(url)

    headers = {
        "User-Agent": "prodcal_ics/1.0 (+https://github.com/yarik2720/prodcal_ics)"
    }

    response = requests.get(
        url, headers=headers, allow_redirects=True, timeout=30
    )

    if response.status_code == 404:
        logging.warning("Production calendar for %s is not available yet", year)
        return None

    response.raise_for_status()

    return parse_xmlcalendar_data(year, response.content)


def create_all_day_event(summary, day_start, day_end):
    event = Event()
    event.add("summary", summary)
    event.add("dtstart", day_start)
    event.add("dtend", day_end + timedelta(days=1))

    # UID is REQUIRED https://tools.ietf.org/html/rfc5545#section-3.6.1
    uid = hashlib.sha512(
        f"{summary}\0{day_start.isoformat()}\0{day_end.isoformat()}".encode("utf-8")
    ).hexdigest()
    event.add("uid", uid)

    return event


def generate_events(calendar_data):
    events = []
    days_off = calendar_data["days_off"]

    if days_off:
        group_start, group_summary = days_off[0]
        group_end = group_start

        for calendar_date, summary in days_off[1:]:
            if (
                calendar_date == group_end + timedelta(days=1)
                and summary == group_summary
            ):
                group_end = calendar_date
                continue

            events.append(
                create_all_day_event(group_summary, group_start, group_end)
            )
            group_start = group_end = calendar_date
            group_summary = summary

        events.append(create_all_day_event(group_summary, group_start, group_end))

    for calendar_date in calendar_data["shortened_days"]:
        events.append(
            create_all_day_event(
                "Сокращённый рабочий день", calendar_date, calendar_date
            )
        )

    events.sort(key=lambda event: event.decoded("dtstart"))

    return events


def parse_args():
    parser = argparse.ArgumentParser(
        description="This script fetches data about production calendar and generates .ics file with it."
    )

    default_output_file = "test.ics"
    parser.add_argument(
        "-o",
        dest="output_file",
        metavar="out",
        default=default_output_file,
        help="output file (default: {0})".format(default_output_file),
    )

    parser.add_argument(
        "--start-year",
        metavar="yyyy",
        type=int,
        default=datetime.today().year,
        help="year calendar starts (default: current year)",
    )

    parser.add_argument(
        "--end-year",
        metavar="yyyy",
        type=int,
        default=(datetime.today().year + 1),
        help="year calendar ends (default: next year)",
    )

    parser.add_argument("--log-level", metavar="level", default="INFO")

    return parser.parse_args()


def generate_calendar(events):
    cal = Calendar()
    cal.add("prodid", "-//My calendar product//mxm.dk//")
    cal.add("version", "2.0")
    cal.add("NAME", "Производственный календарь")
    cal.add("X-WR-CALNAME", "Производственный календарь")

    for e in events:
        cal.add_component(e)

    return cal


def setup_logging(log_level):
    logging_level = getattr(logging, log_level.upper(), None)

    if not isinstance(logging_level, int):
        raise ValueError("Invalid log level: {0}".format(log_level))

    logging.basicConfig(
        level=logging_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="[%d/%m/%Y:%H:%M:%S %z]",
    )


if __name__ == "__main__":
    args = parse_args()
    setup_logging(args.log_level)

    events = []

    # (args.end_year + 1) because range() function doesn't include right margin
    for year in range(args.start_year, args.end_year + 1, 1):
        calendar_data = get_calendar_data(year)

        if not calendar_data:
            break

        events += generate_events(calendar_data)

    cal = generate_calendar(events)

    with open(args.output_file, "wb") as f:
        f.write(cal.to_ical())
