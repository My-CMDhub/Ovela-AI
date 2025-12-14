"""
Security utilities to prevent sensitive data exposure in logs
"""
import re
from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from core.config import settings

def sanitize_for_logging(text: str, max_length: int = 200) -> str:
    """
    Sanitize text before logging to prevent API key exposure.
    Redacts anything that looks like an API key or token.
    """
    if not text:
        return text
    
    # Truncate long strings
    if len(text) > max_length:
        text = text[:max_length] + "... (truncated)"
    
    # Redact common API key patterns
    patterns = [
        (r'sk-[a-zA-Z0-9]{20,}', '[OPENAI_KEY_REDACTED]'),  # OpenAI keys
        (r'Bearer [a-zA-Z0-9_\-\.]{20,}', 'Bearer [TOKEN_REDACTED]'),  # Bearer tokens
        (r'[A-Z0-9]{32,}', '[API_KEY_REDACTED]'),  # Generic long alphanumeric (likely API keys)
        (r'EAA[a-zA-Z0-9]{100,}', '[META_TOKEN_REDACTED]'),  # Meta access tokens
    ]
    
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text)
    
    return text


def safe_error_message(exception: Exception) -> str:
    """
    Extract a safe error message from an exception without exposing sensitive data.
    """
    error_type = type(exception).__name__
    error_msg = str(exception)[:150]  # Limit length
    
    # Sanitize the message
    safe_msg = sanitize_for_logging(error_msg)
    
    return f"{error_type}: {safe_msg}"



api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_dashboard_access(api_key: str = Security(api_key_header)):
    """
    Verify that the request has the correct internal API key.
    Used to protect dashboard endpoints from public access.
    """
    if not settings.DASHBOARD_API_KEY:
        # If no key set, allow access (or log warning)
        # For production, we should enforce this given the sensitive data
        return True
        
    if api_key != settings.DASHBOARD_API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Could not validate credentials"
        )
    return True
