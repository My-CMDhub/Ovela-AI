"""
Square Order Flow Management for Saranda
=========================================
Tracks orders created by AI and detects staff approval/rejection via state changes.

Key Design:
- Orders created in OPEN state with metadata tagging
- Staff "approves" by: processing payment, marking completed, or leaving open
- Staff "rejects" by: canceling/deleting the order
- Polling fallback catches missed webhooks
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any

from .square_client import SquareClient, SquareOrder

logger = logging.getLogger(__name__)


class ApprovalState(Enum):
    """States for AI-created orders awaiting staff action."""
    PENDING = "pending"          # Created, waiting for staff
    APPROVED = "approved"        # Staff confirmed (order COMPLETED or payment taken)
    REJECTED = "rejected"        # Staff cancelled the order
    MODIFIED = "modified"        # Staff changed items (detected via version change)
    EXPIRED = "expired"          # No staff action within TTL


@dataclass
class SquareOrderRequest:
    """
    Represents an AI-created order pending staff approval.
    
    Lifecycle:
    1. AI creates order in Square -> PENDING
    2. Staff sees order in Square Dashboard
    3. Staff action detected:
       - Order COMPLETED -> APPROVED
       - Order CANCELED -> REJECTED
       - Order version changed -> MODIFIED (then check final state)
    4. Customer notified based on final state
    """
    # Square identifiers
    square_order_id: str
    square_order_version: int
    
    # Our identifiers
    call_id: str
    request_id: str  # Short human-readable ID (e.g., "A17")
    
    # Customer info
    customer_name: str
    customer_phone: str
    
    # Order details
    pickup_time: str
    total_cents: int
    items_summary: str  # Human-readable summary
    
    # State tracking
    state: ApprovalState = ApprovalState.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    
    # Config
    ttl_minutes: int = 5
    
    @property
    def total_dollars(self) -> float:
        return self.total_cents / 100
    
    @property
    def is_expired(self) -> bool:
        """Check if request has expired (no staff action within TTL)."""
        if self.state != ApprovalState.PENDING:
            return False
        expiry = self.created_at + timedelta(minutes=self.ttl_minutes)
        return datetime.now() > expiry
    
    @property
    def time_remaining_seconds(self) -> int:
        """Seconds remaining before expiry."""
        if self.state != ApprovalState.PENDING:
            return 0
        expiry = self.created_at + timedelta(minutes=self.ttl_minutes)
        remaining = (expiry - datetime.now()).total_seconds()
        return max(0, int(remaining))


def generate_request_id() -> str:
    """Generate a short, human-readable request ID (e.g., A17, B23)."""
    import random
    import string
    letter = random.choice(string.ascii_uppercase)
    number = random.randint(10, 99)
    return f"{letter}{number}"


class SquareApprovalTracker:
    """
    Tracks pending orders and detects staff approval/rejection.
    
    Detection Logic:
    - Order state = COMPLETED -> Staff approved (payment/marked done)
    - Order state = CANCELED -> Staff rejected
    - Order version increased but state unchanged -> Staff modified items
    - TTL expired with no change -> Expired (treat as rejection)
    """
    
    def __init__(self, square_client: Optional[SquareClient] = None):
        self.square_client = square_client or SquareClient()
        self._pending: Dict[str, SquareOrderRequest] = {}  # order_id -> request
        self._resolved: Dict[str, SquareOrderRequest] = {}  # order_id -> request
    
    def track(self, request: SquareOrderRequest) -> None:
        """Start tracking an order for staff action."""
        self._pending[request.square_order_id] = request
        logger.info(
            f"📋 Tracking order {request.request_id} "
            f"(Square: {request.square_order_id}) for staff approval"
        )
    
    def get_pending(self) -> List[SquareOrderRequest]:
        """Get all pending orders."""
        return list(self._pending.values())
    
    def get_request(self, order_id: str) -> Optional[SquareOrderRequest]:
        """Get a request by Square order ID."""
        return self._pending.get(order_id) or self._resolved.get(order_id)
    
    def get_request_by_call_id(self, call_id: str) -> Optional[SquareOrderRequest]:
        """Get a request by our internal call ID."""
        for req in list(self._pending.values()) + list(self._resolved.values()):
            if req.call_id == call_id:
                return req
        return None
    
    async def poll_for_updates(self) -> List[SquareOrderRequest]:
        """
        Poll Square API for status changes on pending orders.
        
        Returns list of requests that had state changes (for notification).
        """
        if not self._pending:
            return []
        
        order_ids = list(self._pending.keys())
        logger.debug(f"Polling {len(order_ids)} pending orders...")
        
        # Batch fetch all orders
        orders = await self.square_client.batch_get_orders(order_ids)
        
        changed: List[SquareOrderRequest] = []
        
        for order_id, order_data in orders.items():
            request = self._pending.get(order_id)
            if not request:
                continue
            
            # order_data is now an object, not a dict
            square_state = order_data.state if hasattr(order_data, 'state') else "OPEN"
            square_version = order_data.version if hasattr(order_data, 'version') else 1
            fulfillments = order_data.fulfillments if hasattr(order_data, 'fulfillments') else []
            
            new_state = self._detect_approval_state(
                square_state=square_state,
                square_version=square_version,
                original_version=request.square_order_version,
                fulfillments=fulfillments,
            )
            
            if new_state != ApprovalState.PENDING:
                # State changed!
                request.state = new_state
                request.resolved_at = datetime.now()
                request.square_order_version = square_version
                
                # Move to resolved
                del self._pending[order_id]
                self._resolved[order_id] = request
                changed.append(request)
                
                logger.info(
                    f"✅ Order {request.request_id} state changed: {new_state.value} "
                    f"(Square state: {square_state})"
                )
        
        # Check for expired orders (not in Square response or TTL exceeded)
        expired = self._check_expiries()
        changed.extend(expired)
        
        return changed
    
    def _detect_approval_state(
        self,
        square_state: str,
        square_version: int,
        original_version: int,
        fulfillments: List[Any] = None,
    ) -> ApprovalState:
        """
        Determine approval state from Square order state.
        
        Square Order States:
        - OPEN: Order created
        - COMPLETED: Order finalized (picked up)
        - CANCELED: Staff cancelled
        
        Fulfillment States (Pickup):
        - PROPOSED: AI created it (Pending)
        - RESERVED: Staff accepted it (Approved)
        - PREPARED: Staff marked ready (Approved)
        - COMPLETED: Customer picked up (Approved)
        - CANCELED: Staff rejected (Rejected)
        - FAILED: System rejected (Rejected)
        """
        if square_state == "CANCELED":
            return ApprovalState.REJECTED
        
        # Check fulfillment state if available
        if fulfillments:
            # Look at the first fulfillment (we usually only have one for simple pickup)
            fulfillment = fulfillments[0]
            # Handle object vs dict
            f_state = (fulfillment.state if hasattr(fulfillment, 'state') else fulfillment.get('state')) or "PROPOSED"
            
            if f_state in ("RESERVED", "PREPARED", "COMPLETED"):
                return ApprovalState.APPROVED
            elif f_state in ("CANCELED", "FAILED"):
                return ApprovalState.REJECTED
        
        if square_state == "COMPLETED":
            return ApprovalState.APPROVED
            
        elif square_version > original_version:
            # Staff modified the order but didn't complete/cancel/accept yet
            logger.info(f"Order modified (version {original_version} -> {square_version})")
            return ApprovalState.PENDING
        else:
            return ApprovalState.PENDING
    
    def _check_expiries(self) -> List[SquareOrderRequest]:
        """Check for and expire stale requests."""
        expired: List[SquareOrderRequest] = []
        
        for order_id in list(self._pending.keys()):
            request = self._pending[order_id]
            if request.is_expired:
                request.state = ApprovalState.EXPIRED
                request.resolved_at = datetime.now()
                
                del self._pending[order_id]
                self._resolved[order_id] = request
                expired.append(request)
                
                logger.warning(
                    f"⏰ Order {request.request_id} expired (no staff action)"
                )
        
        return expired
    
    def process_webhook_event(
        self,
        order_id: str,
        event_type: str,
        order_data: Dict,
    ) -> Optional[SquareOrderRequest]:
        """
        Process a Square webhook event (order.updated).
        
        Returns the request if state changed, None otherwise.
        """
        request = self._pending.get(order_id)
        if not request:
            logger.debug(f"Webhook for unknown/resolved order {order_id}")
            return None
        
        square_state = order_data.get("state", "OPEN")
        square_version = order_data.get("version", 1)
        fulfillments = order_data.get("fulfillments", [])
        
        new_state = self._detect_approval_state(
            square_state=square_state,
            square_version=square_version,
            original_version=request.square_order_version,
            fulfillments=fulfillments,
        )
        
        if new_state != ApprovalState.PENDING:
            request.state = new_state
            request.resolved_at = datetime.now()
            request.square_order_version = square_version
            
            del self._pending[order_id]
            self._resolved[order_id] = request
            
            logger.info(
                f"📬 Webhook: Order {request.request_id} -> {new_state.value}"
            )
            return request
        
        return None
    
    @property
    def pending_count(self) -> int:
        """Number of orders awaiting staff action."""
        return len(self._pending)


# Global tracker instance for Saranda tenant
# In production, this would be Redis-backed for persistence
saranda_approval_tracker = SquareApprovalTracker()
