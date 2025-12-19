"""
Customer Service for Smart Memory & Abuse Prevention
Handles user profiles, tiered memory context, and cooldown logic.
"""
from appwrite.client import Client
from appwrite.id import ID
from appwrite.exception import AppwriteException
from core.config import settings
from datetime import datetime, timedelta
import json
import logging
import requests

logger = logging.getLogger(__name__)

class CustomerService:
    def __init__(self):
        self.endpoint = settings.APPWRITE_ENDPOINT
        self.project_id = settings.APPWRITE_PROJECT_ID
        self.api_key = settings.APPWRITE_API_KEY
        self.db_id = "ovela_db"
        self.collection_id = "customers"
        self.LOCKOUT_THRESHOLD = 3
        self.LOCKOUT_DURATION_HOURS = 2

    def _make_request(self, method: str, path: str, data: dict = None, params: dict = None):
        """Direct HTTP request to Appwrite API to avoid SDK issues."""
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
                # Don't wrap strings - they're already formatted like 'equal("field", "value")'
                params[f'queries[{i}]'] = q
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data)
            elif method == "PATCH":
                response = requests.patch(url, headers=headers, json=data)
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            # Don't log 404 as errors - it just means document doesn't exist
            if e.response.status_code != 404:
                logger.error(f"Appwrite HTTP error: {e}")
            return None
        except Exception as e:
            logger.error(f"Appwrite request error: {e}")
            return None

    def get_or_create_customer(self, whatsapp_id: str, business_id: str):
        """
        Get customer profile or create new one.
        Uses direct HTTP to avoid SDK query parameter issues.
        """
        try:
            # FIX: Use string format, not dictionary
            queries = [
                f'equal("whatsapp_id", "{whatsapp_id}")',
                f'equal("business_id", "{business_id}")'
            ]
            
            params = {'queries': queries}
            
            # List documents
            result = self._make_request(
                "GET",
                f"/databases/{self.db_id}/collections/{self.collection_id}/documents",
                params=params
            )
            
            if result and result.get('documents') and len(result['documents']) > 0:
                logger.info(f"Found existing customer for {whatsapp_id}")
                return result['documents'][0]
            
            # Create new customer
            logger.info(f"Creating new customer for {whatsapp_id}")
            doc_id = ID.unique()
            data = {
                "whatsapp_id": whatsapp_id,
                "business_id": business_id,
                "violation_count": 0,
                "profile_summary": "New customer."
            }
            
            new_doc = self._make_request(
                "POST",
                f"/databases/{self.db_id}/collections/{self.collection_id}/documents",
                data={
                    "documentId": doc_id,
                    "data": data
                }
            )
            
            return new_doc
                
        except Exception as e:
            logger.error(f"Error managing customer: {e}")
            return None

    def get_customer(self, whatsapp_id: str):
        """Get customer by stats (wrapper for get_or_create without creating if possible, or just query)."""
        try:
            # FIX: Use string format
            queries = [f'equal("whatsapp_id", "{whatsapp_id}")']
            
            result = self._make_request(
                "GET",
                f"/databases/{self.db_id}/collections/{self.collection_id}/documents",
                params={'queries': queries}
            )
            
            if result and result.get('documents') and len(result['documents']) > 0:
                return result['documents'][0]
            return None
        except Exception as e:
            logger.error(f"Error getting customer: {e}")
            return None

    def check_cooldown(self, customer) -> bool:
        """Check if customer is currently in cooldown mode."""
        if not customer:
            return False
            
        cooldown_until = customer.get("cooldown_until")
        if cooldown_until:
            try:
                until_dt = datetime.fromisoformat(cooldown_until.replace("Z", "+00:00"))
                if datetime.now().astimezone() < until_dt:
                    return True
            except Exception as e:
                logger.error(f"Error parsing cooldown: {e}")
        
        return False

    def report_violation(self, customer_id: str, current_count: int):
        """Increment violation count and trigger cooldown if threshold reached."""
        new_count = current_count + 1
        data = {"violation_count": new_count}
        
        if new_count >= self.LOCKOUT_THRESHOLD:
            cooldown_time = datetime.now() + timedelta(hours=self.LOCKOUT_DURATION_HOURS)
            data["cooldown_until"] = cooldown_time.isoformat()
            logger.warning(f"Customer {customer_id} triggered cooldown until {data['cooldown_until']}")
            data["violation_count"] = 0

        try:
            self._make_request(
                "PATCH",
                f"/databases/{self.db_id}/collections/{self.collection_id}/documents/{customer_id}",
                data={"data": data}
            )
            return new_count >= self.LOCKOUT_THRESHOLD
        except Exception as e:
            logger.error(f"Error reporting violation: {e}")
            return False

    def get_customer_context(self, customer) -> str:
        """Build a concise memory context string for the AI."""
        if not customer:
            return ""
            
        summary = customer.get("profile_summary", "")
        name = customer.get("name")
        email = customer.get("email")
        
        # Only include context if we have real data
        if not name and not email:
            return ""
        
        context = "## KNOWN CUSTOMER INFO (Use this - don't ask again!):\n"
        if name:
            context += f"- Name: {name}\n"
        if email:
            context += f"- Email: {email}\n"
        if summary and summary != "New customer.":
            context += f"- History: {summary}\n"
        
        prefs_json = customer.get("preferences_json")
        if prefs_json:
            try:
                prefs = json.loads(prefs_json)
                context += f"- Preferences: {', '.join(f'{k}: {v}' for k,v in prefs.items())}\n"
            except:
                pass
                
        return context

    def update_profile(self, customer_id: str, name: str = None, email: str = None, summary: str = None):
        """Update customer details and memory summary."""
        data = {}
        if name: data["name"] = name
        if email: data["email"] = email
        if summary: data["profile_summary"] = summary
        
        if data:
            try:
                self._make_request(
                    "PATCH",
                    f"/databases/{self.db_id}/collections/{self.collection_id}/documents/{customer_id}",
                    data={"data": data}
                )
            except Exception as e:
                logger.error(f"Error updating profile: {e}")

customer_service = CustomerService()
