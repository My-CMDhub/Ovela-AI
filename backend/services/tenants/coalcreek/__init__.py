"""
Coal Creek Motel - Tenant Package
=================================
All Coal Creek specific services.

Usage:
    from services.tenants.coalcreek import stripe_service
"""

from .stripe import CoalCreekStripeService, coalcreek_stripe_service
from .config import COALCREEK_CONFIG

__all__ = [
    "CoalCreekStripeService", 
    "coalcreek_stripe_service",
    "COALCREEK_CONFIG"
]
