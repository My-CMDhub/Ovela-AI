"""
Magic Links Service
Generates and verifies signed JWT tokens for email-based actions.
"""
import jwt
import logging
from datetime import datetime, timedelta
from core.config import settings

logger = logging.getLogger(__name__)

# Use a secret key for signing (falls back to Appwrite API key if not set)
SECRET_KEY = getattr(settings, 'MAGIC_LINK_SECRET', None) or settings.APPWRITE_API_KEY or "default-secret-key"
ALGORITHM = "HS256"
DEFAULT_EXPIRY_HOURS = 48


def generate_action_token(
    notification_id: str, 
    action: str, 
    expiry_hours: int = DEFAULT_EXPIRY_HOURS
) -> str:
    """
    Generate a signed JWT token for a magic link action.
    
    Args:
        notification_id: The ID of the notification/booking to act on
        action: The action to perform (complete, dismiss, approve, reject, update)
        expiry_hours: Hours until token expires (default 48)
    
    Returns:
        Signed JWT token string
    """
    payload = {
        "notification_id": notification_id,
        "action": action,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=expiry_hours)
    }
    
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    logger.info(f"Generated magic link token for {action} on {notification_id[:8]}...")
    return token


def verify_action_token(token: str) -> tuple[bool, dict, str]:
    """
    Verify a magic link token.
    
    Args:
        token: The JWT token to verify
    
    Returns:
        Tuple of (is_valid, payload, error_message)
        - is_valid: True if token is valid and not expired
        - payload: The decoded payload if valid, empty dict if invalid
        - error_message: Error description if invalid, empty string if valid
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Validate required fields
        if not payload.get("notification_id") or not payload.get("action"):
            return False, {}, "Invalid token: missing required fields"
        
        return True, payload, ""
        
    except jwt.ExpiredSignatureError:
        logger.warning("Magic link token expired")
        return False, {}, "This link has expired. Please check your dashboard instead."
    
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid magic link token: {e}")
        return False, {}, "Invalid or corrupted link. Please check your dashboard."
    
    except Exception as e:
        logger.error(f"Error verifying magic link: {e}")
        return False, {}, "An error occurred. Please try again or use the dashboard."


def generate_action_url(notification_id: str, action: str, base_url: str = None) -> str:
    """
    Generate a complete magic link URL for an action.
    
    Args:
        notification_id: The notification ID
        action: The action (complete, dismiss, approve, reject)
        base_url: Optional base URL (defaults to Heroku app URL)
    
    Returns:
        Complete URL with token
    """
    if not base_url:
        base_url = "https://ovela-12c561a30285.herokuapp.com"
    
    token = generate_action_token(notification_id, action)
    return f"{base_url}/api/actions/{action}?token={token}"
