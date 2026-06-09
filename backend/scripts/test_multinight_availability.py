"""
Coal Creek Motel - Multi-Night Availability Checker
====================================================
Enhanced script that validates availability for EACH night in a multi-night stay.

Tests the critical edge case: A room must be available on ALL nights, not just check-in.
"""

import asyncio
import sys
sys.path.append('/Applications/Journey of pro/Nona/backend')

from scripts.test_coalcreek_scraping import scrape_availability
from datetime import datetime, timedelta
import json
from typing import Optional


async def check_multinight_availability(
    check_in_str: str,
    check_out_str: str,
    room_type: Optional[str] = None
) -> dict:
    """
    Check availability for EACH night in a multi-night stay.
    
    A room is only available if it's available on ALL nights, not just check-in.
    
    Example: Double Room sold out on Feb 11
    - Feb 10-11 (1 night): Check Feb 10 only → Available
    - Feb 10-13 (3 nights): Check Feb 10, 11, 12 → BLOCKED (Feb 11 unavailable)
    
    Args:
        check_in_str: Check-in date YYYY-MM-DD
        check_out_str: Check-out date YYYY-MM-DD
        room_type: Optional specific room to check (e.g., "Double Room")
        
    Returns:
        {
            'success': bool,
            'check_in': str,
            'check_out': str,
            'total_nights': int,
            'available_all_nights': bool,
            'blocked_dates': list,  # Dates where room(s) unavailable
            'available_rooms': list,  # Rooms available ALL nights
            'per_night_results': dict  # Detailed breakdown
        }
    """
    check_in = datetime.strptime(check_in_str, "%Y-%m-%d")
    check_out = datetime.strptime(check_out_str, "%Y-%m-%d")
    nights = (check_out - check_in).days
    
    print("\n" + "="*80)
    print("🏨 MULTI-NIGHT AVAILABILITY CHECK")
    print("="*80)
    print(f"📅 Check-in:  {check_in_str}")
    print(f"📅 Check-out: {check_out_str}")
    print(f"🌙 Nights:    {nights}")
    if room_type:
        print(f"🛏️  Room Type: {room_type}")
    print("="*80 + "\n")
    
    print(f"⏳ Checking availability for EACH of {nights} nights...\n")
    
    # Track per-night results
    per_night_results = {}
    blocked_dates = []
    room_availability_tracker = {}  # Track which rooms available each night
    
    # Check each individual night
    for i in range(nights):
        night_date = check_in + timedelta(days=i)
        next_day = night_date + timedelta(days=1)
        
        night_str = night_date.strftime("%Y-%m-%d")
        next_str = next_day.strftime("%Y-%m-%d")
        
        print(f"📅 Night {i+1}/{nights}: {night_str}")
        print("-" * 40)
        
        # Scrape this specific night
        result = await scrape_availability(night_str, next_str, nights=1)
        
        if not result.get("success"):
            print(f"❌ Failed to check {night_str}: {result.get('error')}\n")
            return {
                'success': False,
                'error': f"Failed to check night {i+1}: {result.get('error')}"
            }
        
        availability = result.get("availability", [])
        per_night_results[night_str] = availability
        
        if room_type:
            # Check specific room
            room_avail = any(
                r.get('room_type') == room_type and r.get('available')
                for r in availability
            )
            
            if room_avail:
                print(f"   ✅ {room_type}: Available\n")
            else:
                print(f"   ❌ {room_type}: NOT AVAILABLE\n")
                blocked_dates.append(night_str)
        else:
            # Track all rooms
            for room in availability:
                room_name = room.get('room_type')
                if room_name not in room_availability_tracker:
                    room_availability_tracker[room_name] = {'available_nights': 0, 'total_nights': 0}
                
                room_availability_tracker[room_name]['total_nights'] += 1
                if room.get('available'):
                    room_availability_tracker[room_name]['available_nights'] += 1
                    print(f"   ✅ {room_name}: Available")
                else:
                    print(f"   ❌ {room_name}: NOT AVAILABLE")
            
            # Check if ALL rooms sold out this night
            all_sold_out = all(not r.get('available') for r in availability)
            if all_sold_out:
                blocked_dates.append(night_str)
            print()
        
        # Small delay between checks
        if i < nights - 1:
            await asyncio.sleep(1)
    
    # Determine which rooms are available for ALL nights
    available_all_nights_rooms = []
    
    if room_type:
        # For specific room check
        available_all_nights = len(blocked_dates) == 0
        if available_all_nights:
            available_all_nights_rooms = [room_type]
    else:
        # Find rooms available ALL nights
        for room_name, stats in room_availability_tracker.items():
            if stats['available_nights'] == stats['total_nights']:
                available_all_nights_rooms.append(room_name)
        
        available_all_nights = len(available_all_nights_rooms) > 0
    
    # Summary
    print("\n" + "="*80)
    print("📊 MULTI-NIGHT AVAILABILITY SUMMARY")
    print("="*80 + "\n")
    
    if available_all_nights:
        print(f"✅ AVAILABLE for all {nights} nights")
        print(f"\n   Rooms available for entire stay:")
        for room in available_all_nights_rooms:
            print(f"   • {room}")
    else:
        print(f"❌ NOT AVAILABLE for all {nights} nights")
        print(f"\n   Blocked dates: {', '.join(blocked_dates)}")
        if room_type:
            print(f"   {room_type} is sold out on these dates")
        else:
            print(f"\n   Rooms available for entire stay:")
            if available_all_nights_rooms:
                for room in available_all_nights_rooms:
                    print(f"   • {room}")
            else:
                print(f"   ⚠️  No single room available for all nights")
    
    # Show per-room breakdown if checking all rooms
    if not room_type and room_availability_tracker:
        print(f"\n📋 Per-Room Breakdown:")
        for room_name, stats in room_availability_tracker.items():
            avail_nights = stats['available_nights']
            total = stats['total_nights']
            if avail_nights == total:
                print(f"   ✅ {room_name}: {avail_nights}/{total} nights")
            else:
                print(f"   ⚠️  {room_name}: {avail_nights}/{total} nights (PARTIAL)")
    
    print("\n" + "="*80)
    
    return {
        'success': True,
        'check_in': check_in_str,
        'check_out': check_out_str,
        'total_nights': nights,
        'available_all_nights': available_all_nights,
        'blocked_dates': blocked_dates,
        'available_rooms': available_all_nights_rooms,
        'per_night_results': per_night_results,
        'room_availability_breakdown': room_availability_tracker if not room_type else None
    }


async def main():
    """Test multi-night availability checker"""
    
    if len(sys.argv) < 3:
        print("Usage: python test_multinight.py CHECK_IN CHECK_OUT [ROOM_TYPE]")
        print("Example: python test_multinight.py 2026-02-10 2026-02-13 'Double Room'")
        sys.exit(1)
    
    check_in = sys.argv[1]
    check_out = sys.argv[2]
    room_type = sys.argv[3] if len(sys.argv) > 3 else None
    
    result = await check_multinight_availability(check_in, check_out, room_type)
    
    # JSON output
    print("\n" + "="*80)
    print("📋 JSON RESULT")
    print("="*80 + "\n")
    print(json.dumps(result, indent=2))
    
    # Exit code based on availability
    sys.exit(0 if result.get('success') else 1)


if __name__ == "__main__":
    asyncio.run(main())
