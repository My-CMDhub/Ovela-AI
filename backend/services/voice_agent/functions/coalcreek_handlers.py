"""
Coal Creek Motel Function Handlers
=================================
Booking request and information handlers for Coal Creek Motel.

Key Design:
- Uses "Read-Only + Soft Hold" strategy
- Fetches data from `services.motel_knowledge_base` with `tenant_id="coalcreek"`
- Directly implements specific handlers like `handle_create_booking_request`
"""

import logging
import time
import copy
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import asyncio
import re
from zoneinfo import ZoneInfo

# Import knowledge base services
from services.motel_knowledge_base import (
    get_room_pricing, get_room_details, recommend_room,
    get_check_in_out_info, get_location_info, get_amenities,
    get_activities_nearby, search_motel_info, get_policies,
    set_tenant_context
)
from services.knowledge_base.coalcreek import COALCREEK_DATA

logger = logging.getLogger(__name__)

MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _today_melbourne_date():
    return datetime.now(MELBOURNE_TZ).date()


# Common STT mishearings for email domains
_EMAIL_DOMAIN_FIXES = [
    (r'g[\s\-]?mail', 'gmail'),
    (r'hot[\s\-]?mail', 'hotmail'),
    (r'ya[\s\-]?hoo', 'yahoo'),
    (r'out[\s\-]?look', 'outlook'),
    (r'i[\s\-]?cloud', 'icloud'),
    (r'google[\s\-]?mail', 'gmail'),
    (r'live[\s\-]?com', 'live.com'),
    (r'proton[\s\-]?mail', 'protonmail'),
    (r'big[\s\-]?pond', 'bigpond'),
    (r'i[\s\-]?inet', 'iinet'),
]

# Known domain names used to strip STT garbage prefix (e.g. "therategmail" → "gmail")
_KNOWN_DOMAIN_NAMES = [
    'gmail', 'hotmail', 'yahoo', 'outlook', 'icloud', 'protonmail',
    'live', 'bigpond', 'iinet', 'me', 'mac',
]


def _normalize_email(raw: str, guest_name: str = "") -> str:
    """Normalize STT-garbled email addresses.

    Handles patterns like:
      - 'james at g mail dot com'       → 'james@gmail.com'
      - 'my name at gmail dot com'      → 'jameslewis@gmail.com'  (if guest_name given)
      - 'JamesLewis at therategmail.com'→ 'jameslewis@gmail.com'  (garbage prefix stripped)
    Pure regex/string — zero network cost.
    """
    if not raw:
        return raw

    text = raw.strip().lower()

    # Replace spoken separators
    text = re.sub(r'\bat\s+sign\b', '@', text)
    text = re.sub(r'\bat\b', '@', text)
    text = re.sub(r'\bdot\b', '.', text)
    text = re.sub(r'\bperiod\b', '.', text)
    text = re.sub(r'\bdash\b', '-', text)
    text = re.sub(r'\bunderscore\b', '_', text)
    text = re.sub(r'\bhyphen\b', '-', text)

    # Fix domain mishearings (before space removal so patterns match)
    for pattern, replacement in _EMAIL_DOMAIN_FIXES:
        text = re.sub(pattern, replacement, text)

    # Strip spaces around the @ and dots (e.g. 'james @ gmail . com')
    text = re.sub(r'\s*@\s*', '@', text)
    text = re.sub(r'\s*\.\s*', '.', text)

    # Remove any remaining internal spaces
    if '@' in text:
        local, _, domain = text.partition('@')
        local = local.replace(' ', '')
        domain = domain.replace(' ', '')

        # Resolve "my name" / "myname" in local part to the actual confirmed guest name
        _MY_NAME_VARIANTS = {'myname', 'myfullname', 'myname', 'firstname', 'lastname'}
        if guest_name and local in _MY_NAME_VARIANTS:
            local = re.sub(r'\s+', '', guest_name.lower())

        # Strip STT-inserted garbage prefix before a known domain
        # e.g. "therategmail.com" → "gmail.com", "therating.yahoo.com" → "yahoo.com"
        for known in _KNOWN_DOMAIN_NAMES:
            m = re.match(rf'^.+?({re.escape(known)}\..+)$', domain)
            if m:
                domain = m.group(1)
                break

        text = local + '@' + domain
    else:
        text = text.replace(' ', '')

    return text


def _parse_iso_date(value: str):
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except Exception:
        return None


def _next_weekday(base_date, target_weekday: int, include_today: bool = False):
    delta_days = (target_weekday - base_date.weekday()) % 7
    if delta_days == 0 and not include_today:
        delta_days = 7
    return base_date + timedelta(days=delta_days)


