"""
Tenant Services Package
=======================
Multi-tenant service implementations.

Each tenant has its own subfolder with:
- email.py: Tenant-branded email templates
- stripe.py: Payment configuration (if applicable)
- config.py: Tenant-specific constants

Usage:
    from services.tenants import get_tenant_service
    email_svc = get_tenant_service('coalcreek', 'email')
"""

from typing import Any

# Tenant registry
REGISTERED_TENANTS = {
    "coalcreek": {
        "name": "Coal Creek Motel",
        "module": "services.tenants.coalcreek",
        "active": True
    },
    # Future tenants (add as needed):
}


def get_tenant_module(tenant_id: str):
    """Get the tenant module for a given tenant_id."""
    if tenant_id not in REGISTERED_TENANTS:
        raise ValueError(f"Unknown tenant: {tenant_id}")
    
    tenant = REGISTERED_TENANTS[tenant_id]
    if not tenant.get("active", False):
        raise ValueError(f"Tenant {tenant_id} is not active")
    
    return tenant["module"]


def get_tenant_email_service(tenant_id: str):
    """Get the email service for a tenant."""
    if tenant_id == "coalcreek":
        from services.tenants.coalcreek.email import CoalCreekEmailService
        return CoalCreekEmailService()
    
    # Default fallback
    from services.email import EmailService
    return EmailService()


def get_tenant_stripe_service(tenant_id: str):
    """Get the Stripe service for a tenant (if configured)."""
    if tenant_id == "coalcreek":
        from services.tenants.coalcreek.stripe import CoalCreekStripeService
        return CoalCreekStripeService()
    
    return None
