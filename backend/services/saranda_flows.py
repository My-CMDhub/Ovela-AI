"""
Saranda Order/Reservation Flow Management
==========================================
State machine for managing pickup orders and reservations with WhatsApp HITL.

Key Principles:
- Fail closed: No response = request expires
- Atomic locking: First valid response wins
- One decision at a time: Internal queue, WhatsApp shows only current request
- System owns state: WhatsApp is just a notification surface
"""

import logging
from enum import Enum
from dataclasses import dataclass, field
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import uuid

from services.staff_notifications import staff_notification_service

logger = logging.getLogger(__name__)


class RequestStatus(Enum):
    """Order/Reservation request states."""
    DRAFT = "draft"                     # Being collected by AI
    PENDING_STAFF = "pending_staff"     # Sent to WhatsApp, awaiting response
    APPROVED = "approved"               # Staff said YES
    REJECTED = "rejected"               # Staff said NO
    TOO_LATE = "too_late"               # Staff said LATE (kitchen already started)
    EXPIRED = "expired"                 # TTL expired, no response
    CONFIRMED = "confirmed_to_customer" # Customer notified of approval
    CANCELLED = "cancelled"             # Cancelled by customer or system


class RequestType(Enum):
    """Types of requests that go through HITL."""
    NEW_ORDER = "order"
    CHANGE_REQUEST = "change"
    CANCELLATION = "cancel"
    RESERVATION = "reservation"


@dataclass
class OrderItem:
    """Single item in an order."""
    name: str
    price: float
    quantity: int = 1
    modifiers: List[str] = field(default_factory=list)
    notes: str = ""
    
    @property
    def subtotal(self) -> float:
        return self.price * self.quantity


@dataclass
class OrderRequest:
    """
    Represents a pickup order request going through HITL.
    
    Lifecycle:
    1. AI creates DRAFT while collecting order
    2. AI submits -> PENDING_STAFF (WhatsApp sent)
    3. Staff replies YES -> APPROVED
    4. Customer notified -> CONFIRMED
    
    Or: Staff ignores -> EXPIRED after TTL
    Or: Staff replies NO -> REJECTED
    """
    id: str
    customer_name: str
    customer_phone: str
    items: List[OrderItem]
    pickup_time: str  # e.g., "20 minutes" or "6:30 PM"
    
    # State
    status: RequestStatus = RequestStatus.DRAFT
    request_type: RequestType = RequestType.NEW_ORDER
    
    # Timing
    created_at: datetime = field(default_factory=datetime.now)
    submitted_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None
    ttl_minutes: int = 3  # Auto-expire after 3 minutes (User Requested)
    
    # Staff response
    staff_response: Optional[str] = None  # YES, NO, LATE
    staff_response_reason: Optional[str] = None  # Optional reason code
    
    # Change request specific
    original_order_id: Optional[str] = None
    change_details: Optional[str] = None
    
    @property
    def total_amount(self) -> float:
        return sum(item.subtotal for item in self.items)
    
    @property
    def is_expired(self) -> bool:
        """Check if request has expired (no response within TTL)."""
        if self.status != RequestStatus.PENDING_STAFF:
            return False
        if not self.submitted_at:
            return False
        expiry = self.submitted_at + timedelta(minutes=self.ttl_minutes)
        return datetime.now() > expiry
    
    @property
    def time_remaining_seconds(self) -> int:
        """Seconds remaining before expiry."""
        if not self.submitted_at:
            return self.ttl_minutes * 60
        expiry = self.submitted_at + timedelta(minutes=self.ttl_minutes)
        remaining = (expiry - datetime.now()).total_seconds()
        return max(0, int(remaining))
    
    def format_for_whatsapp(self) -> str:
        """Format this request for the WhatsApp approval message."""
        # Build items summary
        items_text = []
        for item in self.items:
            line = item.name
            if item.modifiers:
                line += f" (+{', '.join(item.modifiers)})"
            if item.quantity > 1:
                line = f"{item.quantity}x {line}"
            items_text.append(line)
        
        items_summary = " | ".join(items_text) if items_text else "No items"
        
        emoji = "🧾" if self.request_type == RequestType.NEW_ORDER else "🔄"
        type_label = self.request_type.value.upper()
        
        return f"""{emoji} {type_label} #{self.id}
Customer: {self.customer_name}
Items: {items_summary}
Total: ${self.total_amount:.2f}
Pickup: {self.pickup_time}

Reply:
YES ✅
NO ❌
LATE ⏳"""