def _resolve_relative_dates(check_in_raw: str, check_out_raw: str, user_utterance: str):
    """
    Resolve indirect date expressions deterministically.

    Supported patterns:
    - upcoming / next / this weekend
    - upcoming / next / this <weekday>
    - after N days / in N days
    - today / tomorrow / day after tomorrow
    - ISO dates (YYYY-MM-DD)
    """
    today = _today_melbourne_date()
    text = f"{check_in_raw or ''} {check_out_raw or ''} {user_utterance or ''}".lower().strip()

    resolved_check_in = _parse_iso_date(check_in_raw)
    resolved_check_out = _parse_iso_date(check_out_raw)

    # Weekend phrases: Saturday check-in, Sunday check-out (AU motel convention)
    if re.search(r"\b(upcoming|next|this)\s+weekend\b", text) or re.search(r"\bupcoming\s+weekand\b", text):
        saturday = _next_weekday(today, 5, include_today=False)
        sunday = saturday + timedelta(days=1)
        return saturday, sunday, "weekend_phrase"

    # upcoming/next/this weekday
    weekday_match = re.search(r"\b(upcoming|next|this)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", text)
    if weekday_match:
        qualifier = weekday_match.group(1)
        weekday_word = weekday_match.group(2)
        target = WEEKDAY_INDEX[weekday_word]
        include_today = qualifier == "this"
        target_date = _next_weekday(today, target, include_today=include_today)
        if qualifier in {"upcoming", "next"} and target_date <= today:
            target_date = target_date + timedelta(days=7)
        return target_date, target_date + timedelta(days=1), "weekday_phrase"

    # after/in N days
    days_match = re.search(r"\b(?:after|in)\s+(\d{1,3})\s+days?\b", text)
    if days_match:
        day_count = int(days_match.group(1))
        target_date = today + timedelta(days=day_count)
        return target_date, target_date + timedelta(days=1), "relative_days"

    if re.search(r"\bday\s+after\s+tomorrow\b", text):
        target_date = today + timedelta(days=2)
        return target_date, target_date + timedelta(days=1), "day_after_tomorrow"

    if re.search(r"\btomorrow\b", text):
        target_date = today + timedelta(days=1)
        return target_date, target_date + timedelta(days=1), "tomorrow"

    if re.search(r"\btoday\b", text):
        return today, today + timedelta(days=1), "today"

    if resolved_check_in:
        if not resolved_check_out or resolved_check_out <= resolved_check_in:
            resolved_check_out = resolved_check_in + timedelta(days=1)
        return resolved_check_in, resolved_check_out, "iso"

    return None, None, "unresolved"


# =============================================================================
# BOOKING HANDLERS (Read-Only + Soft Hold)
# =============================================================================

