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
    fulfillment_state: str = "PROPOSED"  # PROPOSED, RESERVED (approved), PREPARED, COMPLETED, CANCELED
    
    @property
    def total_dollars(self) -> float:
        return self.total_cents / 100
    
    @property
    def is_approved(self) -> bool:
        """Check if order was approved by staff (fulfillment moved past PROPOSED)."""
        return self.fulfillment_state in ("RESERVED", "PREPARED", "COMPLETED")


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
        
        # Auto-discover from API (using to_thread for sync SDK)
        import asyncio
        logger.info("Auto-discovering Square location ID...")
        try:
            response = await asyncio.to_thread(self.client.locations.list)
            
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
                    "currency": "AUD",
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
        
        # Build order dict
        order_dict = {
            "location_id": location_id,
            "reference_id": f"ovela:{call_id}",
            "line_items": line_items,
            "fulfillments": [
                {
                    "type": "PICKUP",
                    "state": "PROPOSED",
                    "pickup_details": {
                        "recipient": {
                            "display_name": customer_name,
                            "phone_number": customer_phone,
                        },
                        "note": f"🤖 Created by Ovela AI | Pickup: {pickup_time}",
                        "pickup_at": (datetime.now() + timedelta(minutes=20)).isoformat() + "Z",
                    },
                }
            ],
            "metadata": {
                "source": "ovela_ai",
                "call_id": call_id,
                "pending_approval": "true",
            },
        }
        
        logger.info(f"Creating Square order for {customer_name} (call: {call_id})")
        
        try:
            import asyncio
            response = await asyncio.to_thread(
                self.client.orders.create,
                order=order_dict,
                idempotency_key=idempotency_key
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
        """
        try:
            import asyncio
            response = await asyncio.to_thread(self.client.orders.get, order_id=order_id)
            return response.order
        except Exception as e:
            logger.error(f"Failed to fetch order {order_id}: {e}")
            return None
    
    async def get_order_state(self, order_id: str) -> Optional[str]:
        """
        Get just the state of an order.
        """
        order = await self.get_order(order_id)
        if order:
            return order.state
        return None
    
    async def search_orders_by_phone(self, phone: str, limit: int = 1) -> List[SquareOrder]:
        """
        Search for recent orders by customer phone number.
        """
        location_id = await self.get_location_id()
        try:
            import asyncio
            result = await asyncio.to_thread(
                self.client.orders.search,
                location_ids=[location_id],
                query={
                    "filter": {
                        "state_filter": {"states": ["OPEN", "COMPLETED"]}
                    },
                    "sort": {
                        "sort_field": "CREATED_AT",
                        "sort_order": "DESC"
                    }
                },
                limit=50
            )
            
            if result.is_error():
                logger.error(f"Search failed: {result.errors}")
                return []
                
            orders_data = result.body.orders if hasattr(result.body, 'orders') else []
            matches = []
            
            for o in orders_data:
                # Helper for obj/dict access
                def g(obj, k, d=None):
                    return obj.get(k, d) if isinstance(obj, dict) else getattr(obj, k, d)

                # Check fulfillment phone
                found_phone = ""
                fuls = g(o, "fulfillments") or []
                if fuls:
                    f = fuls[0]
                    pd = g(f, "pickup_details", {})
                    recip = g(pd, "recipient", {})
                    found_phone = g(recip, "phone_number", "")
                
                # Check match (last 9 digits)
                p1 = "".join(filter(str.isdigit, phone))[-9:]
                p2 = "".join(filter(str.isdigit, found_phone))[-9:]
                
                if p1 and p2 and p1 == p2:
                    tm = g(o, "total_money")
                    amt = g(tm, "amount") if tm else 0
                    
                    fulfillment_state = "PROPOSED"
                    if fuls:
                        fulfillment_state = g(fuls[0], "state", "PROPOSED")
                    
                    matches.append(SquareOrder(
                        order_id=g(o, "id"),
                        location_id=g(o, "location_id"),
                        state=g(o, "state"),
                        reference_id=g(o, "reference_id", ""),
                        created_at=datetime.fromisoformat(g(o, "created_at").replace("Z", "+00:00")),
                        total_cents=amt,
                        customer_name=g(g(g(fuls[0], "pickup_details", {}), "recipient", {}), "display_name", "Unknown") if fuls else "Unknown",
                        customer_phone=found_phone,
                        version=g(o, "version", 1),
                        fulfillment_state=fulfillment_state,
                    ))
                    if len(matches) >= limit:
                        break
            
            return matches
            
        except Exception as e:
            logger.error(f"Search orders failed: {e}")
            return []
    
    async def batch_get_orders(self, order_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Fetch multiple orders.
        """
        if not order_ids:
            return {}
        
        location_id = await self.get_location_id()
        
        try:
            import asyncio
            response = await asyncio.to_thread(
                self.client.orders.batch_get,
                location_id=location_id,
                order_ids=order_ids
            )
            
            orders = response.body.orders if hasattr(response.body, 'orders') else []
            return {order.id: order for order in orders}
        except Exception as e:
            logger.error(f"Batch order fetch error: {e}")
            return {}
    
    async def test_connection(self) -> bool:
        """
        Test the Square API connection.
        """
        try:
            location_id = await self.get_location_id()
            logger.info(f"✅ Square connection OK (location: {location_id})")
            return True
        except Exception as e:
            logger.error(f"❌ Square connection failed: {e}")
            return False

    async def search_customers(self, email: str = None, phone: str = None, limit: int = 1) -> List[Any]:
        """
        Search for a customer by email or phone.
        Uses client.customers.search(query=..., limit=...)
        """
        try:
            import asyncio
            
            query_filter = {}
            if email:
                query_filter["email_address"] = {"exact": email}
            if phone:
                query_filter["phone_number"] = {"exact": phone}
            
            if not query_filter:
                return []
                
            response = await asyncio.to_thread(
                self.client.customers.search,
                query={"filter": query_filter},
                limit=limit
            )
            
            return response.customers if hasattr(response, 'customers') else []
            
        except Exception as e:
            logger.error(f"Customer search error: {e}")
            return []

    async def get_customer_context(self, phone: str) -> Optional[Dict[str, Any]]:
        """
        Get full customer context (profile + recent orders) by phone.
        """
        # 1. Search Customer
        customers = await self.search_customers(phone=phone)
        if not customers:
            return None
            
        customer = customers[0]
        customer_id = customer.id
        
        # 2. Search Recent Orders
        location_id = await self.get_location_id()
        import asyncio
        
        try:
            orders_response = await asyncio.to_thread(
                self.client.orders.search,
                location_ids=[location_id],
                query={
                    "filter": {
                        "customer_filter": {
                            "customer_ids": [customer_id]
                        },
                         "state_filter": {
                            "states": ["OPEN", "COMPLETED"]
                        }
                    },
                    "sort": {
                        "sort_field": "CREATED_AT",
                        "sort_order": "DESC"
                    }
                },
                limit=5
            )
            
            orders = orders_response.orders if hasattr(orders_response, 'orders') else []
            if orders is None:
                orders = []
            
            # Format Orders
            formatted_orders = []
            for o in orders:
                def g(obj, k, d=None):
                    return obj.get(k, d) if isinstance(obj, dict) else getattr(obj, k, d)
                
                tm = g(o, "total_money")
                amt = g(tm, "amount") if tm else 0
                
                fuls = g(o, "fulfillments") or []
                status_msg = "Completed"
                if g(o, "state") == "OPEN":
                     if fuls:
                         status_msg = g(fuls[0], "state")
                     else:
                         status_msg = "Open"
                
                created_at = g(o, "created_at")
                
                formatted_orders.append({
                    "id": g(o, "id"),
                    "total": amt / 100.0,
                    "status": g(o, "state"),
                    "fulfillment_status": status_msg,
                    "created_at": created_at
                })
            
            return {
                "source": "square_pms",
                "customer": {
                    "id": customer.id,
                    "given_name": customer.given_name,
                    "family_name": customer.family_name,
                    "phone": customer.phone_number
                },
                "recent_orders": formatted_orders
            }
            
        except Exception as e:
            logger.error(f"Context fetch failed: {e}")
            return {
                 "source": "square_pms",
                 "customer": {
                    "id": customer.id,
                    "given_name": customer.given_name
                 }, 
                 "recent_orders": [],
                 "error": str(e)
            }
