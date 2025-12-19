"""
Booking Storage Service
Handles storing and retrieving bookings in Appwrite for AI lookup.
Also implements rate limiting for booking operations.
"""
from core.config import settings
from appwrite.id import ID
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json
import logging
import requests
from rules.whitelist import is_whitelisted

logger = logging.getLogger(__name__)

MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")

# Rate limiting thresholds
MAX_BOOKINGS_PER_HOUR = 3
MAX_RESCHEDULES_PER_DAY = 5
MAX_CANCELS_PER_DAY = 3


class BookingService:
    def __init__(self):
        self.endpoint = settings.APPWRITE_ENDPOINT
        self.project_id = settings.APPWRITE_PROJECT_ID
        self.api_key = settings.APPWRITE_API_KEY
        self.db_id = "ovela_db"
        self.collection_id = "bookings"
    
    def _make_request(self, method: str, path: str, data: dict = None, params: dict = None):
        """Direct HTTP request to Appwrite API."""
        headers = {
            'Content-Type': 'application/json',
            'X-Appwrite-Project': self.project_id,
            'X-Appwrite-Key': self.api_key
        }
        url = f"{self.endpoint}{path}"
        
        if params and 'queries' in params:
            query_list = params['queries']
            params = {}
            for i, q in enumerate(query_list):
                params[f'queries[{i}]'] = json.dumps(q) if isinstance(q, dict) else q
        
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
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code != 404:
                logger.error(f"Appwrite HTTP error: {e}")
            return None
        except Exception as e:
            logger.error(f"Appwrite request error: {e}")
            return None

    def save_booking(
        self,
        customer_phone: str,
        customer_name: str,
        customer_email: str,
        service_name: str,
        booking_date: str,
        booking_time: str,
        source: str = "whatsapp",
        notes: str = ""
    ) -> dict:
        """
        Save a booking to Appwrite (native system, no Cal.com).
        """
        try:
            doc_id = ID.unique()
            data = {
                "customer_phone": customer_phone,
                "customer_name": customer_name,
                "customer_email": customer_email,
                "service_name": service_name,
                "booking_date": booking_date,
                "booking_time": booking_time,
                "duration_minutes": 60,
                "status": "confirmed",
                "source": source,
                "notes": notes,
                "created_at": datetime.now(MELBOURNE_TZ).isoformat()
            }
            
            result = self._make_request(
                "POST",
                f"/databases/{self.db_id}/collections/{self.collection_id}/documents",
                data={
                    "documentId": doc_id,
                    "data": data
                }
            )
            
            if result:
                logger.info(f"Saved booking for {customer_phone} on {booking_date} at {booking_time}")
                return result
            return None
            
        except Exception as e:
            logger.error(f"Error saving booking: {e}")
            return None
    
    def get_customer_bookings(self, customer_phone: str, status: str = "confirmed") -> list:
        """
        Get all bookings for a customer by phone number.
        Uses in-memory filtering for reliability.
        """
        try:
            result = self._make_request(
                "GET",
                f"/databases/{self.db_id}/collections/{self.collection_id}/documents"
            )
            
            if result and result.get('documents'):
                # Filter in-memory for reliability
                bookings = [
                    b for b in result['documents']
                    if b.get('customer_phone') == customer_phone and b.get('status') == status
                ]
                return bookings
            return []
            
        except Exception as e:
            logger.error(f"Error getting bookings: {e}")
            return []
    
    def update_booking_status(self, doc_id: str, status: str, new_start_time: str = None) -> bool:
        """Update booking status (e.g., rescheduled, cancelled)."""
        try:
            data = {"status": status}
            if new_start_time:
                data["start_time"] = new_start_time
            
            result = self._make_request(
                "PATCH",
                f"/databases/{self.db_id}/collections/{self.collection_id}/documents/{doc_id}",
                data={"data": data}
            )
            return result is not None
        except Exception as e:
            logger.error(f"Error updating booking: {e}")
            return False
    
    def check_rate_limit(self, whatsapp_id: str, operation: str) -> tuple:
        """
        Check if user has exceeded rate limits for booking operations.
        Returns (allowed: bool, message: str)
        """
        try:
            # Get recent bookings for this user
            now = datetime.now(MELBOURNE_TZ)
            one_hour_ago = now - timedelta(hours=1)
            one_day_ago = now - timedelta(days=1)
            
            result = self._make_request(
                "GET",
                f"/databases/{self.db_id}/collections/{self.collection_id}/documents"
            )
            
            if not result or not result.get('documents'):
                return (True, "")
            
            # Check whitelist
            if is_whitelisted(whatsapp_id):
                 return (True, "")

            bookings = result['documents']
            
            # Count operations in time windows
            bookings_last_hour = 0
            reschedules_today = 0
            cancels_today = 0
            
            for b in bookings:
                created_str = b.get('created_at') or b.get('$createdAt', '')
                if not created_str:
                    continue
                    
                try:
                    created = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
                    created = created.astimezone(MELBOURNE_TZ)
                    
                    if created > one_hour_ago:
                        bookings_last_hour += 1
                    
                    if created > one_day_ago:
                        status = b.get('status', '')
                        if status == 'rescheduled':
                            reschedules_today += 1
                        elif status == 'cancelled':
                            cancels_today += 1
                except:
                    continue
            
            # Check limits based on operation
            if operation == 'book':
                if bookings_last_hour >= MAX_BOOKINGS_PER_HOUR:
                    return (False, f"You've made {MAX_BOOKINGS_PER_HOUR} bookings in the last hour. Please wait before booking again.")
            elif operation == 'reschedule':
                if reschedules_today >= MAX_RESCHEDULES_PER_DAY:
                    return (False, f"You've rescheduled {MAX_RESCHEDULES_PER_DAY} times today. Please try again tomorrow.")
            elif operation == 'cancel':
                if cancels_today >= MAX_CANCELS_PER_DAY:
                    return (False, f"You've cancelled {MAX_CANCELS_PER_DAY} times today. Please try again tomorrow.")
            
            return (True, "")
            
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            # On error, allow the operation (fail open for good UX)
            return (True, "")
    
    def format_bookings_for_ai(self, bookings: list) -> str:
        """Format bookings list for AI context."""
        if not bookings:
            return "No upcoming bookings found."
        
        lines = []
        for b in bookings:
            date = b.get('booking_date', 'Unknown')
            time = b.get('booking_time', '')
            service = b.get('service_name', 'Appointment')
            booking_id = b.get('$id', 'N/A')
            # Format readable time
            try:
                dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
                readable_time = dt.strftime("%A %d %b at %I:%M %p")
            except:
                readable_time = f"{date} {time}"
            
            lines.append(f"- {service} on {readable_time} (ID: {booking_id})")
        
        return "Your upcoming bookings:\n" + "\n".join(lines)


booking_service = BookingService()
