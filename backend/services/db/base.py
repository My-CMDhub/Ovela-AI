from core.config import settings
import requests
import logging

logger = logging.getLogger(__name__)

class AppwriteBase:
    def __init__(self):
        self.endpoint = settings.APPWRITE_ENDPOINT
        self.project_id = settings.APPWRITE_PROJECT_ID
        self.api_key = settings.APPWRITE_API_KEY
        self.db_id = "ovela_db"
        self.motel_db_id = "6947b8300005f5863f96"  # Ovela_Clients Database (Motel + Tenants)

    def _motel_request(self, method: str, path: str, data: dict = None, params: dict = None):
        """Helper for Motel DB requests (different from main DB)."""
        # Prefix path with Motel DB base if not full path
        if not path.startswith("/databases/"):
             path = f"/databases/{self.motel_db_id}{path}"
        return self._make_request(method, path, data, params)

    def _make_request(self, method: str, path: str, data: dict = None, params: dict = None):
        """Direct HTTP request to Appwrite API."""
        headers = {
            'Content-Type': 'application/json',
            'X-Appwrite-Project': self.project_id,
            'X-Appwrite-Key': self.api_key
        }
        url = f"{self.endpoint}{path}"
        
        # For queries, convert to proper format
        if params and 'queries' in params:
            query_list = params.pop('queries') 
            for i, q in enumerate(query_list):
                params[f'queries[{i}]'] = q
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data)
            elif method == "PATCH":
                response = requests.patch(url, headers=headers, json=data)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers)
            
            response.raise_for_status()
            # Handle 204 No Content
            if response.status_code == 204:
                return True
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code != 404:
                logger.error(f"Appwrite HTTP error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Appwrite request error: {e}")
            return None
