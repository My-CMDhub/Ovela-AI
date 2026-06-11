"""
PMS Client Base Classes
=======================
Abstract base class and data types for PMS integrations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum


class AvailabilityConfidence(Enum):
    """Confidence level for availability check."""
    VERIFIED = "verified"          # Live PMS check successful
    CACHED = "cached"              # From recent cache
    UNVERIFIED = "unverified"      # Could not verify, defer to staff


@dataclass
class AvailabilityResult:
    """Result of an availability check."""
    available: bool
    confidence: AvailabilityConfidence
    rooms_left: Optional[int] = None
    room_type: Optional[str] = None
    message: Optional[str] = None
    
    @property
    def is_verified(self) -> bool:
        """Check if availability is verified from PMS."""
        return self.confidence == AvailabilityConfidence.VERIFIED
    
    @classmethod
    def unverified(cls, message: str = None) -> "AvailabilityResult":
        """Create an unverified result (fallback)."""
        return cls(
            available=False,
            confidence=AvailabilityConfidence.UNVERIFIED,
            message=message or "Unable to verify availability. Staff will confirm."
        )


@dataclass
class BookingRecord:
    """A booking record from the PMS."""
    reference: str
    guest_name: str
    guest_phone: Optional[str]
    guest_email: Optional[str]
    check_in: str
    check_out: str
    room_type: str
    status: str  # "confirmed", "pending", "cancelled", etc.
    source: str  # "website", "walk_in", "phone", "ai"
    total_amount: Optional[float] = None
    created_at: Optional[str] = None
    pms_id: Optional[str] = None  # Original ID in PMS


@dataclass
class RoomStatus:
    """Current status of a room."""
    room_id: str
    room_type: str
    status: str  # "available", "occupied", "maintenance"
    current_guest: Optional[str] = None
    checkout_date: Optional[str] = None


class PMSClient(ABC):
    """
    Abstract base class for PMS integrations.
    
    All PMS providers should implement this interface.
    """
    
    @abstractmethod
    def is_configured(self) -> bool:
        """Check if the client is properly configured with API credentials."""
        pass
    
    @abstractmethod
    async def check_availability(
        self,
        check_in: str,
        check_out: str,
        room_type: Optional[str] = None
    ) -> AvailabilityResult:
        """
        Check room availability for given dates.
        
        Args:
            check_in: Check-in date (YYYY-MM-DD)
            check_out: Check-out date (YYYY-MM-DD)
            room_type: Optional room type filter
            
        Returns:
            AvailabilityResult with availability status and confidence
        """
        pass
    
    @abstractmethod
    async def get_bookings(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> List[BookingRecord]:
        """
        Get bookings in a date range.
        
        Args:
            from_date: Start date (YYYY-MM-DD), defaults to today
            to_date: End date (YYYY-MM-DD), defaults to 30 days ahead
            
        Returns:
            List of BookingRecord objects
        """
        pass
    
    @abstractmethod
    async def get_room_status(self) -> List[RoomStatus]:
        """
        Get current status of all rooms.
        
        Returns:
            List of RoomStatus objects
        """
        pass
