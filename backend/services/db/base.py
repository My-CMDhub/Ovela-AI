from core.config import settings
import httpx
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

from appwrite.query import Query as AppwriteQuery

class AppwriteBase:
    Query = AppwriteQuery
    
    def __init__(self):
        self.endpoint = settings.APPWRITE_ENDPOINT
        self.project_id = settings.APPWRITE_PROJECT_ID
        self.api_key = settings.APPWRITE_API_KEY
        self.db_id = "6947b8300005f5863f96" # PRODUCTION DB: Ovela_Clients
        self.motel_db_id = "6947b8300005f5863f96"  # Ovela_Clients Database (Motel + Tenants)
        self.timeout = httpx.Timeout(15.0, connect=5.0)

    async def _motel_request(self, method: str, path: str, data: dict = None, params: dict = None):
        """Helper for Motel DB requests (different from main DB)."""
        # Prefix path with Motel DB base if not full path
        if not path.startswith("/databases/"):
             path = f"/databases/{self.motel_db_id}{path}"
        return await self._make_request(method, path, data, params)

    async def _make_request(self, method: str, path: str, data: dict = None, params: dict = None):
        """Direct Async HTTP request to Appwrite API."""
        headers = {
            'Content-Type': 'application/json',
            'X-Appwrite-Project': self.project_id,
            'X-Appwrite-Key': self.api_key
        }
        url = f"{self.endpoint}{path}"
        
        # Robust serialization for indexed queries
        if params and 'queries' in params:
            query_list = params.pop('queries')
            new_params = params.copy()
            for i, q in enumerate(query_list):
                new_params[f'queries[{i}]'] = str(q)
            params = new_params
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if method == "GET":
                    response = await client.get(url, headers=headers, params=params)
                elif method == "POST":
                    response = await client.post(url, headers=headers, json=data)
                elif method == "PATCH":
                    response = await client.patch(url, headers=headers, json=data)
                elif method == "DELETE":
                    response = await client.delete(url, headers=headers)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                
                response.raise_for_status()
                
                if response.status_code == 204:
                    return True
                    
                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 404:
                logger.error(f"Appwrite HTTP error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Appwrite request error: {e}")
            return None
