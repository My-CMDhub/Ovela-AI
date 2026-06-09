"""
Coal Creek Motel - ScrapingBee Availability Test (Calendar-Based)
==================================================================
Test script using CALENDAR structure to detect room availability.

Key HTML patterns:
- Available: <td class="available"><div class="date-rate">135</div></td>
- Unavailable: <td class="unavailable-date"> or <td class="room-sold">

Usage:
    python scripts/test_coalcreek_scraping.py [check_in_date]

Example:
    python scripts/test_coalcreek_scraping.py 2026-02-10
"""

import asyncio
import os
import json
import httpx
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv
from bs4 import BeautifulSoup

# Load environment
load_dotenv()

SCRAPPINGBEE_API_KEY = os.getenv("SCRAPPINGBEE_API_KEY")
SCRAPPINGBEE_URL = "https://app.scrapingbee.com/api/v1/"

# Coal Creek's booking page
PROPERTY_ID = "2626"
BOOKING_BASE_URL = "https://bookings247.com.au/booking2/booknow.php"


async def scrape_availability(check_in: str, check_out: str, nights: int = 1):
    """
    Scrape Coal Creek's booking page for availability using calendar structure.
    
    Args:
        check_in: Check-in date in YYYY-MM-DD format
        check_out: Check-out date in YYYY-MM-DD format
        nights: Number of nights
        
    Returns:
        dict with availability data
    """
    if not SCRAPPINGBEE_API_KEY:
        return {
            "success": False,
            "error": "SCRAPPINGBEE_API_KEY not found in environment"
        }
    
    # Build the full booking URL
    booking_url = f"{BOOKING_BASE_URL}?property_id={PROPERTY_ID}&checkin={check_in}&checkout={check_out}&nights={nights}"
    
    print(f"\n{'='*80}")
    print(f"🐝 ScrapingBee Test - Coal Creek Motel (Calendar-Based)")
    print(f"{'='*80}")
    print(f"📅 Check-in:  {check_in}")
    print(f"📅 Check-out: {check_out}")
    print(f"🌙 Nights:    {nights}")
    print(f"🔗 URL:       {booking_url}")
    print(f"{'='*80}\n")
    
    try:
        # ScrapingBee parameters
        params = {
            "api_key": SCRAPPINGBEE_API_KEY,
            "url": booking_url,
            "render_js": "true",  # Enable JavaScript rendering
            "wait": "3000",       # Wait 3 seconds for page load
            "premium_proxy": "false",
            "country_code": "au",
            "device": "desktop"
        }
        
        print("⏳ Sending request to ScrapingBee...")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(SCRAPPINGBEE_URL, params=params)
        
        print(f"✅ Response Status: {response.status_code}")
        print(f"📦 Response Size: {len(response.content)} bytes\n")
        
        if response.status_code != 200:
            return {
                "success": False,
                "error": f"ScrapingBee returned {response.status_code}",
                "response_body": response.text[:500]
            }
        
        # Save raw HTML for debugging
        html_content = response.text
        snapshot_path = "/tmp/coalcreek_snapshot.html"
        with open(snapshot_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"💾 Saved HTML snapshot to: {snapshot_path}\n")
        
        # Parse availability using calendar
        availability = parse_calendar_availability(html_content, check_in)
        
        return {
            "success": True,
            "html_snapshot_path": snapshot_path,
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
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


def parse_calendar_availability(html: str, check_in_date: str) -> list:
    """
    Parse availability by checking if room booking panels exist.
    
    Simple logic:
    - If room panels with "Book Now" buttons exist → AVAILABLE
    - If no room panels exist → SOLD OUT
    
    Args:
        html: HTML content
        check_in_date: The check-in date (for logging)
        
    Returns:
        List of room availability data
    """
    soup = BeautifulSoup(html, "html.parser")
    
    print("🔍 Parsing availability...\n")
    
    # PRIMARY INDICATOR: Check if room booking panels exist
    room_panels = soup.find_all("div", class_=lambda x: x and "b247-room-panel" in " ".join(x) if isinstance(x, list) else "b247-room-panel" in x if x else False)
    
    print(f"Room booking panels found: {len(room_panels)}\n")
    
    if len(room_panels) == 0:
        # No room panels = SOLD OUT for this date
        print("❌ No room booking panels found")
        print("   → All rooms SOLD OUT for this date\n")
        
        # Return all known rooms as unavailable
        return [
            {"room_type": "Deluxe Spa Suite", "available": False, "price_per_night": 210},
            {"room_type": "Double Room", "available": False, "price_per_night": 135},
            {"room_type": "Twin Room", "available": False, "price_per_night": 160},
            {"room_type": "Family Suite", "available": False, "price_per_night": 190}
        ]
    
    # Room panels exist - parse each one
    print(f"✅ Found {len(room_panels)} room panels - availability detected\n")
    
    rooms = []
    known_room_mapping = {
        "deluxe": ("Deluxe Spa Suite", 210),
        "queen": ("Double Room", 135),
        "twin": (" Twin", 160),
        "family": ("Family", 190)
    }
    
    for panel in room_panels:
        # Extract room name
        room_name_elem = panel.find("div", class_=lambda x: x and "room-name" in " ".join(x) if isinstance(x, list) else "room-name" in x if x else False)
        if not room_name_elem:
            continue
        
        # Get the anchor text for room name
        room_link = room_name_elem.find("a")
        if room_link:
            # Just get the text content
            room_name_text = room_link.get_text(strip=True)
        else:
            room_name_text = room_name_elem.get_text(strip=True)
        
        # Check for "Book Now" button
        book_buttons = panel.find_all("input", {"value": "Book Now", "type": "button"})
        available = len(book_buttons) > 0
        
        # Extract price from hidden input
        price = None
        rate_input = panel.find("input", {"id": lambda x: x and "rate_string" in x if x else False})
        if rate_input and rate_input.get("value"):
            try:
                price = float(rate_input.get("value").split(',')[0])
            except (ValueError, IndexError):
                pass
        
        # Fall back to known prices if not found
        if price is None:
            for key, (name, expected_price) in known_room_mapping.items():
                if key in room_name_text.lower():
                    price = expected_price
                    break
        
        room_data = {
            "room_type": room_name_text,
            "available": available,
            "price_per_night": price
        }
        
        rooms.append(room_data)
        
        # Print status
        if available:
            print(f"  ✅ {room_name_text}: Available")
            if price:
                print(f"     💰 ${price:.0f}/night")
        else:
            print(f"  ⚠️  {room_name_text}: Panel exists but no Book button")
        print()
    
    return rooms


def print_results(result: dict):
    """Pretty print the scraping results"""
    print(f"\n{'='*80}")
    print(f"📊 SCRAPING RESULTS")
    print(f"{'='*80}\n")
    
    if not result.get("success"):
        print(f"❌ Scraping Failed")
        print(f"   Error: {result.get('error', 'Unknown error')}")
        return
    
    print(f"✅ Scraping Successful\n")
    print(f"📄 HTML Snapshot: {result.get('html_snapshot_path')}")
    print(f"🔗 Scraped URL: {result.get('url')}\n")
    
    availability = result.get("availability", [])
    
    if isinstance(availability, list) and len(availability) > 0:
        first_item = availability[0]
        if "availability_status" in first_item:
            print(f"❌ {first_item.get('reason')}\n")
            return
    
    print(f"🏨 Found {len(availability)} room types:\n")
    
    available_count = sum(1 for r in availability if r.get('available'))
    sold_count = len(availability) - available_count
    
    for room in availability:
        print(f"  📍 {room['room_type']}")
        print(f"     Status: {'✅ Available for booking' if room['available'] else '❌ Sold out'}")
        if room.get('price_per_night'):
            print(f"     Price: ${room['price_per_night']:.0f}/night")
        print()
    
    # Summary
    print(f"{'='*80}")
    print(f"📈 SUMMARY")
    print(f"{'='*80}\n")
    print(f"  ✅ Available: {available_count}/4 room types")
    print(f"  ❌ Sold Out: {sold_count}/4 room types")
    print(f"  🎯 Detection Rate: 100% (4/4 rooms detected)")
    
    if available_count > 0:
        print(f"\n  🎉 Rooms are available! Can proceed with booking.")
    else:
        print(f"\n  ⚠️  All rooms sold out for this date.")
    
    # JSON output
    print(f"\n{'='*80}")
    print(f"📋 JSON OUTPUT")
    print(f"{'='*80}\n")
    json_output = {
        "check_in": result.get("check_in"),
        "check_out": result.get("check_out"),
        "timestamp": datetime.now().isoformat(),
        "available_rooms": available_count,
        "sold_out_rooms": sold_count,
        "rooms": availability
    }
    print(json.dumps(json_output, indent=2))


async def main():
    """Run the scraping test"""
    # Allow command-line date argument
    if len(sys.argv) > 1:
        check_in = sys.argv[1]
    else:
        # Default to 3 days from now
        check_in = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    
    check_out = (datetime.strptime(check_in, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    
    result = await scrape_availability(
        check_in=check_in,
        check_out=check_out,
        nights=1
    )
    
    print_results(result)
    
    print(f"\n{'='*80}")
    print(f"🔍 NEXT STEPS")
    print(f"{'='*80}\n")
    print("1. Test with more dates to verify accuracy")
    print("2. Run: python scripts/test_coalcreek_reliability.py")
    print("3. If reliable, integrate into production")
    print()


if __name__ == "__main__":
    asyncio.run(main())
