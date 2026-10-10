from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.dashboard_alarms.model import AlarmCalendar, metadata

ZONE = ZoneInfo("Europe/Berlin")
NOW = datetime(2026, 10, 10, 12, tzinfo=ZONE)


def test_persistent_disabled_alarm_and_metadata():
    model = AlarmCalendar(str(ZONE))
    uid = model.create({"start": "2026-10-11T07:00:00", "repeat": "daily",
                        "description": "Coffee & breakfast", "audio": {"media_players": ["media_player.kitchen"]}}, NOW)
    model.set_enabled(uid, False, NOW)
    restored = AlarmCalendar(str(ZONE), model.serialize())
    item = restored.definitions(NOW)[0]
    assert item["uid"] == uid
    assert not item["enabled"]
    assert item["description"] == "Coffee & breakfast"
    assert item["audio"]["media_players"] == ["media_player.kitchen"]
    restored.set_enabled(uid, True, NOW)
    assert restored.definitions(NOW)[0]["enabled"]


def test_weekday_next_and_generated_names():
    model = AlarmCalendar(str(ZONE))
    uid = model.create({"start": "2026-10-10T07:00:00", "repeat": "weekdays", "weekdays": [0, 2, 4]}, NOW)
    item = model.definitions(NOW)[0]
    assert item["name"] == "Alarm 07:00 - Mon, Wed, Fri"
    assert item["next_occurrence"].startswith("2026-10-12T07:00:00")
    assert model.root(uid).rrule.as_rrule_str() == "FREQ=WEEKLY;BYDAY=MO,WE,FR"


def test_once_future_and_reenable_validation():
    model = AlarmCalendar(str(ZONE))
    with pytest.raises(ValueError, match="future"):
        model.create({"start": "2026-10-09T12:00:00"}, NOW)
    uid = model.create({"start": "2026-10-11T12:00:00"}, NOW)
    model.set_enabled(uid, False, NOW)
    with pytest.raises(ValueError, match="future"):
        model.set_enabled(uid, True, NOW + timedelta(days=2))
    assert model.next_occurrence(uid, NOW + timedelta(days=2)) is None


@pytest.mark.parametrize("data", [
    {"start": "2026-10-11"},
    {"start": "2026-10-11T12:00:00", "repeat": "weekdays", "weekdays": []},
    {"start": "2026-10-11T12:00:00", "repeat": "weekdays", "weekdays": [7]},
    {"start": "2026-10-11T12:00:00", "audio": {"sound": "javascript:alert(1)"}},
    {"start": "2026-10-11T12:00:00", "audio": {"media_players": ["light.kitchen"]}},
    {"start": "2026-10-11T12:00:00", "audio": {"ring_minutes": 0}},
])
def test_invalid_inputs(data):
    with pytest.raises(ValueError):
        AlarmCalendar(str(ZONE)).create(data, NOW)


def test_calendar_roundtrip_preserves_description_and_audio():
    model = AlarmCalendar(str(ZONE))
    uid = model.create({"start": "2026-10-11T07:00:00", "repeat": "daily", "description": "User note",
                        "audio": {"sound": "/local/wake.mp3"}}, NOW)
    old = model.root(uid)
    model.update(uid, {"start": "2026-10-11T08:00:00", "end": "2026-10-11T08:01:00",
                       "rrule": "FREQ=DAILY", "description": old.description}, NOW, calendar_api=True)
    text, options = metadata(model.root(uid))
    assert text == "User note"
    assert options["sound"] == "/local/wake.mp3"


def test_calendar_created_alarm_and_unsupported_rule():
    model = AlarmCalendar(str(ZONE))
    model.create({"start": "2026-10-11T07:00:00", "end": "2026-10-11T07:10:00", "summary": "Whatever"}, NOW, calendar_api=True)
    assert model.definitions(NOW)[0]["enabled"]
    with pytest.raises(ValueError, match="daily|weekly"):
        model.create({"start": "2026-10-11T07:00:00", "rrule": "FREQ=MONTHLY"}, NOW, calendar_api=True)


def test_spring_gap_skipped_and_autumn_fires_first_fold_once():
    model = AlarmCalendar(str(ZONE))
    before = datetime(2026, 3, 28, 12, tzinfo=ZONE)
    uid = model.create({"start": "2026-03-28T02:30:00", "repeat": "daily"}, before)
    assert model.next_occurrence(uid, before)[0] == datetime(2026, 3, 30, 2, 30, tzinfo=ZONE)
    before = datetime(2026, 10, 24, 12, tzinfo=ZONE)
    next_when = model.next_occurrence(uid, before)[0]
    assert next_when == datetime(2026, 10, 25, 2, 30, tzinfo=ZONE, fold=0)
    assert model.next_occurrence(uid, next_when)[0].date().isoformat() == "2026-10-26"


def test_recurring_instance_delete_and_edit():
    model = AlarmCalendar(str(ZONE))
    uid = model.create({"start": "2026-10-11T07:00:00", "repeat": "daily"}, NOW)
    occurrences = model.occurrences(NOW, NOW + timedelta(days=4))
    instance = occurrences[1][1].recurrence_id
    assert instance
    model.delete(uid, recurrence_id=instance)
    assert len(model.occurrences(NOW, NOW + timedelta(days=4))) == 3
    instance = model.occurrences(NOW, NOW + timedelta(days=4))[1][1].recurrence_id
    model.update(uid, {"start": "2026-10-13T09:00:00", "end": "2026-10-13T09:01:00"}, NOW,
                 calendar_api=True, recurrence_id=instance)
    occurrences = model.occurrences(NOW, NOW + timedelta(days=4))
    assert [time.hour for time, _ in occurrences] == [7, 9, 7]
    model.set_enabled(uid, False, NOW)
    assert not model.occurrences(NOW, NOW + timedelta(days=4), enabled_only=True)


def test_future_series_edit_and_delete():
    model = AlarmCalendar(str(ZONE))
    uid = model.create({"start": "2026-10-11T07:00:00", "repeat": "daily"}, NOW)
    instance = model.occurrences(NOW, NOW + timedelta(days=4))[1][1].recurrence_id
    model.update(uid, {"start": "2026-10-12T08:00:00", "end": "2026-10-12T08:01:00", "rrule": "FREQ=DAILY"}, NOW,
                 calendar_api=True, recurrence_id=instance, recurrence_range="THISANDFUTURE")
    assert [time.hour for time, _ in model.occurrences(NOW, NOW + timedelta(days=4))] == [7, 8, 8, 8]
    future = model.occurrences(NOW, NOW + timedelta(days=4))[2][1]
    model.delete(future.uid, recurrence_id=future.recurrence_id, recurrence_range="THISANDFUTURE")
    assert len(model.occurrences(NOW, NOW + timedelta(days=4))) == 2


def test_disabled_calendar_events_remain_visible():
    model = AlarmCalendar(str(ZONE))
    uid = model.create({"start": "2026-10-11T07:00:00"}, NOW)
    model.set_enabled(uid, False, NOW)
    assert len(model.occurrences(NOW, NOW + timedelta(days=2))) == 1
    assert not model.occurrences(NOW, NOW + timedelta(days=2), enabled_only=True)