async def handle_check_availability(args: dict, db_service, context: dict | None = None) -> dict:
    """
    Check room availability using real-time scraping.
    
    Features:
    - Multi-night validation (checks EACH night)
    - Efficient data handling (minimal context)
    - Dead air prevention compatible (function designed for 3-10s latency)
    
    Returns compact result for AI to parse quickly.
    """
    # Ensure KB knows we are acting as Coal Creek
    set_tenant_context("coalcreek")
    
    check_in = args.get("check_in_date", "")
    check_out = args.get("check_out_date", "")
    user_utterance = args.get("_user_utterance", "")
    room_type_arg = args.get("room_type", "any")
    
    if not check_in and not user_utterance:
        return {
            "available": False, 
            "verified": False, 
            "message": "Please provide check-in date",
            "ai_should_say": "What date were you looking to check in?"
        }

    # 1. Deterministic date resolution (relative phrases + strict calendar validity)
    check_in_date, check_out_date, resolution_source = _resolve_relative_dates(check_in, check_out, user_utterance)

    if not check_in_date:
        return {
            "available": False,
            "verified": False,
            "message": "Invalid or unresolved date",
            "ai_should_say": "I didn't catch the date properly. Could you repeat that in month-day format?"
        }

    if check_in_date < _today_melbourne_date():
        return {
            "available": False,
            "verified": True,
            "message": "Date in the past",
            "ai_should_say": "That date has already passed. What dates were you looking at?"
        }

    if not check_out_date or check_out_date <= check_in_date:
        check_out_date = check_in_date + timedelta(days=1)

    check_in = check_in_date.strftime("%Y-%m-%d")
    check_out = check_out_date.strftime("%Y-%m-%d")
    nights = (check_out_date - check_in_date).days

    logger.info(f"📅 Date resolved: source={resolution_source}, check_in={check_in}, check_out={check_out}")
    
    # 2. Map room type to scraper format
    room_map = {
        "queen": "Queen/Double",
        "standard": "Queen/Double",
        "twin": "Twin Room",
        "family": "Family Suite",
        "suite": "Deluxe Spa Suite",
        "spa": "Deluxe Spa Suite",
        "deluxe": "Deluxe Spa Suite",
        "any": None  # Check all rooms
    }
    
    search_key = room_type_arg.lower()
    target_room = room_map.get(search_key)

    availability_cache = (context or {}).get("availability_cache") if context else None
    cache_key = f"{check_in}|{check_out}|{target_room or 'any'}"
    if isinstance(availability_cache, dict) and cache_key in availability_cache:
        logger.info("♻️ Session availability cache hit: %s", cache_key)
        return copy.deepcopy(availability_cache[cache_key])
    
    # 3. Call multi-night scraper with RETRY LOGIC
    # FORCE room_type=None to scrape ALL rooms (more efficient, same API cost)
    scrape_target = None 
    
    try:
        # Import the production scraper
        from services.availability.coalcreek_scraper import check_multinight_availability
        
        logger.info(f"🔍 Checking availability: {check_in} to {check_out} ({nights} nights), target={target_room or 'any'}")
        
        result = None
        MAX_RETRIES = 2
        
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Call the scraper
                result = await check_multinight_availability(
                    check_in_str=check_in,
                    check_out_str=check_out,
                    room_type=scrape_target  # ALWAYS scrape all rooms
                )
                
                if result.get("success"):
                    logger.info(f"✅ Scraping success on attempt {attempt}")
                    break
                else:
                    logger.warning(f"⚠️ Scraping attempt {attempt} failed: {result.get('error')}")
                    
            except Exception as scrape_err:
                logger.error(f"⚠️ Scraping exception on attempt {attempt}: {scrape_err}")
                result = {"success": False, "error": str(scrape_err)}
            
            # Small delay before retry if not last attempt
            if attempt < MAX_RETRIES:
                await asyncio.sleep(1.0)
        
        # Check final result
        if not result or not result.get("success"):
            # Scraping failed after retries - TRANSPARENT FALLBACK
            logger.error(f"❌ All scraping attempts failed. Triggering fallback.")
            payload = {
                "available": "unknown",
                "verified": False,
                "message": "Technical issue accessing live calendar",
                "ai_should_say": "Sorry, I couldn't complete the live calendar check just now. If you want, I can put you through to reception."
            }
            if isinstance(availability_cache, dict):
                availability_cache[cache_key] = copy.deepcopy(payload)
            return payload

        if result.get("partial_scan"):
            checked = result.get("checked_nights", [])
            skipped = result.get("skipped_nights", [])
            checked_range = f"{checked[0]} to {checked[-1]}" if checked else check_in
            payload = {
                "available": "unknown",
                "verified": False,
                "message": "Live calendar check was rate-limited",
                "scan_limited": True,
                "checked_nights": checked,
                "skipped_nights": skipped,
                "ai_should_say": f"I can run up to ten nights per live check right now, and I verified {checked_range}. If you want, I can put you through to reception for the full span.",
            }
            if isinstance(availability_cache, dict):
                availability_cache[cache_key] = copy.deepcopy(payload)
            return payload
        
        # 4. Parse result efficiently
        available_all_nights = result.get("available_all_nights", False)
        blocked_dates = result.get("blocked_dates", [])
        available_rooms = result.get("available_rooms", [])
        
        # 5. Build compact AI response
        if available_all_nights and target_room:
            # Specific room is available
            # Get pricing from first night
            first_night_data = result.get("per_night_results", {})
            first_date = list(first_night_data.keys())[0] if first_night_data else None
            price = None
            
            if first_date:
                for room in first_night_data[first_date]:
                    if room.get("room_type") == target_room:
                        price = room.get("price_per_night")
                        break
            
            payload = {
                "available": True,
                "verified": True,
                "room_type": target_room,
                "check_in": check_in,
                "check_out": check_out,
                "nights": nights,
                "price_per_night": price,
                "total": price * nights if price else None,
                "ai_should_say": f"Great news! The {target_room} is available for {check_in if nights == 1 else f'{nights} nights from {check_in}'}. The rate is ${price} per night{f', total ${price * nights}' if nights > 1 else ''}. Would you like me to place a hold?"
            }
            if isinstance(availability_cache, dict):
                availability_cache[cache_key] = copy.deepcopy(payload)
            return payload
            
        elif available_all_nights and not target_room:
            # Guest asked for "any" room - show what's available
            prices = {}
            first_night_data = result.get("per_night_results", {})
            first_date = list(first_night_data.keys())[0] if first_night_data else None
            
            if first_date:
                for room in first_night_data[first_date]:
                    room_name = room.get("room_type")
                    if room_name in available_rooms:
                        prices[room_name] = room.get("price_per_night")
            
            room_list = ", ".join([f"{r} (${prices.get(r)}/night)" for r in available_rooms if r in prices])
            
            payload = {
                "available": True,
                "verified": True,
                "available_rooms": available_rooms,
                "check_in": check_in,
                "check_out": check_out,
                "nights": nights,
                "rooms_with_pricing": prices,
                "ai_should_say": f"I have {len(available_rooms)} room types available for those dates: {room_list}. Which would you prefer?"
            }
            if isinstance(availability_cache, dict):
                availability_cache[cache_key] = copy.deepcopy(payload)
            return payload
            
        else:
            # NOT available - explain why
            if target_room:
                # Specific room requested but blocked
                blocked_str = ", ".join(blocked_dates)
                payload = {
                    "available": False,
                    "verified": True,
                    "room_type": target_room,
                    "blocked_dates": blocked_dates,
                    "check_in": check_in,
                    "check_out": check_out,
                    "nights": nights,
                    "ai_should_say": f"I'm sorry, the {target_room} isn't available for all {nights} night{'s' if nights > 1 else ''} - it's sold out on {blocked_str}. However, I have other room types available. Would you like to hear those options?"
                }
                if isinstance(availability_cache, dict):
                    availability_cache[cache_key] = copy.deepcopy(payload)
                return payload
            else:
                # All rooms sold out
                blocked_str = ", ".join(blocked_dates)
                payload = {
                    "available": False,
                    "verified": True,
                    "blocked_dates": blocked_dates,
                    "check_in": check_in,
                    "check_out": check_out,
                    "nights": nights,
                    "ai_should_say": f"I'm sorry, we're fully booked on {blocked_str}. Would you like to check different dates, or can I have someone call you if we get a cancellation?"
                }
                if isinstance(availability_cache, dict):
                    availability_cache[cache_key] = copy.deepcopy(payload)
                return payload
        
    except Exception as e:
        logger.error(f"Availability check error: {e}", exc_info=True)
        payload = {
            "available": "unknown",
            "verified": False,
            "error": str(e),
            "ai_should_say": "Sorry, I couldn't complete the live calendar check. If you'd like, I can put you through to reception."
        }
        if isinstance(availability_cache, dict):
            availability_cache[cache_key] = copy.deepcopy(payload)
        return payload


