"""
Coal Creek Motel - Live Availability Scraper
==========================================
Production scraper using ScrapingBee for live availability.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SCRAPPINGBEE_API_KEY = os.getenv("SCRAPPINGBEE_API_KEY")
SCRAPPINGBEE_URL = "https://app.scrapingbee.com/api/v1/"

PROPERTY_ID = "2626"
BOOKING_BASE_URL = "https://bookings247.com.au/booking2/booknow.php"


async def scrape_availability(check_in: str, check_out: str, nights: int = 1) -> dict:
    """
    Scrape Coal Creek's booking page for availability using calendar structure.
    """
    if not SCRAPPINGBEE_API_KEY:
        return {
            "success": False,
            "error": "SCRAPPINGBEE_API_KEY not found in environment"
        }

    booking_url = f"{BOOKING_BASE_URL}?property_id={PROPERTY_ID}&checkin={check_in}&checkout={check_out}&nights={nights}"

    try:
        params = {
            "api_key": SCRAPPINGBEE_API_KEY,
            "url": booking_url,
            "render_js": "true",
            "wait": "3000",
            "premium_proxy": "false",
            "country_code": "au",
            "device": "desktop"
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(SCRAPPINGBEE_URL, params=params)

        if response.status_code != 200:
            return {
                "success": False,
                "error": f"ScrapingBee returned {response.status_code}",
                "response_body": response.text[:500]
            }

        html_content = response.text
        availability = parse_calendar_availability(html_content)

        return {
            "success": True,
            "url": booking_url,
            "check_in": check_in,
            "check_out": check_out,
            "availability": availability,
            "scraping_metadata": {
                "timestamp": datetime.now().isoformat(),
                "response_size_bytes": len(response.content),
                "status_code": response.status_code
            }
        }
    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "Request timeout - ScrapingBee took too long to respond"
        }
    except Exception as e:
        logger.error(f"Scraping error: {e}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


def parse_calendar_availability(html: str) -> List[Dict[str, object]]:
    """
    Parse availability by checking if room booking panels exist.
    """
    soup = BeautifulSoup(html, "html.parser")

    room_panels = soup.find_all(
        "div",
        class_=lambda x: x and "b247-room-panel" in " ".join(x) if isinstance(x, list) else "b247-room-panel" in x if x else False
    )

    if len(room_panels) == 0:
        return [
            {"room_type": "Deluxe Spa Suite", "available": False, "price_per_night": 210},
            {"room_type": "Queen/Double", "available": False, "price_per_night": 135},
            {"room_type": "Twin Room", "available": False, "price_per_night": 160},
            {"room_type": "Family Suite", "available": False, "price_per_night": 190}
        ]

    rooms = []
    known_room_mapping = {
        "deluxe": ("Deluxe Spa Suite", 210),
        "queen": ("Queen/Double", 135),
        "twin": ("Twin Room", 160),
        "family": ("Family Suite", 190)
    }

    for panel in room_panels:
        room_name_elem = panel.find(
            "div",
            class_=lambda x: x and "room-name" in " ".join(x) if isinstance(x, list) else "room-name" in x if x else False
        )
        if not room_name_elem:
            continue

        room_link = room_name_elem.find("a")
        if room_link:
            room_name_text = room_link.get_text(strip=True)
        else:
            room_name_text = room_name_elem.get_text(strip=True)

        book_buttons = panel.find_all("input", {"value": "Book Now", "type": "button"})
        available = len(book_buttons) > 0

        price = None
        rate_input = panel.find("input", {"id": lambda x: x and "rate_string" in x if x else False})
        if rate_input and rate_input.get("value"):
            try:
                price = float(rate_input.get("value").split(',')[0])
            except (ValueError, IndexError):
                price = None

        if price is None:
            for key, (name, expected_price) in known_room_mapping.items():
                if key in room_name_text.lower():
                    price = expected_price
                    break

        rooms.append({
            "room_type": room_name_text,
            "available": available,
            "price_per_night": price
        })

    return rooms


async def check_multinight_availability(
    check_in_str: str,
    check_out_str: str,
    room_type: Optional[str] = None
) -> dict:
    """
    Check availability for EACH night in a multi-night stay.
    """
    check_in = datetime.strptime(check_in_str, "%Y-%m-%d")
    check_out = datetime.strptime(check_out_str, "%Y-%m-%d")
    nights = (check_out - check_in).days

    per_night_results = {}
    blocked_dates = []
    room_availability_tracker = {}

    for i in range(nights):
        night_date = check_in + timedelta(days=i)
        next_day = night_date + timedelta(days=1)

        night_str = night_date.strftime("%Y-%m-%d")
        next_str = next_day.strftime("%Y-%m-%d")

        result = await scrape_availability(night_str, next_str, nights=1)
        if not result.get("success"):
            return {
                "success": False,
                "error": f"Failed to check night {i + 1}: {result.get('error')}"
            }

        availability = result.get("availability", [])
        per_night_results[night_str] = availability

        if room_type:
            room_avail = any(
                r.get("room_type") == room_type and r.get("available")
                for r in availability
            )
            if not room_avail:
                blocked_dates.append(night_str)
        else:
            for room in availability:
                room_name = room.get("room_type")
                if room_name not in room_availability_tracker:
                    room_availability_tracker[room_name] = {"available_nights": 0, "total_nights": 0}

                room_availability_tracker[room_name]["total_nights"] += 1
                if room.get("available"):
                    room_availability_tracker[room_name]["available_nights"] += 1

            all_sold_out = all(not r.get("available") for r in availability)
            if all_sold_out:
                blocked_dates.append(night_str)

    available_all_nights_rooms = []

    if room_type:
        available_all_nights = len(blocked_dates) == 0
        if available_all_nights:
            available_all_nights_rooms = [room_type]
    else:
        for room_name, stats in room_availability_tracker.items():
            if stats["available_nights"] == stats["total_nights"]:
                available_all_nights_rooms.append(room_name)

        available_all_nights = len(available_all_nights_rooms) > 0

    return {
        "success": True,
        "check_in": check_in_str,
        "check_out": check_out_str,
        "total_nights": nights,
        "available_all_nights": available_all_nights,
        "blocked_dates": blocked_dates,
        "available_rooms": available_all_nights_rooms,
        "per_night_results": per_night_results,
        "room_availability_breakdown": room_availability_tracker if not room_type else None
    }
