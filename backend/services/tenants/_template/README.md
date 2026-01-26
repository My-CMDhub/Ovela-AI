# New Tenant Template

This directory serves as a template for adding new tenants to the Ovela platform.

## Quick Start

1. **Copy this folder** to `services/tenants/your_tenant_name/`
2. **Create these files:**
   - `__init__.py` - Exports
   - `config.py` - Tenant constants (colors, contact, etc.)
   - `email.py` - Branded email service (extends `CoalCreekEmailService`)
   - `stripe.py` - Payment service (if applicable)

3. **Register in `services/tenants/__init__.py`:**
```python
REGISTERED_TENANTS = {
    "coalcreek": {...},
    "your_tenant": {
        "name": "Your Business Name",
        "module": "services.tenants.your_tenant",
        "active": True
    }
}
```

4. **Create tenant in Appwrite:**
   - Add entry to `Tenants` collection
   - Create `Call_Transcripts_YourTenant` collection

5. **Update appwrite.py:**
```python
TENANT_TRANSCRIPT_COLLECTIONS = {
    "coalcreek": "call_transcripts_coalcreek",
    "your_tenant": "call_transcripts_your_tenant",
}
```

## Files Reference

| File | Purpose |
|------|---------|
| `config.py` | Colors, contact info, feature flags |
| `email.py` | Branded email templates |
| `stripe.py` | Payment link generation |

## Example Config

```python
YOUR_TENANT_CONFIG = {
    "tenant_id": "your_tenant",
    "name": "Your Business Name",
    "primary_color": "#000000",
    "phone": "0400 000 000",
    "has_stripe": True,
    "booking_strategy": "read_only_soft_hold",
}
```