async def handle_create_booking_request(args: dict, user_phone: str, save_reservation_fn) -> dict:
    """
    Create a SOFT HOLD booking request.
    Status: pending_confirmation
    """
    guest_name = args.get("guest_name", "")
    check_in = args.get("check_in_date", "")
    check_out = args.get("check_out_date", "")
    user_utterance = args.get("_user_utterance", "")
    room_type = args.get("room_type", "queen")
    num_guests = args.get("num_guests", 1)
    guest_email = _normalize_email(args.get("guest_email", ""), guest_name)
    notes = args.get("notes", "")

    guest_phone = args.get("guest_phone", "") or user_phone

    if not guest_name:
        return {
            "success": False,
            "message": "I need your name and check-in date to place the hold."
        }

    check_in_date, check_out_date, resolution_source = _resolve_relative_dates(check_in, check_out, user_utterance)
    if not check_in_date:
        return {
            "success": False,
            "message": "I need a valid check-in date to place the hold."
        }

    if not check_out_date or check_out_date <= check_in_date:
        check_out_date = check_in_date + timedelta(days=1)

    check_in = check_in_date.strftime("%Y-%m-%d")
    check_out = check_out_date.strftime("%Y-%m-%d")
    num_nights = max(1, (check_out_date - check_in_date).days)

    logger.info(f"📅 Booking date resolved: source={resolution_source}, check_in={check_in}, check_out={check_out}")
            
    # Get pricing (Approximate for hold)
    rooms_data = COALCREEK_DATA["rooms"]
    # fuzzy match logic again
    search_key = room_type.lower().split()[0]
    key_map = {"queen": "queen", "standard": "queen", "twin": "twin", "family": "family", "spa": "spa", "deluxe": "spa"}
    final_key = key_map.get(search_key, "queen")
    room_data = rooms_data.get(final_key, rooms_data["queen"])
    
    rate = room_data["price"]
    total = rate * num_nights
    
    # Booking Ref
    booking_ref = f"CC-{int(time.time()) % 100000:05d}"
    now = datetime.now().isoformat()
    
    reservation_data = {
        "guest_name": guest_name,
        "guest_phone": guest_phone,
        "guest_email": guest_email,
        "num_guests": num_guests,
        "room_type": room_data["name"],
        "check_in_date": check_in,
        "check_out_date": check_out,
        "num_nights": num_nights,
        "rate_per_night": rate,
        "total_amount": total,
        "status": "pending", # Explicit Soft Hold status
        "source": "voice_ai_soft_hold",
        "booking_reference": booking_ref,
        "notes": notes or "Soft Hold Request via AI",
        "created_at": now,
        "updated_at": now,
        "created_by": "ovela_ai",
        "tenant_id": "coalcreek"
    }
    
    try:
        # Save to DB (if saving function provided)
        if save_reservation_fn:
            await save_reservation_fn(reservation_data)
        
        # Trigger staff notification
        try:
            from services.staff_notifications import staff_notification_service
            asyncio.create_task(
                staff_notification_service.notify_new_booking_request(
                    guest_name=guest_name,
                    guest_phone=guest_phone,
                    guest_email=guest_email,
                    check_in=check_in,
                    check_out=check_out,
                    room_type=room_data["name"],
                    total_amount=total,
                    booking_reference=booking_ref,
                    num_nights=num_nights,
                )
            )
        except Exception as notify_err:
            logger.error(f"Failed to send staff notification: {notify_err}")
            
        return {
            "success": True,
            "booking_reference": booking_ref,
            "guest_name": guest_name,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "room_type": room_data["name"],
            "total_amount": total,
            "message": f"I've placed a temporary hold and sent this to the team. They'll email you a payment link shortly to confirm."
        }

    except Exception as e:
        logger.error(f"Soft hold creation error: {e}")
        return {
            "success": False,
            "message": "System error. Please contact reception."
        }


