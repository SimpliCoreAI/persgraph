from datetime import date, datetime

from second_brain.connectors.schemas import DailyContext, PreBriefSection


def sample_daily_context() -> DailyContext:
    return DailyContext(
        date=date.fromisoformat('2026-06-14'),
        generated_at=datetime.fromisoformat('2026-06-14T07:00:00+00:00'),
        events_today=PreBriefSection(items=[
            {'id':'evt_standup_001','title':'Standup','start_time':'2026-06-14T09:00:00'},
            {'id':'evt_1on1_001','title':'1:1','start_time':'2026-06-14T14:00:00'}
        ], capped=False, cap_limit=5),
        events_upcoming=PreBriefSection(items=[{'id':'evt_allday_001','title':'All day event','start_time':'2026-06-15T00:00:00'}], capped=False, cap_limit=5),
        bills_due=PreBriefSection(items=[{'id':'msg_bill_001','subject':'Statement due June 18','amount':142.5,'due_date':'2026-06-18'}], capped=False, cap_limit=5),
        followups_needed=PreBriefSection(items=[{'id':'msg_task_001','subject':'Permission slip'}], capped=False, cap_limit=5),
        worth_checking=PreBriefSection(items=[{'id':'msg_appt_001','subject':'Flight time change'}], capped=False, cap_limit=5),
        carry_forward=PreBriefSection(items=[], capped=False, cap_limit=5),
        suggested_priorities=['Review bill due June 18'],
    )


def sample_empty_daily_context() -> DailyContext:
    return DailyContext(
        date=date.fromisoformat('2026-06-14'),
        generated_at=datetime.fromisoformat('2026-06-14T07:00:00+00:00'),
        events_today=PreBriefSection(items=[], capped=False, cap_limit=5),
        events_upcoming=PreBriefSection(items=[], capped=False, cap_limit=5),
        bills_due=PreBriefSection(items=[], capped=False, cap_limit=5),
        followups_needed=PreBriefSection(items=[], capped=False, cap_limit=5),
        worth_checking=PreBriefSection(items=[], capped=False, cap_limit=5),
        carry_forward=PreBriefSection(items=[], capped=False, cap_limit=5),
        suggested_priorities=[],
    )
