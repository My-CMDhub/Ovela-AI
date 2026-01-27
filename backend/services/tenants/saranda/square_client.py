"""
Square API Client for Saranda Pizza Shop
=========================================
Wraps the Square Python SDK for order creation and status tracking.

Key Features:
- Auto-discovers location ID if not configured
- Creates orders with Ovela AI metadata for traceability
- Handles sandbox vs production environments
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from square import Square
from square.environment import SquareEnvironment

from .config import get_config, SarandaConfig

logger = logging.getLogger(__name__)


@dataclass
class SquareOrderItem:
    """Single item in a Square order."""
    name: str
    quantity: int = 1
    price_cents: int = 0  
    note: str = ""
    modifiers: List[str] = field(default_factory=list)


@dataclass
class SquareOrder:
    """Represents a created Square order."""
    order_id: str
    location_id: str
    state: str  # OPEN, COMPLETED, CANCELED
    reference_id: str  # Our internal call ID
    created_at: datetime
    total_cents: int
    customer_name: str
    customer_phone: str
    version: int = 1  # Square order version for updates
    
    @property
    def total_dollars(self) -> float:
        return self.total_cents / 100


class SquareClient:
    """
    Square API client for Saranda Pizza Shop.
    
    Usage:
        client = SquareClient()
        order = await client.create_pickup_order(
            customer_name="John Doe",
            customer_phone="+61412345678",
            items=[SquareOrderItem(name="Large Pepperoni", price_cents=2500)],
            pickup_time="20 minutes",
            call_id="abc123"
        )
    """
    
    def __init__(self, config: Optional[SarandaConfig] = None):
        self.config = config or get_config()
        self._client: Optional[Square] = None
        self._location_id: Optional[str] = None
    
    @property
    def client(self) -> Square:
        """Lazy-load the Square SDK client."""
        if self._client is None:
            # Convert string environment to enum
            env = (
                SquareEnvironment.SANDBOX 
                if self.config.square_environment.lower() == "sandbox" 
                else SquareEnvironment.PRODUCTION
            )
            self._client = Square(
                token=self.config.square_access_token,
                environment=env,
            )
        return self._client
    
    async def get_location_id(self) -> str:
        """
        Get the Square location ID.
        
        Uses configured value if available, otherwise auto-discovers
        from the API (uses first active location).
        """
        if self._location_id:
            return self._location_id
        
        if self.config.square_location_id:
            self._location_id = self.config.square_location_id
            return self._location_id
        
        # Auto-discover from API
        logger.info("Auto-discovering Square location ID...")
        try:
            response = self.client.locations.list()
            
            # Response has a .locations attribute with the list of location objects
            locations = response.locations if hasattr(response, 'locations') else []
            
            if locations:
                # Use first active location
                for loc in locations:
                    if loc.status == "ACTIVE":
                        self._location_id = loc.id
                        logger.info(f"Discovered location: {loc.name} ({self._location_id})")
                        return self._location_id
                
                # Fallback to first location if none active
                self._location_id = locations[0].id
                logger.warning(f"No active location found, using: {self._location_id}")
                return self._location_id
            else:
                raise ValueError("No locations found in Square account")
        except Exception as e:
            logger.error(f"Failed to discover location ID: {e}")
            raise
    
    async def create_pickup_order(
        self,
        customer_name: str,
        customer_phone: str,
        items: List[SquareOrderItem],
        pickup_time: str,
        call_id: str,
    ) -> SquareOrder:
        """
        Create a pickup order in Square with Ovela AI metadata.
        
        The order is created in OPEN state with metadata tagging it as
        AI-generated and pending staff approval.
        
        Args:
            customer_name: Customer's name
            customer_phone: Customer's phone (E.164 format preferred)
            items: List of order items
            pickup_time: Human-readable pickup time (e.g., "20 minutes", "6:30 PM")
            call_id: Our internal call ID for traceability
        
        Returns:
            SquareOrder with the created order details
        """
        location_id = await self.get_location_id()
        idempotency_key = str(uuid.uuid4())
        
        # Build line items
        line_items = []
        for item in items:
            line_item = {
                "name": item.name,
                "quantity": str(item.quantity),
                "base_price_money": {
                    "amount": item.price_cents,
                    "currency": "AUD",  # Australian dollars for Perth
                },
            }
            if item.note or item.modifiers:
                notes = []
                if item.modifiers:
                    notes.append(", ".join(item.modifiers))
                if item.note:
                    notes.append(item.note)
                line_item["note"] = " | ".join(notes)
            line_items.append(line_item)
        
        # Build the order with Ovela AI metadata
        # Using reference_id and note fields for traceability
        order_body = {
            "idempotency_key": idempotency_key,
            "order": {
                "location_id": location_id,
                "reference_id": f"ovela:{call_id}",  # Traceable reference
                "line_items": line_items,
                "fulfillments": [
                    {
                        "type": "PICKUP",
                        "state": "PROPOSED",  # Staff will update to RESERVED/PREPARED
                        "pickup_details": {
                            "recipient": {
                                "display_name": customer_name,
                                "phone_number": customer_phone,
                            },
                            "note": f"🤖 Created by Ovela AI | Pickup: {pickup_time}",
                            # Square requires pickup_at for SCHEDULED pickups
                            "pickup_at": (datetime.now() + timedelta(minutes=20)).isoformat() + "Z",
                        },
                    }
                ],
                # Metadata in the note field (visible in Square Dashboard)
                "metadata": {
                    "source": "ovela_ai",
                    "call_id": call_id,
                    "pending_approval": "true",
                },
            },
        }
        
        logger.info(f"Creating Square order for {customer_name} (call: {call_id})")
        
        try:
            response = self.client.orders.create(
                order=order_body["order"],
                idempotency_key=order_body["idempotency_key"],
            )
            
            order_data = response.order
            
            # Calculate total
            total_cents = order_data.total_money.amount if order_data.total_money else 0
            
            order = SquareOrder(
                order_id=order_data.id,
                location_id=location_id,
                state=order_data.state or "OPEN",
                reference_id=f"ovela:{call_id}",
                created_at=datetime.now(),
                total_cents=total_cents,
                customer_name=customer_name,
                customer_phone=customer_phone,
                version=order_data.version or 1,
            )
            
            logger.info(f"✅ Created Square order {order.order_id} (${order.total_dollars:.2f})")
            return order
                
        except Exception as e:
            logger.error(f"❌ Square order creation failed: {e}")
            raise
    
    async def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch an order by ID.
        
        Returns the raw Square order data, or None if not found.
        """
        try:
            response = self.client.orders.get(order_id=order_id)
            return response.order
        except Exception as e:
            logger.error(f"Failed to fetch order {order_id}: {e}")
            return None
    
    async def get_order_state(self, order_id: str) -> Optional[str]:
        """
        Get just the state of an order (OPEN, COMPLETED, CANCELED).
        
        Returns None if order not found.
        """
        order = await self.get_order(order_id)
        if order:
            return order.state
        return None
    
    async def batch_get_orders(self, order_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Fetch multiple orders in a single API call.
        
        Returns a dict mapping order_id -> order data.
        """
        if not order_ids:
            return {}
        
        location_id = await self.get_location_id()
        
        try:
            response = self.client.orders.batch_get(
                location_id=location_id,
                order_ids=order_ids,
            )
            
            orders = response.orders if hasattr(response, 'orders') else []
            return {order.id: order for order in orders}
        except Exception as e:
            logger.error(f"Batch order fetch error: {e}")
            return {}
    
    async def test_connection(self) -> bool:
        """
        Test the Square API connection.
        
        Returns True if connection is successful.
        """
        try:
            location_id = await self.get_location_id()
            logger.info(f"✅ Square connection OK (location: {location_id})")
            return True
        except Exception as e:
            logger.error(f"❌ Square connection failed: {e}")
            return False
