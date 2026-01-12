from .data_types import MotelData

LYDOUN_DATA: MotelData = {
    "rooms": {
        "queen": {
            "name": "Queen Room",
            "price": 130,
            "max_guests": 2,
            "bedding": "Queen Bed",
            "best_for": "Solo travellers, couples, business guests",
            "facilities": [
                "Queen Bed", "Table + chairs", "Couch", "Air-conditioner/heating",
                "HD flat screen TV", "En-suite bathroom", "Free WiFi",
                "Coffee/tea making facilities", "Toaster", "Microwave",
                "Bar fridge", "Oil heater", "Hairdryer", "Iron and ironing board",
                "At-door parking"
            ]
        },
        "twin": {
            "name": "Twin Room",
            "price": 140,
            "max_guests": 3,
            "bedding": "Queen Bed + Single Bed",
            "best_for": "Friends travelling together, small groups",
            "facilities": [
                "Queen Bed plus Single Bed", "Table + chairs", "Air-conditioner/heating",
                "HD flat screen TV", "En-suite bathroom", "Free WiFi",
                "Coffee/tea making facilities", "Toaster", "Microwave",
                "Bar fridge", "Oil heater", "Hairdryer", "Iron and ironing board",
                "At-door parking"
            ]
        },
        "family": {
            "name": "Family Room",
            "price": 160,
            "max_guests": 4,
            "bedding": "Queen Bed + Two Single Beds",
            "best_for": "Families, groups of friends",
            "facilities": [
                "Queen Bed plus Two Single Beds", "Air-conditioner/heating",
                "HD flat screen TV", "En-suite bathroom", "Free WiFi",
                "Coffee/tea making facilities", "Toaster", "Microwave",
                "Bar fridge", "Oil heater", "Hairdryer", "Iron and ironing board",
                "At-door parking"
            ]
        },
        "accessible": {
            "name": "Accessible Room",
            "price": 130,
            "max_guests": 3,
            "bedding": "Queen Bed + Single Bed",
            "best_for": "Guests with reduced mobility",
            "special_features": [
                "Flat floor internally",
                "Open shower with hand rails and shower stool",
                "Note: NOT adjusted for all special needs - contact to discuss requirements"
            ],
            "facilities": [
                "Queen Bed plus Single Bed", "Open Shower with hand rails and stool",
                "Table + chairs", "Air-conditioner/heating", "HD flat screen TV",
                "En-suite bathroom", "Free WiFi", "Coffee/tea making facilities",
                "Toaster", "Microwave", "Bar fridge", "Oil heater", "Hairdryer",
                "Iron and ironing board", "At-door parking"
            ]
        }
    },
    "info": {
        "name": "The Lydoun Motel Chiltern",
        "address": "7 Main Street, Chiltern Vic 3683, Australia",
        "phone": "(03) 5726 1788",
        "total_rooms": 14,
        "reception_hours": "7:30am – 9:00pm",
        "check_in": "From 2:00pm",
        "check_out": "Prior to 10:00am",
        "owner": "Meena",
        "established_rebrand": 2017,
        "previous_name": "The Chiltern Colonial Motor Inn"
    },
    "amenities": [
        "All Rooms at Ground Level",
        "Reduced Mobility Room available",
        "100% Non Smoking Rooms",
        "Complimentary WiFi",
        "Room Service",
        "Extra Single Bed or Cot Available",
        "Seasonal Pool",
        "Guest BBQ",
        "Free Onsite Parking",
        "Guest Laundry Facilities",
        "Large Vehicle Parking Area",
        "Group Bookings (contact directly)"
    ],
    "location": {
        "description": "Just off the Hume Freeway, midway between Wangaratta and Wodonga",
        "region": "North East Victoria",
        "national_park": "Chiltern Mt Pilot National Park",
        "distances": {
            "Melbourne": "3 hours north",
            "Canberra": "4 hours south",
            "Albury/Wodonga": "30 minutes",
            "Wangaratta": "30 minutes",
            "Rutherglen wine region": "20 minutes north",
            "Beechworth": "20 minutes south",
            "Yackandandah": "20 minutes east",
            "Albury Regional Airport": "30 minutes drive"
        },
        "travel_options": {
            "car": "Just off the Hume Freeway",
            "train": "Historic railway station on Melbourne-Sydney rail line",
            "plane": "30 minutes from Albury Regional Airport",
            "boat": "3 hours from Spirit of Tasmania dock (late check-in available)"
        }
    },
    "activities": [
        "Gold fossicking",
        "Bird watching",
        "Cycling",
        "Walking trails",
        "Antique browsing",
        "Horse riding",
        "Fishing and hunting",
        "Photography",
        "Wine tasting (Rutherglen)",
        "Craft beer and spirits tasting"
    ],
    "policies": {
        "cancellation": {
            "standard": "24 hours notice required prior to check-in. Late cancellation forfeits first night's fee.",
            "peak": "7 days notice required for Special Events & Public Holidays. Late cancellation forfeits first night's fee.",
            "no_show": "Full first night tariff charged to credit card provided at booking."
        },
        "payment": {
            "surcharge": "2.2% Service & Handling Fee applies to all online card payments.",
            "methods": "Visa, MasterCard. Processed as 'Accommodation Payment Services'.",
            "terms": "Full payment may be charged at booking. Balance collected at check-in if not pre-paid.",
            "check_in_payment": "Balance payable at reception upon arrival."
        }
    }
}