@dataclass
class ReservationRequest:
    """
    Represents a table reservation request going through HITL.
    """
    id: str
    customer_name: str
    customer_phone: str
    party_size: int
    date: str  # e.g., "Saturday 18th January"
    time: str  # e.g., "7:00 PM"
    
    # State
    status: RequestStatus = RequestStatus.DRAFT
    request_type: RequestType = RequestType.RESERVATION
    
    # Timing
    created_at: datetime = field(default_factory=datetime.now)
    submitted_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None
    ttl_minutes: int = 10  # Longer TTL for reservations
    
    # Staff response
    staff_response: Optional[str] = None
    notes: str = ""
    
    @property
    def is_expired(self) -> bool:
        if self.status != RequestStatus.PENDING_STAFF:
            return False
        if not self.submitted_at:
            return False
        expiry = self.submitted_at + timedelta(minutes=self.ttl_minutes)
        return datetime.now() > expiry
    
    def format_for_whatsapp(self) -> str:
        """Format this request for the WhatsApp approval message."""
        return f"""📅 RESERVATION #{self.id}
Name: {self.customer_name}
Phone: {self.customer_phone}
Party: {self.party_size} people
Date: {self.date}
Time: {self.time}

Reply:
YES ✅
NO ❌"""


def generate_request_id() -> str:
    """Generate a short, human-readable request ID (e.g., A17, B23)."""
    # Use first letter + 2 digits for readability
    import random
    import string
    letter = random.choice(string.ascii_uppercase)
    number = random.randint(10, 99)
    return f"{letter}{number}"


def parse_staff_reply(message: str) -> tuple[str | None, str | None]:
    """
    Parse a staff WhatsApp reply message with flexible matching.
    
    Case-insensitive, handles common variations.
    Priority: NO (explicit rejection) > LATE > YES
    
    Returns:
        (command, reason) where command is YES/NO/LATE or None if invalid
    """
    import re
    
    # Normalize: lowercase, strip whitespace
    text = message.strip().lower()
    original = message.strip()  # Keep original for emoji checks
    
    # Helper: check if any word appears as a whole word (not substring)
    def has_word(text: str, words: list) -> bool:
        for word in words:
            # Match word boundaries or start/end of string
            if re.search(rf'\b{re.escape(word)}\b', text):
                return True
        return False
    
    # NO variations (check first - explicit rejection takes priority)
    no_words = ["no", "nope", "reject", "rejected", "deny", "denied", 
                "can't", "cannot", "cant", "decline", "declined", "refuse"]
    if has_word(text, no_words) or "❌" in original:
        # Check for reason codes
        reason = None
        if "1" in text or "kitchen" in text or "started" in text:
            reason = "Kitchen already started"
        elif "2" in text or "busy" in text:
            reason = "Too busy right now"
        elif "3" in text or "unavailable" in text or "ingredient" in text or "out of" in text:
            reason = "Ingredient unavailable"
        return "NO", reason
    
    # LATE variations (before YES since "already started" shouldn't be approval)
    late_words = ["late", "already", "started", "cooking", "begun", "in progress"]
    if has_word(text, late_words) or "⏳" in original:
        return "LATE", None
    
    # YES variations (case-insensitive)
    yes_words = ["yes", "yep", "yeah", "yea", "confirm", "approve", "approved", 
                 "ok", "okay", "sure", "go ahead", "accepted", "accept"]
    if has_word(text, yes_words) or "✅" in original:
        return "YES", None
    
    # Invalid/unrecognized - ignore per design
    return None, None


