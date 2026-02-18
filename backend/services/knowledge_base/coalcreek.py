"""
Coal Creek Motel - Knowledge Base Data.

Contains structured data for:
- Room Types & Pricing
- Amenities & Facilities
- Policies (Check-in, Check-out, etc.)
- Location & Contact Info

Used to dynamically generate system prompts and answer function queries.
"""

COALCREEK_DATA = {
    "info": {
        "name": "Coal Creek Motel",
        "phone": "0492 897 718",
        "email": "coalcreekmotel@gmail.com",
        "address": "8444 South Gippsland Highway, Korumburra VIC 3950",
        "website": "coalcreekmotel.com.au",
        "reception_hours": "8:00am - 8:00pm",  # Assumed or standard, adjust if known
        "check_in": "2:00pm",
        "check_out": "10:00am",
        "late_check_in_fee": "$50 (must be arranged in advance)",
    },
    "location": {
        "description": "Located in Korumburra, the 'Heritage Centre of South Gippsland', in the foothills of the Strzelecki Ranges. Opposite Prom Country Visitor Information Centre.",
        "region": "South Gippsland, Victoria",
        "nearby_attractions": [
            "Coal Creek Heritage Village (4 min walk)",
            "Korumburra Botanic Park (26 min walk)",
            "Leongatha Golf Club (8.2km)",
            "Great Southern Rail Trail (9.2km)",
            "Lucinda Estate Wines (9.6km)",
            "Wilson Promontory National Park (Day trip)",
            "Inverloch & Venus Bay (Coastal towns nearby)"
        ]
    },
    "rooms": {
        "queen": {
            "name": "Standard Queen Room",
            "price": 135,
            "bedding": "1 Queen Bed",
            "max_guests": 2,
            "features": "Ground floor, Parking at door, Ensuite, Free WiFi, Flat-screen TV, Fridge, Microwave, Tea/Coffee making, Electric blanket",
            "best_for": "Couples or solo travelers"
        },
        "twin": {
            "name": "Twin Room",
            "price": 160,
            "bedding": "1 Queen Bed + 1 Single Bed",
            "max_guests": 3,
            "features": "Ground floor, Parking at door, Ensuite, Free WiFi, Flat-screen TV, Fridge, Microwave, Tea/Coffee making, Electric blanket",
            "best_for": "Friends or small families"
        },
        "spa": {
            "name": "Deluxe Spa Suite",
            "price": 210,
            "bedding": "1 King Bed (or Large Queen)",
            "max_guests": 2,
            "features": "Large corner spa bath, Private patio, Ground floor, Parking at door, Ensuite, Free WiFi, Flat-screen TV, Fridge, Microwave",
            "best_for": "Couples, special occasions, relaxation"
        },
        "family": {
            "name": "Family Room",
            "price": 180, # Estimate/Placeholder based on market rates, to be confirmed by client
            "bedding": "1 Queen Bed + 2 Single Beds",
            "max_guests": 4,
            "features": "Larger room, Ground floor, Parking at door, Ensuite, Free WiFi, Flat-screen TV, Fridge, Microwave, Toaster",
            "best_for": "Families or groups (up to 4)"
        }
    },
    "amenities": [
        "Free WiFi in all rooms",
        "Free private parking (space for large vehicles)",
        "BBQ facilities",
        "Air conditioning (Reverse cycle)",
        "Flat-screen TV",
        "Streaming services (Netflix/Stan capable smart TVs - verify)",
        "Refrigerator & Microwave",
        "Tea/Coffee making facilities",
        "Electric blankets",
        "Non-smoking rooms",
        "Wheelchair accessible (check availability)",
        "Continental breakfast available (verify)",
        "Luggage storage",
        "Garden area"
    ],
    "policies": {
        "cancellation": "Free cancellation up to 48 hours before check-in. Full charge if cancelled within 48 hours.",
        "payment": "Credit card required to secure booking. Payment processed upon arrival (unless prepaid).",
        "pets": "No pets allowed.",
        "smoking": "Strictly non-smoking in rooms.",
        "children": "Children welcome. Port-a-cot available for hire ($20/night). Extra child (under 16) $40/night.",
        "groups": "Group bookings (5+ rooms) require direct management approval."
    }
}