# =============================================================================
# LOOKUP BOOKING HANDLER
# =============================================================================

def _normalize_reference(raw: str) -> str:
    """
    Normalize STT-garbled booking references.
    'CC76818' → 'CC-76818', 'cc 7 6 8 1 8' → 'CC-76818', 'cc-76818' → 'CC-76818'
    """
    r = re.sub(r'\s+', '', raw).upper().replace('-', '')
    m = re.match(r'^([A-Z]+)(\d+)$', r)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return r


async def handle_lookup_booking(args: dict, db_service, user_phone: str) -> dict:
    """
    Phone-first booking lookup — like a receptionist who can see caller's record
    the moment they call.

    Strategy:
      Step 0: Always silently try caller's own Twilio phone number first.
              If found → return booking info with found_by="caller_phone".
              AI should then CONFIRM ("I found a booking under X for Y. Is that yours?")
              rather than interrogate.
      Step 1: If reference provided → normalize + lookup (handles STT garbling
              like 'CC 7 6 8 1 8' or 'CC76818' → 'CC-76818').
      Step 2: If guest_name + explicit phone provided (different caller) → lookup.
      Step 3: Name-only search.
      Step 4: Email (last resort, STT-fragile).
    """
    from services.voice_agent.text_utils import normalize_phone_number

    guest_name = (args.get("guest_name") or "").strip()
    raw_ref    = (args.get("reference")  or "").strip()
    raw_phone  = (args.get("phone")      or "").strip()
    email      = (args.get("email")      or "").strip().lower()

    reference = _normalize_reference(raw_ref) if raw_ref else ""

    # Normalize any explicitly provided phone
    phone = None
    if raw_phone:
        try:
            phone = normalize_phone_number(raw_phone)
        except Exception:
            phone = raw_phone

    # Always have caller_phone from Twilio (most reliable key)
    caller_phone = None
    try:
        caller_phone = normalize_phone_number(user_phone) if user_phone else None
    except Exception:
        caller_phone = user_phone

    def _booking_detail_tail(doc: dict) -> str:
        details = []
        if doc.get("check_in_date"):
            details.append(f"checking in on {doc['check_in_date']}")
        if doc.get("room_type"):
            details.append(f"for the {doc['room_type']}")
        return " ".join(details)

    def _build_confirmation_prompt(result: dict, found_by: str, name_mismatch: bool = False) -> str:
        guest = result.get("guest_name") or "that guest"
        details = _booking_detail_tail(result)
        if found_by == "caller_phone":
            opener = f"I found a booking on this number under {guest}"
        elif found_by == "phone":
            opener = f"I found a booking on that number under {guest}"
        elif found_by == "reference" and result.get("booking_reference"):
            opener = f"I found booking {result['booking_reference']} under {guest}"
        else:
            opener = f"I found a booking under {guest}"

        if details:
            opener = f"{opener} {details}"

        if name_mismatch:
            return f"{opener} - is that the one?"
        return f"{opener} - is that yours?"

    def _format_doc(doc, total_docs, found_by: str = "", name_mismatch: bool = False):
        result = {
            "found":             True,
            "booking_reference": doc.get("booking_reference", ""),
            "guest_name":        doc.get("guest_name", ""),
            "room_type":         doc.get("room_type", ""),
            "check_in_date":     doc.get("check_in_date", ""),
            "check_out_date":    doc.get("check_out_date", ""),
            "num_nights":        doc.get("num_nights", ""),
            "status":            doc.get("status", ""),
            "total_amount":      doc.get("total_amount", ""),
            "other_bookings":    total_docs - 1,
        }
        if found_by:
            result["found_by"] = found_by
        if name_mismatch:
            result["name_mismatch"] = True
        result["lookup_confidence"] = "high" if found_by in {"caller_phone", "reference"} and not name_mismatch else "medium"
        result["confirmation_prompt"] = _build_confirmation_prompt(result, found_by, name_mismatch=name_mismatch)
        result["message"] = result["confirmation_prompt"]
        return result

    def _name_matches(doc, name: str) -> bool:
        n = name.lower()
        db_name = doc.get("guest_name", "").lower()
        return n in db_name or db_name in n

    try:
        # ── Step 0: Caller's own phone (Twilio) — always try first ──────────
        if caller_phone:
            docs = await db_service.lookup_motel_reservation(
                phone=caller_phone,
                tenant_id="coalcreek"
            )
            if docs:
                if guest_name:
                    matched = [d for d in docs if _name_matches(d, guest_name)]
                    if matched:
                        return _format_doc(matched[0], len(matched), found_by="caller_phone")
                    # Phone matched but name differs — still return; flag for AI to clarify
                    return _format_doc(docs[0], len(docs), found_by="caller_phone", name_mismatch=True)
                # No name given — return booking, let AI confirm with user
                return _format_doc(docs[0], len(docs), found_by="caller_phone")

        # ── Step 1: Reference lookup (normalized) ───────────────────────────
        if reference:
            docs = await db_service.lookup_motel_reservation(
                booking_reference=reference,
                tenant_id="coalcreek"
            )
            if docs:
                if guest_name:
                    match = next((d for d in docs if _name_matches(d, guest_name)), None)
                    if match:
                        return _format_doc(match, 1, found_by="reference")
                    return _format_doc(docs[0], len(docs), found_by="reference", name_mismatch=True)
                return _format_doc(docs[0], len(docs), found_by="reference")

        # ── Step 2: Explicit (different) phone + name ───────────────────────
        if phone and phone != caller_phone:
            docs = await db_service.lookup_motel_reservation(
                phone=phone,
                tenant_id="coalcreek"
            )
            if docs:
                if guest_name:
                    matched = [d for d in docs if _name_matches(d, guest_name)]
                    if matched:
                        return _format_doc(matched[0], len(matched), found_by="phone")
                return _format_doc(docs[0], len(docs), found_by="phone")

        # ── Step 3: Name-only search ─────────────────────────────────────────
        if guest_name:
            docs = await db_service.lookup_motel_reservation(
                guest_name=guest_name,
                tenant_id="coalcreek"
            )
            if docs:
                return _format_doc(docs[0], len(docs), found_by="name")

        # ── Step 4: Email (last resort) ───────────────────────────────────────
        if email:
            docs = await db_service.lookup_motel_reservation(
                email=email,
                tenant_id="coalcreek"
            )
            if docs:
                if guest_name:
                    matched = [d for d in docs if _name_matches(d, guest_name)]
                    if matched:
                        return _format_doc(matched[0], len(matched), found_by="email")
                return _format_doc(docs[0], len(docs), found_by="email")

        # ── Nothing found ────────────────────────────────────────────────────
        return {
            "found": False,
            "message": "I couldn't find a booking linked to your number or the details I have here - want me to put you through to reception?"
        }

    except Exception as e:
        logger.error(f"lookup_booking error: {e}")
        return {
            "found": False,
            "error": True,
            "message": "I'm having trouble accessing the booking system right now. Let me connect you to reception.",
            "should_transfer": True
        }




