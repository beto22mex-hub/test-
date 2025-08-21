from datetime import datetime, time
from django.utils import timezone


def get_shift_from_datetime(dt):
    """
    Determine which shift a datetime belongs to
    First shift: 6:00 AM to 3:30 PM
    Second shift: 3:30 PM to 12:00 AM (midnight)
    """
    if dt.tzinfo is None:
        dt = timezone.make_aware(dt)
    
    time_only = dt.time()
    
    # First shift: 6:00 AM to 3:30 PM
    if time(6, 0) <= time_only < time(15, 30):
        return 1
    # Second shift: 3:30 PM to 12:00 AM
    elif time(15, 30) <= time_only < time(23, 59, 59):
        return 2
    # Night hours (12:00 AM to 6:00 AM) belong to previous day's second shift
    else:
        return 2


def get_shift_display(shift_number):
    """Get display name for shift"""
    if shift_number == 1:
        return "Primer Turno (6:00 AM - 3:30 PM)"
    elif shift_number == 2:
        return "Segundo Turno (3:30 PM - 12:00 AM)"
    else:
        return "Turno Desconocido"


def get_current_shift():
    """Get current shift number"""
    return get_shift_from_datetime(timezone.now())
