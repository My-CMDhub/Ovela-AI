"""
PMS (Property Management System) Service Package
=================================================
One-way sync integration with external PMS providers.

Supports:
- Update247 (Coal Creek Motel)
- Extensible for other providers
"""

from .base import PMSClient, AvailabilityResult, BookingRecord, RoomStatus
from .update247 import Update247Client

# Client registry by tenant
_clients = {}


def get_pms_client(tenant_id: str) -> PMSClient:
    """
    Get the PMS client for a tenant.
    
    Returns None if not configured or tenant not found.
    """
    if tenant_id in _clients:
        return _clients[tenant_id]
    
    # Initialize client based on tenant config
    if tenant_id == "coalcreek":
        from services.tenants.coalcreek.config import COALCREEK_CONFIG
        
        api_key = COALCREEK_CONFIG.get("pms_api_key")
        property_id = COALCREEK_CONFIG.get("pms_property_id")
        
        if api_key and property_id:
            client = Update247Client(api_key=api_key, property_id=property_id)
            _clients[tenant_id] = client
            return client
    
    return None


def is_pms_configured(tenant_id: str) -> bool:
    """Check if PMS is configured for a tenant."""
    client = get_pms_client(tenant_id)
    return client is not None and client.is_configured()


__all__ = [
    "PMSClient",
    "AvailabilityResult", 
    "BookingRecord",
    "RoomStatus",
    "Update247Client",
    "get_pms_client",
    "is_pms_configured",
]
