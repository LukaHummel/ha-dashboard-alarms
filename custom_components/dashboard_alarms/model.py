"""Calendar model. No Home Assistant imports: independently testable."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from dateutil.rrule import rrulestr

from ical.calendar import Calendar
from ical.calendar_stream import IcsCalendarStream
from ical.event import Event, EventStatus
from ical.store import EventStore
from ical.types import Range, Recur

META_MARKER = "\n[dashboard_alarms:v1]"
DAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
UTC = timezone.utc


def local_datetime(value, zone: ZoneInfo) -> datetime:
    """Interpret floating calendar times in the HA zone, reject all-day input."""
    if isinstance(value, str):
        if "T" not in value and " " not in value:
            raise ValueError("Choose a date and time, not an all-day event.")
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime):
        raise ValueError("Choose a date and time, not an all-day event.")
    return value.replace(tzinfo=zone) if value.tzinfo is None else value.astimezone(zone)


def valid_wall_time(value: datetime, zone: ZoneInfo) -> datetime | None:
    """Skip imaginary times; use only fold=0 when the clock repeats."""
    wall = value.astimezone(zone).replace(tzinfo=None)
    first = wall.replace(tzinfo=zone, fold=0)
    if first.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != wall:
        return None
    return first


def metadata(event: Event) -> tuple[str, dict]:
    text = event.description or ""
    if META_MARKER not in text:
        return text, {}
    user_text, encoded = text.rsplit(META_MARKER, 1)
    try:
        value = json.loads(encoded)
        if isinstance(value, dict):
            return user_text, value
    except (ValueError, TypeError):
        pass
    raise ValueError("Alarm metadata is damaged; restore the calendar from backup.")


def with_metadata(description: str, options: dict) -> str:
    return description + META_MARKER + json.dumps(options, separators=(",", ":"))


def recurrence(rule: str | None) -> tuple[str, list[int]]:
    """Only the supported UI patterns; bounded rules remain calendar-editable."""
    if not rule:
        return "once", []
    parts = dict(part.split("=", 1) for part in rule.upper().split(";"))
    if set(parts) - {"FREQ", "INTERVAL", "BYDAY", "COUNT", "UNTIL"}:
        raise ValueError("Use daily or weekly selected-weekday recurrence.")
    if parts.get("INTERVAL", "1") != "1":
        raise ValueError("Only daily and weekly recurrence intervals of 1 are supported.")
    if parts.get("FREQ") == "DAILY" and "BYDAY" not in parts:
        Recur.from_rrule(rule)
        return "daily", []
    if parts.get("FREQ") == "WEEKLY":
        days = parts.get("BYDAY", "").split(",")
        if days and all(day in DAYS for day in days):
            Recur.from_rrule(rule)
            return "weekdays", sorted({DAYS.index(day) for day in days})
    raise ValueError("Use daily or weekly recurrence with selected weekdays.")


def rule_for(mode: str, weekdays: list[int]) -> str | None:
    if mode == "once":
        return None
    if mode == "daily":
        return "FREQ=DAILY"
    if mode == "weekdays" and weekdays:
        if any(type(day) is not int or not 0 <= day <= 6 for day in weekdays):
            raise ValueError("Weekdays must be integers from 0 (Monday) to 6 (Sunday).")
        return "FREQ=WEEKLY;BYDAY=" + ",".join(DAYS[day] for day in sorted(set(weekdays)))
    raise ValueError("Choose once, daily, or at least one weekday.")


def generated_name(start: datetime, rule: str | None) -> str:
    mode, days = recurrence(rule)
    if mode == "once":
        return f"Alarm {start:%d %b %H:%M}"
    repeat = "Daily" if mode == "daily" else ", ".join(LABELS[day] for day in days)
    return f"Alarm {start:%H:%M} - {repeat}"


def validate_options(options: dict) -> dict:
    result = {}
    if "media_players" in options:
        targets = options["media_players"]
        if targets is not None:
            if not isinstance(targets, list) or any(
                not isinstance(t, str) or not t.startswith("media_player.") for t in targets
            ):
                raise ValueError("Audio targets must be media-player entity IDs.")
            result["media_players"] = list(dict.fromkeys(targets))
    if options.get("sound"):
        sound = str(options["sound"])
        if not sound.startswith(("/", "http://", "https://", "media-source://")):
            raise ValueError("Use a local sound path, media-source URI, or HTTP(S) URL.")
        result["sound"] = sound
    for key in ("snooze_minutes", "ring_minutes"):
        if key in options and options[key] is not None:
            value = options[key]
            if type(value) is not int or not 1 <= value <= 120:
                raise ValueError(f"{key} must be a whole number from 1 to 120.")
            result[key] = value
    return result


class AlarmCalendar:
    """Authoritative iCalendar event store, including recurring exceptions."""

    def __init__(self, zone: str, ics: str | None = None):
        self.zone = ZoneInfo(zone)
        self.calendar = IcsCalendarStream.calendar_from_ics(ics) if ics else Calendar()
        self.calendar.prodid = "-//Dashboard Alarms//EN"

    def serialize(self) -> str:
        return IcsCalendarStream.calendar_to_ics(self.calendar)

    def clone(self) -> AlarmCalendar:
        return AlarmCalendar(str(self.zone), self.serialize())

    def roots(self) -> list[Event]:
        return [event for event in self.calendar.events if not event.recurrence_id]

    def root(self, uid: str) -> Event:
        for event in self.roots():
            if event.uid == uid:
                return event
        raise ValueError("Alarm no longer exists. Refresh the card.")

    def create(self, data: dict, now: datetime, *, calendar_api=False) -> str:
        event = self._event(data, now, calendar_api=calendar_api)
        EventStore(self.calendar).add(event)
        return event.uid

    def _event(self, data: dict, now: datetime, *, calendar_api=False, old=None) -> Event:
        start = local_datetime(data["start"], self.zone)
        start = valid_wall_time(start, self.zone)
        if start is None:
            raise ValueError("This local time does not exist because the clock moves forward.")
        # Store floating local wall time, as the built-in Local Calendar does.
        wall = start.replace(tzinfo=None)
        old_description, old_options = metadata(old) if old else ("", {})
        rule = data.get("rrule") if calendar_api else rule_for(
            data.get("repeat", "once"), data.get("weekdays", [])
        )
        recurrence(rule)
        enabled = data.get("enabled", old.status != EventStatus.TENTATIVE if old else True)
        if type(enabled) is not bool:
            raise ValueError("Enabled must be true or false.")
        if not rule and enabled and start.timestamp() <= now.timestamp() and not (calendar_api and old):
            raise ValueError("Choose a future date/time for a one-time alarm.")
        options = old_options if calendar_api else validate_options(data.get("audio", old_options))
        description = data.get("description", old_description)
        # Standard calendar UI round trips the description including our marker.
        if META_MARKER in description:
            description = description.rsplit(META_MARKER, 1)[0]
        end = local_datetime(data.get("end", start + timedelta(minutes=1)), self.zone)
        if end.timestamp() <= start.timestamp():
            raise ValueError("The event end must be after its start.")
        parsed_rule = Recur.from_rrule(rule) if rule else None
        if parsed_rule and isinstance(parsed_rule.until, datetime) and parsed_rule.until.tzinfo:
            parsed_rule.until = parsed_rule.until.astimezone(self.zone).replace(tzinfo=None)
        return Event(
            uid=old.uid if old else str(uuid4()),
            start=wall, end=end.replace(tzinfo=None),
            summary=generated_name(start, rule),
            description=with_metadata(description, options),
            location=data.get("location", old.location if old else None),
            rrule=parsed_rule,
            status=EventStatus.CONFIRMED if enabled else EventStatus.TENTATIVE,
        )

    def update(self, uid: str, data: dict, now: datetime, *, calendar_api=False,
               recurrence_id=None, recurrence_range=None):
        root = self.root(uid)
        event = self._event(data, now, calendar_api=calendar_api, old=root)
        EventStore(self.calendar).edit(
            uid, event, recurrence_id=recurrence_id,
            recurrence_range=Range.THIS_AND_FUTURE if recurrence_range == "THISANDFUTURE" else Range.NONE,
        )

    def set_enabled(self, uid: str, enabled: bool, now: datetime):
        root = self.root(uid)
        if type(enabled) is not bool:
            raise ValueError("Enabled must be true or false.")
        if enabled and not root.rrule and root.status == EventStatus.TENTATIVE:
            # Re-arm the saved local time for its next occurrence, keeping the UID,
            # event duration, description, and audio overrides intact.
            original = local_datetime(root.start, self.zone).replace(tzinfo=None)
            duration = local_datetime(root.end, self.zone).replace(tzinfo=None) - original
            day = now.astimezone(self.zone).date()
            while True:
                wall = datetime.combine(day, original.time())
                when = valid_wall_time(wall.replace(tzinfo=self.zone), self.zone)
                if when is not None and when.timestamp() > now.timestamp():
                    break
                day += timedelta(days=1)
            root.dtstart = wall
            root.dtend = wall + duration
            root.summary = generated_name(when, None)
        # Apply to all exceptions belonging to the same series as well.
        for event in self.calendar.events:
            if event.uid == uid:
                event.status = EventStatus.CONFIRMED if enabled else EventStatus.TENTATIVE

    def delete(self, uid: str, recurrence_id=None, recurrence_range=None):
        self.root(uid)
        EventStore(self.calendar).delete(
            uid, recurrence_id=recurrence_id,
            recurrence_range=Range.THIS_AND_FUTURE if recurrence_range == "THISANDFUTURE" else Range.NONE,
        )

    def occurrences(self, start: datetime, end: datetime, *, enabled_only=False):
        result = []
        for event in self.calendar.timeline_tz(self.zone).overlapping(start, end):
            when = valid_wall_time(local_datetime(event.start, self.zone), self.zone)
            if when is None or (enabled_only and event.status == EventStatus.TENTATIVE):
                continue
            result.append((when, event))
        return sorted(result, key=lambda item: item[0].timestamp())

    def next_occurrence(self, uid: str, after: datetime):
        # Each series is expanded independently: distant once-only alarms do not
        # make us expand every daily alarm for years.
        events = [event for event in self.calendar.events if event.uid == uid]
        calendar = Calendar(events=events)
        for index, event in enumerate(calendar.timeline_tz(self.zone).active_after(after)):
            if index >= 10000:
                raise ValueError("Recurrence search exceeded its limit.")
            when = valid_wall_time(local_datetime(event.start, self.zone), self.zone)
            if when is not None and when.timestamp() > after.timestamp():
                return when, event
        return None

    def last_occurrence(self, uid: str, since: datetime, before: datetime):
        """Find latest missed occurrence without expanding years of daily events."""
        root = self.root(uid)
        if root.status == EventStatus.TENTATIVE:
            return None
        start = local_datetime(root.start, self.zone).replace(tzinfo=None)
        bound = before.astimezone(self.zone).replace(tzinfo=None)
        sequence = rrulestr(root.rrule.as_rrule_str(), dtstart=start) if root.rrule else None
        candidate = sequence.before(bound, inc=True) if sequence else start
        candidates = [local_datetime(event.start, self.zone).replace(tzinfo=None)
                      for event in self.calendar.events if event.uid == uid and event.recurrence_id]
        for _ in range(10000):
            if candidate is None:
                break
            when = valid_wall_time(candidate.replace(tzinfo=self.zone), self.zone)
            if when and when.timestamp() <= since.timestamp():
                break
            if when and when.timestamp() <= before.timestamp():
                actual = self.occurrences(when - timedelta(seconds=1), when + timedelta(seconds=1), enabled_only=True)
                if any(event.uid == uid and instant.timestamp() == when.timestamp() for instant, event in actual):
                    candidates.append(candidate)
                    break
            if not sequence:
                break
            candidate = sequence.before(candidate, inc=False)
        found = []
        for candidate in candidates:
            when = valid_wall_time(candidate.replace(tzinfo=self.zone), self.zone)
            if when and since.timestamp() < when.timestamp() <= before.timestamp():
                for instant, event in self.occurrences(when - timedelta(seconds=1), when + timedelta(seconds=1), enabled_only=True):
                    if event.uid == uid and instant.timestamp() == when.timestamp():
                        found.append((instant, event))
        return max(found, key=lambda item: item[0].timestamp()) if found else None

    def definitions(self, now: datetime) -> list[dict]:
        result = []
        for root in self.roots():
            text, options = metadata(root)
            rule = root.rrule.as_rrule_str() if root.rrule else None
            mode, days = recurrence(rule)
            start = local_datetime(root.start, self.zone)
            upcoming = self.next_occurrence(root.uid, now)
            result.append({
                "uid": root.uid, "name": root.summary,
                "start": start.isoformat(), "local_start": start.strftime("%Y-%m-%dT%H:%M:%S"),
                "repeat": mode, "weekdays": days, "rrule": rule,
                "enabled": root.status != EventStatus.TENTATIVE,
                "description": text, "audio": options,
                "next_occurrence": upcoming[0].isoformat() if upcoming else None,
                "has_exceptions": any(e.uid == root.uid and e.recurrence_id for e in self.calendar.events)
                    or bool(root.exdate),
            })
        return sorted(result, key=lambda item: (not item["enabled"], item["next_occurrence"] or "9999", item["uid"]))
