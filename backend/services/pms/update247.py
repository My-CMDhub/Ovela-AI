"""
Update247 PMS Client
=====================
Integration with Update247 property management system.

Note: Endpoint URLs are placeholders until API documentation is obtained.
"""

import logging
from typing import List, Optional
from datetime import datetime, timedelta
import httpx

from .base import (
    PMSClient,
    AvailabilityResult,
    AvailabilityConfidence,
    BookingRecord,
    RoomStatus,
)

logger = logging.getLogger(__name__)

# Timeout for API calls
API_TIMEOUT = 10.0  # seconds


class Update247Client(PMSClient):
    """
    Update247 PMS integration client.
    
    Provides read-only access to:
    - Room availability
    - Booking list
    - Room status
    
    Note: Write operations (creating bookings) are not implemented.
    Staff manually adds AI-initiated bookings to Update247.
    """
    
    def __init__(self, api_key: str, property_id: str):
        """
        Initialize Update247 client.
        
        Args:
            api_key: API key from Update247
            property_id: Property identifier in Update247
        """
        self.api_key = api_key
        self.property_id = property_id
        
        # Placeholder base URL - update when documentation received
        self.base_url = "https://api.update247.com/v2"
        
        logger.info(f"Update247 client initialized for property: {property_id}")
    
    def is_configured(self) -> bool:
        """Check if client has valid credentials."""
        return bool(self.api_key and self.property_id)
    
    def _get_headers(self) -> dict:
        """Get HTTP headers for API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Property-ID": self.property_id,
        }
    
    async def check_availability(
        self,
        check_in: str,
        check_out: str,
        room_type: Optional[str] = None
    ) -> AvailabilityResult:
        """
        Check room availability for given dates.
        
        Makes real-time API call to Update247.
        Falls back to unverified if API fails.
        """
        if not self.is_configured():
            return AvailabilityResult.unverified("PMS not configured")
        
        try:
            # Placeholder endpoint - update when API docs received
            endpoint = f"{self.base_url}/availability"
            
            params = {
                "property_id": self.property_id,
                "check_in": check_in,
                "check_out": check_out,
            }
            
            if room_type:
                params["room_type"] = room_type
            
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                response = await client.get(
                    endpoint,
                    headers=self._get_headers(),
                    params=params
                )
            
            if response.status_code == 200:
                data = response.json()
                
                # Parse response - adjust based on actual API structure
                return AvailabilityResult(
                    available=data.get("available", False),
                    confidence=AvailabilityConfidence.VERIFIED,
                    rooms_left=data.get("rooms_available", 0),
                    room_type=room_type,
                    message="Availability verified from booking system"
                )
            
            elif response.status_code == 401:
                logger.error("Update247 API: Invalid credentials")
                return AvailabilityResult.unverified("Authentication failed")
            
            else:
                logger.warning(f"Update247 API returned {response.status_code}")
                return AvailabilityResult.unverified(f"API error: {response.status_code}")
        
        except httpx.TimeoutException:
            logger.warning("Update247 API timeout")
            return AvailabilityResult.unverified("Booking system temporarily unavailable")
        
        except Exception as e:
            logger.error(f"Update247 API error: {e}")
            return AvailabilityResult.unverified("Could not verify availability")
    
    async def get_bookings(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> List[BookingRecord]:
        """
        Get bookings in a date range.
        
        Used by background sync job to import external bookings.
        """
        if not self.is_configured():
            logger.warning("get_bookings called but PMS not configured")
            return []
        
        # Default date range
        if not from_date:
            from_date = datetime.now().strftime("%Y-%m-%d")
        if not to_date:
            to_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        
        try:
            # Placeholder endpoint - update when API docs received
            endpoint = f"{self.base_url}/bookings"
            
            params = {
                "property_id": self.property_id,
                "from_date": from_date,
                "to_date": to_date,
            }
            
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                response = await client.get(
                    endpoint,
                    headers=self._get_headers(),
                    params=params
                )
            
            if response.status_code == 200:
                data = response.json()
                bookings = []
                
                # Parse response - adjust based on actual API structure
                for item in data.get("bookings", []):
                    bookings.append(BookingRecord(
                        reference=item.get("booking_reference", ""),
                        guest_name=item.get("guest_name", ""),
                        guest_phone=item.get("guest_phone"),
                        guest_email=item.get("guest_email"),
                        check_in=item.get("check_in", ""),
                        check_out=item.get("check_out", ""),
                        room_type=item.get("room_type", "queen"),
                        status=item.get("status", "confirmed"),
                        source=item.get("source", "website"),
                        total_amount=item.get("total_amount"),
                        created_at=item.get("created_at"),
                        pms_id=item.get("id"),
                    ))
                
                logger.info(f"Fetched {len(bookings)} bookings from Update247")
                return bookings
            
            else:
                logger.warning(f"Update247 bookings API returned {response.status_code}")
                return []
        
        except Exception as e:
            logger.error(f"Update247 get_bookings error: {e}")
            return []
    
    async def get_room_status(self) -> List[RoomStatus]:
        """
        Get current status of all rooms.
        
        Used for dashboard display and availability cache.
        """
        if not self.is_configured():
            return []
        
        try:
            # Placeholder endpoint - update when API docs received
            endpoint = f"{self.base_url}/rooms/status"
            
            params = {"property_id": self.property_id}
            
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                response = await client.get(
                    endpoint,
                    headers=self._get_headers(),
                    params=params
                )
            
            if response.status_code == 200:
                data = response.json()
                rooms = []
                
                # Parse response - adjust based on actual API structure
                for item in data.get("rooms", []):
                    rooms.append(RoomStatus(
                        room_id=item.get("room_id", ""),
                        room_type=item.get("room_type", "queen"),
                        status=item.get("status", "available"),
                        current_guest=item.get("current_guest"),
                        checkout_date=item.get("checkout_date"),
                    ))
                
                logger.info(f"Fetched status for {len(rooms)} rooms from Update247")
                return rooms
            
            else:
                logger.warning(f"Update247 room status API returned {response.status_code}")
                return []
        
        except Exception as e:
            logger.error(f"Update247 get_room_status error: {e}")
            return []
