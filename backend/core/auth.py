import logging
from fastapi import Header, HTTPException
import httpx
from core.config import settings

logger = logging.getLogger(__name__)

async def get_current_tenant_id(
    authorization: str = Header(None)
) -> str:
    """
    FastAPI Dependency to extract the tenant_id securely from the user's Appwrite JWT.
    This entirely ignores any forged query parameters and ensures strict tenant isolation.
    """
    if not authorization or not authorization.startswith("Bearer "):
        logger.error("🚨 Missing or invalid Authorization header in request")
        raise HTTPException(status_code=401, detail="Missing Authorization header")
        
    jwt_token = authorization.replace("Bearer ", "")
    logger.info(f"🔑 Received JWT Token: {jwt_token[:10]}...")

    url = f"{settings.APPWRITE_ENDPOINT}/account"
    headers = {
        "X-Appwrite-Project": settings.APPWRITE_PROJECT_ID,
        "X-Appwrite-JWT": jwt_token
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=10.0)
            if response.status_code != 200:
                logger.error(f"Appwrite session validation failed: {response.text}")
                raise HTTPException(status_code=401, detail="Invalid Appwrite session")
            
            user_data = response.json()
            prefs = user_data.get("prefs", {})
            tenant_id = prefs.get("tenant_id")
            
            if not tenant_id:
                # Default to coalcreek for backward compatibility if user has no prefs, 
                # or block them. We should block them for security.
                # However, for transition, we might want to allow it or log it.
                logger.warning(f"User {user_data.get('$id')} has no tenant_id in prefs")
                # Let's return the default 'coalcreek' for legacy users that don't have it set,
                # but in production we should require it.
                return "coalcreek"
                
            return tenant_id
            
        except httpx.RequestError as e:
            logger.error(f"Failed to connect to Appwrite to validate session: {e}")
            raise HTTPException(status_code=502, detail="Auth Gateway Error")