class RequestQueue:
    """
    In-memory queue for managing pending approval requests.
    
    Design principle: Only ONE active request visible on WhatsApp at a time.
    Others wait in queue until current is resolved.
    """
    
    def __init__(self):
        self._pending: List[OrderRequest | ReservationRequest] = []
        self._active: Optional[OrderRequest | ReservationRequest] = None
        self._completed: Dict[str, OrderRequest | ReservationRequest] = {}
    
    async def add(self, request: OrderRequest | ReservationRequest) -> None:
        """Add a new request to the queue."""
        # Clean up any stale requests blocking the queue (Anti-Ghosting)
        expired_list = self.expire_stale()
        
        # Notify ghosts (people whose requests expired)
        for exp_req in expired_list:
            try:
                # Send polite apology SMS
                await staff_notification_service.send_whatsapp_customer_confirmation(
                    customer_phone=exp_req.customer_phone,
                    order_id=exp_req.id,
                    status="expired",
                    message_override=f"Sorry, we missed your request ({exp_req.id}). Our team is super busy right now! Please call us directly to place your order. Apologies! - Saranda Team"
                )
                logger.info(f"👻 Anti-Ghosting SMS sent to {exp_req.customer_name} ({exp_req.id})")
            except Exception as e:
                logger.warning(f"Failed to send Anti-Ghosting SMS for {exp_req.id}: {e}")
        
        if self._active is None:
            self._active = request
            request.status = RequestStatus.PENDING_STAFF
            request.submitted_at = datetime.now()
            logger.info(f"Request {request.id} is now active")
        else:
            self._pending.append(request)
            logger.info(f"Request {request.id} queued behind {self._active.id}")
    
    def resolve(self, request_id: str, response: str, reason: str = None) -> bool:
        """
        Resolve the active request with staff response.
        
        Returns True if resolved, False if request not found or already resolved.
        """
        if not self._active or self._active.id != request_id:
            # Check if already completed (late reply)
            if request_id in self._completed:
                logger.warning(f"Late reply for already-resolved request {request_id}")
                return False
            logger.warning(f"Reply for unknown request {request_id}")
            return False
        
        # Lock the decision (atomic)
        self._active.staff_response = response
        self._active.staff_response_reason = reason
        self._active.responded_at = datetime.now()
        
        if response == "YES":
            self._active.status = RequestStatus.APPROVED
        elif response == "LATE":
            self._active.status = RequestStatus.TOO_LATE
        else:
            self._active.status = RequestStatus.REJECTED
        
        # Move to completed
        self._completed[request_id] = self._active
        logger.info(f"Request {request_id} resolved: {response}")
        
        # Activate next in queue
        self._active = None
        if self._pending:
            self._active = self._pending.pop(0)
            self._active.status = RequestStatus.PENDING_STAFF
            self._active.submitted_at = datetime.now()
            logger.info(f"Next request {self._active.id} is now active")
        
        return True
    
    def expire_stale(self) -> List[OrderRequest | ReservationRequest]:
        """
        Check and expire requests that have exceeded TTL.
        
        Returns list of expired Request objects (so we can notify them).
        """
        expired = []
        
        if self._active and self._active.is_expired:
            self._active.status = RequestStatus.EXPIRED
            self._completed[self._active.id] = self._active
            expired.append(self._active)
            logger.info(f"Request {self._active.id} expired (no response)")
            
            # Activate next
            self._active = None
            if self._pending:
                self._active = self._pending.pop(0)
                self._active.status = RequestStatus.PENDING_STAFF
                self._active.submitted_at = datetime.now()
        
        return expired
    
    def get_active(self) -> Optional[OrderRequest | ReservationRequest]:
        """Get the currently active request (if any)."""
        return self._active
    
    def get_request(self, request_id: str) -> Optional[OrderRequest | ReservationRequest]:
        """Get a request by ID (active, pending, or completed)."""
        if self._active and self._active.id == request_id:
            return self._active
        for req in self._pending:
            if req.id == request_id:
                return req
        return self._completed.get(request_id)
    
    @property
    def queue_length(self) -> int:
        """Number of requests waiting in queue."""
        return len(self._pending)
    
    @property
    def is_busy(self) -> bool:
        """True if queue is getting backed up."""
        return len(self._pending) >= 3  # Threshold for "busy mode"


# Global queue instance for Saranda tenant
# In production, this would be per-tenant and Redis-backed
saranda_queue = RequestQueue()


# =============================================================================
# DELAYED NOTIFICATION QUEUE (Off-Hours Reservations)
# =============================================================================

class DelayedNotificationQueue:
    """
    Holds off-hours reservation requests until next business opening.
    
    When a customer requests a reservation outside of business hours,
    we log it immediately but delay the WhatsApp notification to staff
    until 5 minutes before the next opening time.
    
    This ensures:
    1. Customer gets immediate acknowledgment ("We'll pass this to the team")
    2. Staff aren't pinged at midnight
    3. Nothing gets lost
    """
    
    def __init__(self):
        self._pending: List[ReservationRequest] = []
        self._processed: Dict[str, ReservationRequest] = {}
    
    def add(self, request: ReservationRequest) -> None:
        """Queue a reservation for delayed notification."""
        self._pending.append(request)
        logger.info(f"📋 Queued off-hours reservation {request.id} for delayed notification")
    
    @property
    def pending_count(self) -> int:
        return len(self._pending)
    
    def get_pending(self) -> List[ReservationRequest]:
        """Get all pending requests (for processing)."""
        return self._pending.copy()
    
    def mark_processed(self, request_id: str) -> bool:
        """Mark a request as processed (notification sent)."""
        for i, req in enumerate(self._pending):
            if req.id == request_id:
                processed = self._pending.pop(i)
                self._processed[request_id] = processed
                logger.info(f"✅ Delayed notification sent for {request_id}")
                return True
        return False
    
    def get_next_notification_time(self) -> Optional[datetime]:
        """
        Get the datetime when pending notifications should be sent.
        
        Returns 5 minutes before next opening time.
        """
        from services.knowledge_base.saranda import get_next_opening_datetime
        
        next_opening = get_next_opening_datetime()
        if next_opening:
            # Send notification 5 minutes before opening
            from datetime import timedelta
            return next_opening - timedelta(minutes=5)
        return None


# Global delayed notification queue
delayed_notification_queue = DelayedNotificationQueue()

