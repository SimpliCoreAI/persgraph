from datetime import date, datetime

from second_brain.connectors.schemas import InboxEmail


def sample_bill_email() -> InboxEmail:
    return InboxEmail(id='msg_bill_001', source='fixture', sender='billing@fakebank.example', subject='Statement due June 18', timestamp=datetime.fromisoformat('2026-06-14T08:00:00+00:00'), snippet='Amount: $142.50 due June 18', bucket='bill', due_date=date.fromisoformat('2026-06-18'), amount=142.5, urgency=2, confidence=0.95, action_required=True, thread_key='t1')


def sample_overdue_bill() -> InboxEmail:
    return InboxEmail(id='msg_bill_002', source='fixture', sender='billing@utility.example', subject='Overdue notice', timestamp=datetime.fromisoformat('2026-06-14T07:00:00+00:00'), snippet='Past due', bucket='bill', due_date=date.fromisoformat('2026-06-10'), amount=87.0, urgency=4, confidence=0.95, action_required=True, thread_key='t2')


def sample_task_email() -> InboxEmail:
    return InboxEmail(id='msg_task_001', source='fixture', sender='noreply@school.test', subject='Permission slip', timestamp=datetime.fromisoformat('2026-06-13T16:30:00+00:00'), snippet='Please sign and return', bucket='followup', due_date=date.fromisoformat('2026-06-19'), urgency=2, confidence=0.88, action_required=True, thread_key='t3')


def sample_urgent_followup_email() -> InboxEmail:
    return InboxEmail(id='msg_task_002', source='fixture', sender='team@work.test', subject='Need your reply today', timestamp=datetime.fromisoformat('2026-06-14T09:30:00+00:00'), snippet='Please reply', bucket='followup', urgency=4, confidence=0.9, action_required=True, thread_key='t4')


def sample_appointment_email() -> InboxEmail:
    return InboxEmail(id='msg_appt_001', source='fixture', sender='alerts@travelco.example', subject='Flight time change', timestamp=datetime.fromisoformat('2026-06-14T10:00:00+00:00'), snippet='Departure moved', bucket='worth_checking', urgency=1, confidence=0.8, action_required=False, thread_key='t5')


def sample_url_email() -> InboxEmail:
    return InboxEmail(id='msg_url_001', source='fixture', sender='updates@service.example', subject='Account update', timestamp=datetime.fromisoformat('2026-06-14T11:00:00+00:00'), snippet='Worth checking', bucket='worth_checking', urgency=1, confidence=0.7, action_required=False, thread_key='t6')


def sample_inbox_emails() -> list[InboxEmail]:
    return [sample_bill_email(), sample_overdue_bill(), sample_task_email(), sample_urgent_followup_email(), sample_appointment_email(), sample_url_email()]
