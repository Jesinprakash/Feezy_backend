# utils.py

from django.utils import timezone

def is_due(dt, today=None, testing=False):
    """
    Returns True if dt is due today or in the past.
    """
    if today is None:
        today = timezone.now().astimezone(dt.tzinfo)

    if testing:
        dt = dt.replace(second=0, microsecond=0)
        today = today.replace(second=0, microsecond=0)
        return dt == today or dt < today
    else:
        return dt.date() <= today.date()

