from typing import TypedDict, List, Dict, Any, Optional

class RoomDetails(TypedDict):
    name: str
    price: int
    max_guests: int
    bedding: str
    best_for: str
    facilities: List[str]
    special_features: Optional[List[str]]

class MotelInfo(TypedDict):
    name: str
    address: str
    phone: str
    total_rooms: int
    reception_hours: str
    check_in: str
    check_out: str
    owner: str
    established_rebrand: Optional[int]
    previous_name: Optional[str]

class LocationInfo(TypedDict):
    description: str
    region: str
    national_park: str
    distances: Dict[str, str]
    travel_options: Dict[str, str]

class Policies(TypedDict):
    cancellation: Dict[str, str]
    payment: Dict[str, str]

class MotelData(TypedDict):
    rooms: Dict[str, RoomDetails]
    info: MotelInfo
    amenities: List[str]
    location: LocationInfo
    activities: List[str]
    policies: Policies
