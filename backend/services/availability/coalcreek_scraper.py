"""
Coal Creek Motel - Live Availability Scraper
==========================================
Production scraper using ScrapingBee for live availability.
"""

import os
import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SCRAPPINGBEE_API_KEY = os.getenv("SCRAPPINGBEE_API_KEY", "").strip() or None
SCRAPPINGBEE_URL = "https://app.scrapingbee.com/api/v1/"


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
        return value if value > 0 else default
    except ValueError:
        return default


# Free-tier safe defaults; can be raised in paid plans without code changes.
# Keep checks sequential by default to avoid burst-limit failures.
MAX_REQUESTS_PER_LOOKUP = _env_int("SCRAPPINGBEE_MAX_REQUESTS_PER_LOOKUP", 10)
CACHE_TTL_SECONDS = _env_int("SCRAPPINGBEE_CACHE_TTL_SECONDS", 300)

# Lightweight in-process cache to avoid duplicate hit bursts for same dates.
_SCRAPE_CACHE: Dict[tuple[str, str, int], tuple[float, dict]] = {}

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

    cache_key = (check_in, check_out, nights)
    now = time.time()
    cached = _SCRAPE_CACHE.get(cache_key)
    if cached and now - cached[0] <= CACHE_TTL_SECONDS:
        return cached[1]

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

        payload = {
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
        _SCRAPE_CACHE[cache_key] = (now, payload)
        return payload
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
            {"room_type": "Double Room", "available": False, "price_per_night": 135},
            {"room_type": "Twin Room", "available": False, "price_per_night": 160},
            {"room_type": "Family Suite", "available": False, "price_per_night": 190}
        ]

    rooms = []
    known_room_mapping = {
        "deluxe": ("Deluxe Spa Suite", 210),
        "queen": ("Double Room", 135),
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
    """Check availability for each night in a multi-night stay.

    Runs requests sequentially (one-by-one) to stay safe on free-tier limits
    and avoid concurrent request bursts.
    """
    check_in = datetime.strptime(check_in_str, "%Y-%m-%d")
    check_out = datetime.strptime(check_out_str, "%Y-%m-%d")
    nights = (check_out - check_in).days

    # Build per-night pairs for the full stay.
    night_pairs: list[tuple[str, str]] = []
    for i in range(nights):
        night_date = check_in + timedelta(days=i)
        next_day = night_date + timedelta(days=1)
        night_str = night_date.strftime("%Y-%m-%d")
        next_str = next_day.strftime("%Y-%m-%d")
        night_pairs.append((night_str, next_str))

    partial_scan = nights > MAX_REQUESTS_PER_LOOKUP
    pairs_to_check = night_pairs[:MAX_REQUESTS_PER_LOOKUP] if partial_scan else night_pairs
    checked_nights = [pair[0] for pair in pairs_to_check]
    skipped_nights = [pair[0] for pair in night_pairs[len(pairs_to_check):]]

    if partial_scan:
        logger.warning(
            "⚠️ Capping availability lookup: requested=%s nights, checking=%s nights (max_requests=%s)",
            nights,
            len(pairs_to_check),
            MAX_REQUESTS_PER_LOOKUP,
        )

    logger.info(
        "🚀 Running %s sequential scrape checks (requested=%s nights) for %s → %s",
        len(pairs_to_check),
        nights,
        check_in_str,
        check_out_str,
    )

    results = []
    for ci, co in pairs_to_check:
        try:
            results.append(await scrape_availability(ci, co, nights=1))
        except Exception as e:
            results.append(e)

    # Process results
    per_night_results = {}
    blocked_dates = []
    room_availability_tracker = {}

    for idx, (night_str, result) in enumerate(zip(checked_nights, results)):
        # Handle exceptions from individual tasks
        if isinstance(result, Exception):
            logger.error(f"Night {idx+1} ({night_str}) scrape exception: {result}")
            return {
                "success": False,
                "error": f"Failed to check night {idx + 1} ({night_str}): {str(result)}"
            }

        if not result.get("success"):
            return {
                "success": False,
                "error": f"Failed to check night {idx + 1}: {result.get('error')}"
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

    logger.info(f"✅ Sequential scrape complete: checked={len(checked_nights)} nights, blocked={blocked_dates}")
    return {
        "success": True,
        "check_in": check_in_str,
        "check_out": check_out_str,
        "total_nights": nights,
        "checked_nights": checked_nights,
        "skipped_nights": skipped_nights,
        "partial_scan": partial_scan,
        "scan_limit": MAX_REQUESTS_PER_LOOKUP,
        "available_all_nights": available_all_nights,
        "blocked_dates": blocked_dates,
        "available_rooms": available_all_nights_rooms,
        "per_night_results": per_night_results,
        "room_availability_breakdown": room_availability_tracker if not room_type else None
    }
