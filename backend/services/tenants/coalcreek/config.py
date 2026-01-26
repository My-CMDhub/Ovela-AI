"""
Coal Creek Motel - Configuration Constants
==========================================
Tenant-specific configuration for Coal Creek Motel.
"""

COALCREEK_CONFIG = {
    # Identity
    "tenant_id": "coalcreek",
    "name": "Coal Creek Motel",
    "short_name": "Coal Creek",
    
    # Contact
    "phone": "0492 897 718",
    "email": "coalcreekmotel@gmail.com",
    "address": "8444 South Gippsland Highway, Korumburra VIC 3950",
    "website": "coalcreekmotel.com.au",
    
    # Brand Colors
    "primary_color": "#2C5F2D",   # Rustic Green
    "secondary_color": "#97BC62", # Light Green
    "accent_color": "#ffffff",
    
    # Placeholders (replace when client provides)
    "logo_url": "[LOGO_URL_PLACEHOLDER]",
    "staff_email": "staff@placeholder.com",
    
    # Operations
    "timezone": "Australia/Melbourne",
    "check_in_time": "2:00 PM",
    "check_out_time": "10:00 AM",
    "reception_hours": "8:00am - 8:00pm",
    
    # Features
    "has_stripe": True,
    "has_voice_agent": True,
    "booking_strategy": "read_only_soft_hold",
    
    # PMS Integration (Update247)
    "pms_provider": "update247",
    "pms_api_key": None,  # Set via environment: COALCREEK_PMS_API_KEY
    "pms_property_id": None,  # Set via environment: COALCREEK_PMS_PROPERTY_ID
    "pms_sync_enabled": False,  # Enable when API key obtained
    "pms_sync_interval_mins": 30,  # Background sync frequency
}

# Staff phone for transfers
STAFF_PHONE = "+61492897718"

# Collection IDs
TRANSCRIPT_COLLECTION = "call_transcripts_coalcreek"
