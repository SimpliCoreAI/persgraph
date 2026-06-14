from datetime import datetime

from second_brain.connectors.schemas import CalendarEvent


def sample_standup_meeting() -> CalendarEvent:
    return CalendarEvent(
        id='evt_standup_001', source='fixture', title='Standup',
        start_time=datetime.fromisoformat('2026-06-14T09:00:00'),
        end_time=datetime.fromisoformat('2026-06-14T09:30:00'),
        participants=['alice@sample.test'], location='Meet', notes='', category='work', prep_needed=False,
    )


def sample_afternoon_meeting() -> CalendarEvent:
    return CalendarEvent(
        id='evt_1on1_001', source='fixture', title='1:1',
        start_time=datetime.fromisoformat('2026-06-14T14:00:00'),
        end_time=datetime.fromisoformat('2026-06-14T14:30:00'),
        participants=['bob@sample.test'], location='Meet', notes='', category='work', prep_needed=False,
    )


def sample_all_day_event() -> CalendarEvent:
    return CalendarEvent(
        id='evt_allday_001', source='fixture', title='All day event',
        start_time=datetime.fromisoformat('2026-06-15T00:00:00'),
        end_time=datetime.fromisoformat('2026-06-15T23:59:00'),
        participants=[], location='', notes='', category='personal', prep_needed=False,
    )


def sample_dental_appointment() -> CalendarEvent:
    return CalendarEvent(
        id='evt_dental_001', source='fixture', title='Dental appointment',
        start_time=datetime.fromisoformat('2026-06-16T10:00:00'),
        end_time=datetime.fromisoformat('2026-06-16T11:00:00'),
        participants=[], location='Dental Clinic', notes='', category='personal', prep_needed=True,
    )


def sample_calendar_events() -> list[CalendarEvent]:
    return [sample_afternoon_meeting(), sample_standup_meeting(), sample_all_day_event(), sample_dental_appointment()]
