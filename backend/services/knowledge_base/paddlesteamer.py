from .data_types import MotelData

PADDLESTEAMER_DATA: MotelData = {
    "rooms": {
        "deluxe_king": {
            "name": "Deluxe King Room",
            "price": 160, # Estimated from context context
            "max_guests": 2,
            "bedding": "1 King Bed",
            "best_for": "Couples and individual business travelers",
            "facilities": [
                "King Bed", "Kitchenette (fridge, microwave, toaster, kettle, crockery, sink)",
                "Dining table and chairs", "Large desk", "Extra large LCD TV with FOXTEL",
                "Free WiFi", "Modern bathroom with fluffy towels",
                "Reverse cycle air-conditioning", "Ground floor"
            ]
        },
        "deluxe_queen": {
            "name": "Deluxe Queen Room",
            "price": 150, # Estimated
            "max_guests": 2,
            "bedding": "1 Queen Bed",
            "best_for": "One or two guests",
            "facilities": [
                "Queen Bed", "Kitchenette (fridge, microwave, toaster, kettle, crockery, sink)",
                "Dining table and chairs", "Large desk", "Large LCD TV with FOXTEL",
                "Free WiFi", "Modern bathroom",
                "Reverse cycle air-conditioning", "Ground floor"
            ]
        },
        "deluxe_twin": {
            "name": "Deluxe Twin Room",
            "price": 160, # Estimated
            "max_guests": 3,
            "bedding": "1 Queen Bed + 1 Single Bed",
            "best_for": "Three guests, friends traveling together",
            "facilities": [
                "Queen Bed plus Single Bed", "Kitchenette", "Dining table and chairs",
                "LCD TV with FOXTEL", "Free WiFi", "Modern bathroom",
                "Reverse cycle air-conditioning", "Ground floor"
            ]
        },
        "standard_queen": {
            "name": "Standard Queen Room",
            "price": 130, # Estimated "affordable price"
            "max_guests": 2,
            "bedding": "1 Queen Bed",
            "best_for": "Budget conscious travelers, short stays",
            "facilities": [
                "Queen Bed", "Tea/Coffee making facilities", "LCD TV with FOXTEL",
                "Free WiFi", "En-suite bathroom", "Reverse cycle air-conditioning",
                "First floor access (stairs)"
            ]
        },
        "standard_twin": {
            "name": "Standard Twin Room",
            "price": 140, # Estimated
            "max_guests": 3,
            "bedding": "1 Queen Bed + 1 Single Bed",
            "best_for": "Budget conscious groups",
            "facilities": [
                "Queen Bed plus Single Bed", "Tea/Coffee making facilities", 
                "LCD TV with FOXTEL", "Free WiFi", "En-suite bathroom",
                "Reverse cycle air-conditioning", "First floor access (stairs)"
            ]
        },
        "family": {
            "name": "Extra Large Family Room",
            "price": 220, # Estimated
            "max_guests": 5,
            "bedding": "2 Queen Beds + 1 Single Bed",
            "best_for": "Families, larger groups",
            "facilities": [
                "2 Queen Beds plus 1 Single Bed", "Kitchenette",
                "42\" LCD TV with FOXTEL", "Free WiFi", "En-suite bathroom",
                "Reverse cycle air-conditioning", "Dining area",
                "On-site parking"
            ]
        }
    },
    "info": {
        "name": "Albury Paddlesteamer Motel",
        "address": "324 Wodonga Place, Albury NSW 2640",
        "phone": "(02) 6042 0500",
        "total_rooms": 30, # Estimated
        "reception_hours": "Contact for hours",
        "check_in": "2:00pm",
        "check_out": "10:00am",
        "owner": "Manager",
        "established_rebrand": None,
        "previous_name": None
    },
    "amenities": [
        "Restaurant (Closed)",
        "Saltwater Pool",
        "Free On-site Parking (abundant)",
        "Free WiFi",
        "Ice Machine (near reception)",
        "Conference Room (The Empress Room, capacity 50)",
        "Interconnecting Rooms Available",
        "Opposite Noreuil Park",
        "Located near Murray River",
        "Close to Albury City Centre",
        "All rooms recently renovated",
        "AAA Four-Star Rated"
    ],
    "location": {
        "description": "Perfectly positioned on the border of Albury Wodonga, close to city centre and just over the bridge from Wodonga.",
        "region": "Albury Wodonga",
        "national_park": "Noreuil Park (opposite)",
        "distances": {
            "Albury CBD": "Close proximity",
            "Wodonga": "Just over the bridge",
            "Noreuil Park": "Opposite the motel",
            "Botanical Gardens": "Walking distance via riverside",
            "Oddies Creek Adventure Playground": "Opposite (Noreuil Park)"
        },
        "travel_options": {
            "car": "On Wodonga Place, plenty of free parking",
            "walk": "Walking distance to river and parks"
        }
    },
    "activities": [
        "Walking along Murray River",
        "Cycling on riverside bike tracks",
        "Visiting Albury Botanic Gardens",
        "Oddies Creek Adventure Playspace (playground with dinosaurs)",
        "Swimming in on-site saltwater pool",
        "Picnic in Noreuil Park (BBQ facilities)",
        "Exploring historic townships nearby",
        "Winery visits (Rutherglen nearby)",
        "Team building activities"
    ],
    "policies": {
        "cancellation": {
            "standard": "24 hours notice required prior to check-in.",
            "peak": "Contact property for peak period policies.",
            "no_show": "First night's fee charged."
        },
        "payment": {
            "surcharge": "2.2% Service & Handling Fee for online payments (typical).",
            "methods": "Visa, MasterCard.",
            "terms": "Book direct for discounted rates. Payment typically on arrival or booking.",
            "check_in_payment": "Balance payable on arrival."
        }
    }
}
