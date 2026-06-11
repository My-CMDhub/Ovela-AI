import logging

logger = logging.getLogger(__name__)

def mask_phone(phone: str) -> str:
    """
    Mask phone number for logging (e.g. +614...123).
    Safe for production logs.
    """
    if not phone:
        return "None"
    
    phone_str = str(phone).strip()
    if len(phone_str) < 8:
        return "..."
    
    # Mask middle digits
    return f"{phone_str[:4]}...{phone_str[-3:]}"

def mask_email(email: str) -> str:
    """
    Mask email for logging (e.g. j***@example.com).
    """
    if not email or "@" not in email:
        return "..."
    
    parts = email.split("@")
    name = parts[0]
    domain = parts[1]
    
    if len(name) <= 1:
        return f"*@{domain}"
    
    return f"{name[0]}***@{domain}"