# =============================================================================
# HUMAN & UTILITY HANDLERS
# =============================================================================

async def handle_report_missing_booking(args: dict, user_phone: str) -> dict:
    """Report a missing booking to staff."""
    from services.staff_notifications import staff_notification_service
    from services.voice_agent.text_utils import normalize_phone_number
    
    name = args.get("guest_name", "Unknown")
    source = args.get("booking_source", "unknown")
    check_in = args.get("expected_check_in", "Unknown")
    contact_phone = args.get("contact_phone", "") or user_phone
    
    try:
        contact_phone = normalize_phone_number(contact_phone)
    except:
        pass # Ignore errors if utils fail
    
    reason = f"MISSING BOOKING: Guest claims {source} booking. Check-in: {check_in}"
    
    await staff_notification_service.notify_new_callback_request(
        customer_phone=contact_phone,
        customer_name=name,
        reason=reason,
        urgency="high"
    )
    
    return {
        "success": True,
        "message": "I've sent an urgent report to the team. They will checks the records and call you back shortly."
    }

async def handle_request_human_callback(args: dict, user_phone: str) -> dict:
    """Request a human callback."""
    from services.staff_notifications import staff_notification_service
    from services.voice_agent.text_utils import normalize_phone_number
    
    customer_name = args.get("customer_name", "Unknown")
    customer_phone = args.get("customer_phone", "") or user_phone
    reason = args.get("reason", "Inquiry")
    
    try:
        customer_phone = normalize_phone_number(customer_phone)
    except:
        pass
        
    await staff_notification_service.notify_new_callback_request(
        customer_phone=customer_phone,
        customer_name=customer_name,
        reason=reason,
        urgency="medium"
    )
    
    return {
        "success": True,
        "message": "I've passed your details to reception. They'll give you a call back soon."
    }


