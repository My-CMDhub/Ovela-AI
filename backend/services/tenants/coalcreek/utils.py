"""
Coal Creek Motel - Utility Functions
=====================================
Time-based utilities for after-hours handling and business logic.
"""

from datetime import datetime, time
from zoneinfo import ZoneInfo
from typing import Optional

# Coal Creek Timezone
COALCREEK_TZ = ZoneInfo("Australia/Melbourne")

# Business Hours (from config)
RECEPTION_OPEN_TIME = time(8, 0)   # 8:00 AM
RECEPTION_CLOSE_TIME = time(20, 0)  # 8:00 PM

# Hard cut-off for same-day bookings (5 mins before close)
HARD_CUTOFF_TIME = time(19, 55)  # 7:55 PM


def get_current_time(current_time_str: Optional[str] = None) -> datetime:
    """
    Get current time in Coal Creek timezone.
    
    Args:
        current_time_str: Optional time string from voice handler (e.g., "09:30 PM")
                         If None, uses system time
    
    Returns:
        datetime object in Australia/Melbourne timezone
    """
    if current_time_str:
        # Parse the time string from voice handler format
        # Expected format: "HH:MM AM/PM" or "H:MM AM/PM"
        try:
            # Get current date in Coal Creek timezone
            now = datetime.now(COALCREEK_TZ)
            
            # Parse time component
            parsed_time = datetime.strptime(current_time_str.strip(), "%I:%M %p").time()
            
            # Combine date and parsed time
            return datetime.combine(now.date(), parsed_time, tzinfo=COALCREEK_TZ)
        except ValueError:
            # If parsing fails, fall back to system time
            pass
    
    # Default to current system time in Coal Creek timezone
    return datetime.now(COALCREEK_TZ)


def is_after_hours(current_time_str: Optional[str] = None) -> bool:
    """
    Check if current time is outside reception hours (8am-8pm).
    
    Args:
        current_time_str: Optional time string from voice handler
    
    Returns:
        True if outside business hours, False otherwise
    """
    current = get_current_time(current_time_str)
    current_time_only = current.time()
    
    # After hours if before opening OR after closing
    if current_time_only < RECEPTION_OPEN_TIME or current_time_only >= RECEPTION_CLOSE_TIME:
        return True
    
    return False


def is_past_cutoff(current_time_str: Optional[str] = None) -> bool:
    """
    Check if past hard cut-off time (7:55 PM) for same-day bookings.
    
    Args:
        current_time_str: Optional time string from voice handler
    
    Returns:
        True if past cut-off time, False otherwise
    """
    current = get_current_time(current_time_str)
    current_time_only = current.time()
    
    return current_time_only >= HARD_CUTOFF_TIME


def is_same_day_request(check_in_date_str: str) -> bool:
    """
    Check if check-in date is today.
    
    Args:
        check_in_date_str: Check-in date in YYYY-MM-DD format
    
    Returns:
        True if check-in is today, False otherwise
    """
    try:
        check_in_date = datetime.strptime(check_in_date_str, "%Y-%m-%d").date()
        today = datetime.now(COALCREEK_TZ).date()
        
        return check_in_date == today
    except ValueError:
        # If date parsing fails, assume not same-day to be safe
        return False


def should_decline_same_day_booking(
    check_in_date_str: str,
    current_time_str: Optional[str] = None
) -> bool:
    """
    Determine if a same-day booking request should be declined due to after-hours cut-off.
    
    Args:
        check_in_date_str: Check-in date in YYYY-MM-DD format
        current_time_str: Optional current time string
    
    Returns:
        True if booking should be declined (same-day + past cut-off), False otherwise
    """
    if not is_same_day_request(check_in_date_str):
        # Future booking - always accept
        return False
    
    # Same-day booking - check if past cut-off
    return is_past_cutoff(current_time_str)


def get_after_hours_message(
    check_in_date_str: str,
    current_time_str: Optional[str] = None
) -> Optional[str]:
    """
    Get the appropriate after-hours message for the AI to use.
    
    Args:
        check_in_date_str: Check-in date in YYYY-MM-DD format
        current_time_str: Optional current time string
    
    Returns:
        Message string to use, or None if during business hours
    """
    if not is_after_hours(current_time_str):
        return None
    
    # Check if same-day and past cut-off
    if should_decline_same_day_booking(check_in_date_str, current_time_str):
        return (
            "I'm sorry, reception is closed for tonight and we can't facilitate "
            "new check-ins until staff arrive tomorrow at 8am. I'd be happy to "
            "take a booking for tomorrow onwards if you'd like?"
        )
    
    # After hours but future booking (acceptable)
    return (
        "Reception is closed right now, but I've sent your request to the manager "
        "who will review it first thing tomorrow morning."
    )
