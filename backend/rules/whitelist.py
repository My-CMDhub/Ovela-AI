# Whitelist for Ovela Demo System
# These numbers bypass standard rate limits.

# Format: E.164 format (e.g. +61412345678)
ADMIN_NUMBERS = {
    "+61475677771",
    "+61489055555"
    
}

def is_whitelisted(phone_number: str) -> bool:
    """Check if a phone number is authorized to bypass limits."""
    if not phone_number:
        return False
    return phone_number in ADMIN_NUMBERS
