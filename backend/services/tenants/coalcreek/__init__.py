"""
Coal Creek Motel - Tenant Package
=================================
All Coal Creek specific services.

Usage:
    from services.tenants.coalcreek import email_service, stripe_service
"""

from .email import CoalCreekEmailService, coalcreek_email_service
from .stripe import CoalCreekStripeService, coalcreek_stripe_service
from .config import COALCREEK_CONFIG

__all__ = [
    "CoalCreekEmailService",
    "coalcreek_email_service",
    "CoalCreekStripeService", 
    "coalcreek_stripe_service",
    "COALCREEK_CONFIG"
]