async def handle_update_guest_info(args: dict, db_service) -> dict:
    """
    Save guest details to CRM for persistent memory.
    Call this when guest verifies their info.
    """
    guest_name = args.get("guest_name", "")
    guest_phone = args.get("guest_phone", "")
    guest_email = args.get("guest_email", "")
    
    logger.info(f"Captured Guest Info: {guest_name} - {guest_phone}")
    
    if db_service and hasattr(db_service, "upsert_motel_guest"):
        try:
            # Save as 'inquiry' since they haven't booked yet (just memory)
            # If they book later, the booking logic should upgrade this or we can add a 'create_booking' hook.
            # But upsert is safe.
            db_service.upsert_motel_guest(
                guest_name=guest_name, 
                guest_phone=guest_phone, 
                guest_email=guest_email,
                tenant_id="coalcreek",
                status="inquiry"
            )
            message = "Details securely saved to guest profile."
        except Exception as e:
            logger.error(f"Failed to save guest info: {e}")
            message = "Details captured."
    else:
        message = "Details captured (temporary)."
        
    return {"success": True, "message": message}


# =============================================================================
# COAL CREEK DISPATCHER
# =============================================================================

class CoalCreekFunctionDispatcher:
    """
    Dispatches Coal Creek specific function calls.
    Ensures 'coalcreek' context is set for all KB operations.
    """
    
    def __init__(self, db_service, user_phone: str, save_reservation_fn, abuse_protection, caller_memory_bank=None, call_sid: str = ""):
        self.db_service = db_service
        self.user_phone = user_phone
        self.save_reservation_fn = save_reservation_fn
        self.abuse_protection = abuse_protection
        self.caller_memory_bank = caller_memory_bank  # CallerMemoryBank for persistent profile saves
        self.call_sid = call_sid  # Twilio CallSid for ADK session keying
        # Always set context on init
        set_tenant_context("coalcreek")

    def fire_adk_cold_path(self, query: str, session_state: dict | None = None) -> None:
        """
        Fire-and-forget: POST a booking intent to the ADK Cold Path graph.

        Schedules as a background asyncio.create_task so it NEVER blocks the
        voice loop. The ADK graph (OvelaManager → BookingWorker/InfoWorker)
        processes the query asynchronously and stores the result in the
        per-call InMemory session.

        Args:
            query:         User's booking intent text to route through ADK.
            session_state: Optional caller context (name, dates) to merge into
                           the ADK session before routing.
        """
        import asyncio
        import httpx

        call_sid = self.call_sid or "unknown"

        async def _post():
            try:
                payload = {
                    "call_sid": call_sid,
                    "query": query,
                    "session_state": session_state or {},
                }
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        "http://localhost:8000/api/adk/query",
                        json=payload,
                    )
                if resp.status_code == 200:
                    data = resp.json()
                    logger.info(
                        "🤖 ADK cold path OK for %s | response_len=%d",
                        call_sid[:8],
                        len(data.get("response", "")),
                    )
                else:
                    logger.warning(
                        "🤖 ADK cold path non-200 for %s: %d",
                        call_sid[:8],
                        resp.status_code,
                    )
            except Exception as exc:
                # Silently swallow — cold path must NEVER crash the voice loop
                logger.error("🤖 ADK cold path error for %s: %s", call_sid[:8], exc)

        try:
            asyncio.create_task(_post())
        except RuntimeError:
            # No running loop (e.g., test context) — silently skip
            logger.debug("🤖 ADK cold path skipped (no event loop)")

    
    async def execute(self, function_name: str, args: dict, context: dict = None) -> dict:
        """Execute a function with basic error handling."""
        import asyncio
        
        # Dynamic timeout: scale with nights for availability checks.
        # Parallel scraping completes in ~10s, but we add headroom.
        TIMEOUT = 18.0
        if function_name == "check_availability":
            try:
                ci = args.get("check_in_date", "")
                co = args.get("check_out_date", "")
                if ci and co:
                    from datetime import datetime as dt
                    nights = max(1, (dt.strptime(co, "%Y-%m-%d") - dt.strptime(ci, "%Y-%m-%d")).days)
                    # Parallel: base 15s + 3s per extra night (safety margin)
                    TIMEOUT = max(18.0, 15.0 + nights * 3.0)
                    logger.info(f"⏱️ Dynamic timeout for {nights}-night check: {TIMEOUT}s")
            except Exception:
                pass
        
        # Refresh context just in case
        set_tenant_context("coalcreek")
        
        try:
             result = await asyncio.wait_for(
                self._dispatch(function_name, args, context),
                timeout=TIMEOUT
             )
             return result
        except asyncio.TimeoutError:
             logger.error(f"Function {function_name} timed out after {TIMEOUT}s")
             # For availability checks, return "unknown" and let AI transparently
             # explain the issue, then ask if user wants transfer.
             if function_name == "check_availability":
                 return {
                     "available": "unknown",
                     "verified": False,
                     "message": "Live calendar timed out",
                     "ai_should_say": "Sorry, the live calendar took too long to respond. I can try a shorter date range now, or if you prefer I can put you through to reception."
                 }
             return {"success": False, "message": "I'm having a connection issue. One moment."}
        except Exception as e:
             logger.error(f"Function error {function_name}: {e}")
             return {"error": str(e), "message": "I encountered a system error."}

    async def _dispatch(self, function_name: str, args: dict, context: dict = None) -> dict:
        """Internal dispatch map."""

        # Booking / Availability
        if function_name == "check_availability":
            return await handle_check_availability(args, self.db_service, context=context)

        elif function_name == "create_booking_request":
            result = await handle_create_booking_request(args, self.user_phone, self.save_reservation_fn)
            # Cold Path: notify ADK graph of successful booking intent for session memory
            if result.get("success") and self.call_sid:
                guest_name = args.get("guest_name", "")
                room_type = args.get("room_type", "")
                check_in = args.get("check_in_date", "")
                adk_query = f"Booking confirmed for {guest_name}: {room_type} room, check-in {check_in}."
                session_state = {
                    "guest_name": guest_name,
                    "room_type": room_type,
                    "check_in": check_in,
                    "booking_ref": result.get("booking_reference", ""),
                }
                self.fire_adk_cold_path(query=adk_query, session_state=session_state)
            return result
            
        elif function_name == "lookup_booking":
            return await handle_lookup_booking(args, self.db_service, self.user_phone)
        
        # Knowledge Base (Direct calls to motel_knowledge_base service)
        elif function_name == "get_room_pricing":
             return get_room_pricing(args.get("room_type"))
             
        elif function_name == "get_room_details":
             return get_room_details(args.get("room_type", "queen"))
             
        elif function_name == "recommend_room":
             return recommend_room(args.get("num_guests", 2), args.get("needs_accessibility", False))
             
        elif function_name == "get_check_in_out_info":
             return get_check_in_out_info()
             
        elif function_name == "get_location_info":
             return get_location_info(args.get("detail"))
             
        elif function_name == "get_amenities":
             return get_amenities(args.get("category"))
             
        elif function_name == "get_activities_nearby":
             return get_activities_nearby()
             
        elif function_name == "search_motel_info":
             return search_motel_info(args.get("query", ""))
             
        elif function_name == "get_policies":
             return get_policies(args.get("policy_type"))
             
        # Human / Reporting
        elif function_name == "request_human_callback":
             return await handle_request_human_callback(args, self.user_phone)
             
        elif function_name == "report_missing_booking":
             return await handle_report_missing_booking(args, self.user_phone)
             
        elif function_name == "update_guest_info":
             result = await handle_update_guest_info(args, self.db_service)
             # Persist profile to CallerMemoryBank on successful guest info capture
             if result.get("success") and self.caller_memory_bank:
                 profile_data = {}
                 if args.get("guest_name"):
                     profile_data["name"] = args["guest_name"]
                 if args.get("guest_email"):
                     profile_data["email"] = args["guest_email"]
                 if profile_data:
                     # Fire-and-forget: never await on the hot path
                     asyncio.create_task(
                         self.caller_memory_bank.save_profile(self.user_phone, profile_data)
                     )
             return result
             
        # Common controls
        elif function_name == "end_call":
             return {
                "action": "end_call",
                "success": True,
                "message": args.get("message", ""),
                "user_utterance": args.get("_user_utterance", ""),
            }
             
        elif function_name == "transfer_to_staff":
             from core.config import settings
             return {
                "action": "transfer",
                "transfer_to": settings.STAFF_PHONE_NUMBER,
                "message": "Sure, I'll transfer you to reception now."
            }

        elif function_name == "wait_on_request":
             wait_seconds = args.get("wait_seconds", 90)
             try:
                 wait_seconds = int(wait_seconds)
             except Exception:
                 wait_seconds = 90
             wait_seconds = max(30, min(wait_seconds, 120))
             return {
                "action": "wait_on_request",
                "duration_seconds": wait_seconds,
                "reason": args.get("reason", ""),
                "message": "No worries, take your time. I'll stay on the line."
            }
            
        elif function_name == "report_user_behavior":
             if self.abuse_protection:
                 category = args.get("category", "off_topic")
                 reason = args.get("reason", "unspecified")
                 return self.abuse_protection.report_violation(category, reason)
             return {"message": "Please continue."}
        
        else:
             return {"error": f"Unknown function: {function_name}"}
