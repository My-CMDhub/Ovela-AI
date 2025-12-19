from appwrite.id import ID
from core.config import settings
import json
from datetime import datetime, timedelta
import requests
import logging
from zoneinfo import ZoneInfo
from rules.whitelist import is_whitelisted

MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")

logger = logging.getLogger(__name__)

class AppwriteService:
    def __init__(self):
        self.endpoint = settings.APPWRITE_ENDPOINT
        self.project_id = settings.APPWRITE_PROJECT_ID
        self.api_key = settings.APPWRITE_API_KEY
        self.db_id = "ovela_db"

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
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code != 404:
                logger.error(f"Appwrite HTTP error: {e}")
            return None
        except Exception as e:
            logger.error(f"Appwrite request error: {e}")
            return None

    def get_business(self, whatsapp_business_id: str):
        """Fetch business settings by WhatsApp Business ID."""
        try:
            queries = [f'equal("whatsapp_business_id", "{whatsapp_business_id}")']
            params = {'queries': queries}
            
            result = self._make_request(
                "GET",
                f"/databases/{self.db_id}/collections/businesses/documents",
                params=params
            )
            
            if result and result.get('documents'):
                return result['documents'][0]
            return None
        except Exception as e:
            logger.error(f"Error fetching business: {e}")
            return None

    def get_or_create_conversation(self, whatsapp_id: str, business_id: str):
        """Get existing conversation or create a new one."""
        try:
            queries = [
                f'equal("whatsapp_id", "{whatsapp_id}")',
                f'equal("business_id", "{business_id}")'
            ]
            params = {'queries': queries}
            
            result = self._make_request(
                "GET",
                f"/databases/{self.db_id}/collections/conversations/documents",
                params=params
            )
            
            if result and result.get('documents') and len(result['documents']) > 0:
                logger.info(f"Found existing conversation for {whatsapp_id}")
                return result['documents'][0]
            
            # Create new
            logger.info(f"Creating new conversation for {whatsapp_id}")
            doc_id = ID.unique()
            data = {
                "whatsapp_id": whatsapp_id,
                "business_id": business_id,
                "status": "active",
                "history": "[]"
            }
            
            new_doc = self._make_request(
                "POST",
                f"/databases/{self.db_id}/collections/conversations/documents",
                data={
                    "documentId": doc_id,
                    "data": data
                }
            )
            
            return new_doc
        except Exception as e:
            logger.error(f"Error managing conversation: {e}")
            return None

    def append_message(self, conversation_id: str, role: str, content: str, history_json: str):
        """Append a message to the conversation history."""
        try:
            history = json.loads(history_json) if history_json else []
            history.append({"role": role, "content": content, "timestamp": str(datetime.now())})
            
            # Keep only last 20 messages
            if len(history) > 20:
                history = history[-20:]

            self._make_request(
                "PATCH",
                f"/databases/{self.db_id}/collections/conversations/documents/{conversation_id}",
                data={
                    "data": {
                        "history": json.dumps(history),
                        "last_message": content
                    }
                }
            )
        except Exception as e:
            logger.error(f"Error appending message: {e}")

    # ==================== TOKEN RATE LIMITING ====================
    
    DAILY_TOKEN_LIMIT = 3000  # Max tokens per day per user
    TOKEN_WARNING_THRESHOLD = 0.70  # Warn at 70%
    COOLDOWN_HOURS = 5  # Hours until tokens reset
    
    DEMO_LIMIT_HOURS = 24 # One demo per day
    
    def check_token_limit(self, conversation: dict, business_phone: str = "the business") -> tuple:
        """
        Check if user has exceeded daily token limit.
        Returns: (can_proceed: bool, status: str, message: str or None)
        status: 'ok', 'warning', 'blocked'
        """
        try:
            # Check whitelist first
            if is_whitelisted(conversation.get("whatsapp_id")):
                logger.info(f" whitelist bypass for {conversation.get('whatsapp_id')}")
                return (True, "ok", None)

            tokens_used = conversation.get("tokens_used_today", 0) or 0
            reset_at_str = conversation.get("token_reset_at")
            
            # Check if we need to reset (5 hours passed)
            if reset_at_str:
                try:
                    reset_at = datetime.fromisoformat(reset_at_str.replace("Z", "+00:00"))
                    if datetime.now(MELBOURNE_TZ) >= reset_at:
                        # Reset tokens
                        tokens_used = 0
                except:
                    pass
            
            usage_ratio = tokens_used / self.DAILY_TOKEN_LIMIT if self.DAILY_TOKEN_LIMIT > 0 else 0
            
            if tokens_used >= self.DAILY_TOKEN_LIMIT:
                # Blocked - calculate when reset happens
                if reset_at_str:
                    try:
                        reset_at = datetime.fromisoformat(reset_at_str.replace("Z", "+00:00"))
                        reset_time = reset_at.strftime("%I:%M %p")
                    except:
                        reset_time = "a few hours"
                else:
                    reset_time = "a few hours"
                
                message = f"You've reached your chat limit for today. Your limit will refresh at {reset_time}. Please call {business_phone} for urgent matters. All your booking details are safely saved! 💜"
                return (False, "blocked", message)
            
            elif usage_ratio >= self.TOKEN_WARNING_THRESHOLD:
                # Warning - approaching limit
                remaining = self.DAILY_TOKEN_LIMIT - tokens_used
                message = f"Just a heads up — you're approaching your chat limit for today ({remaining} tokens remaining). If you need more help, feel free to call {business_phone} directly. Your limit will refresh in a few hours! 💜"
                return (True, "warning", message)
            
            else:
                # OK - proceed normally
                return (True, "ok", None)
                
        except Exception as e:
            logger.error(f"Error checking token limit: {e}")
            return (True, "ok", None)  # Fail open
    
    def update_token_usage(self, conversation_id: str, tokens_used: int, current_tokens: int = 0):
        """
        Update token usage for a conversation.
        Sets reset time if first usage of the day.
        """
        try:
            new_total = (current_tokens or 0) + tokens_used
            
            # Set reset time if this is the start of a new period
            reset_at = (datetime.now(MELBOURNE_TZ) + timedelta(hours=self.COOLDOWN_HOURS)).isoformat()
            
            self._make_request(
                "PATCH",
                f"/databases/{self.db_id}/collections/conversations/documents/{conversation_id}",
                data={
                    "data": {
                        "tokens_used_today": new_total,
                        "token_reset_at": reset_at
                    }
                }
            )
            logger.info(f"Updated token usage: {new_total} tokens used")
            return new_total
        except Exception as e:
            logger.error(f"Error updating token usage: {e}")
            return current_tokens

    def get_business_by_id(self, business_id: str):
        """Get business settings by document ID."""
        try:
            result = self._make_request(
                "GET",
                f"/databases/{self.db_id}/collections/businesses/documents/{business_id}"
            )
            return result
        except Exception as e:
            logger.error(f"Error fetching business by ID: {e}")
            return None

    def upsert_business(self, business_id: str, name: str, industry: str, settings_json: str = "{}", owner_email: str = "", business_phone: str = ""):
        """Create or update business settings."""
        try:
            # Try to get existing business
            existing = self.get_business_by_id(business_id)
            
            data = {
                "name": name,
                "industry": industry,
                "whatsapp_business_id": business_id,  # Use same ID for lookup
                "system_prompt_override": settings_json,  # Store all settings as JSON
                "owner_email": owner_email,  # Also store separately for quick access
                "business_phone": business_phone  # Also store separately for quick access
            }
            
            if existing:
                # Update existing
                result = self._make_request(
                    "PATCH",
                    f"/databases/{self.db_id}/collections/businesses/documents/{business_id}",
                    data={"data": data}
                )
            else:
                # Create new
                result = self._make_request(
                    "POST",
                    f"/databases/{self.db_id}/collections/businesses/documents",
                    data={
                        "documentId": business_id,
                        "data": data
                    }
                )
            
            return result
        except Exception as e:
            logger.error(f"Error upserting business: {e}")
            return None

    def get_all_settings(self):
        """Get settings for the default business (for AI prompt building)."""
        business = self.get_business_by_id("default_business")
        if business:
            # Parse the system_prompt_override as JSON settings
            try:
                settings = json.loads(business.get("system_prompt_override", "{}"))
                return {
                    "business_name": business.get("name", ""),
                    "industry": business.get("industry", "beauty"),
                    **settings
                }
            except:
                return {"business_name": business.get("name", ""), "industry": business.get("industry", "beauty")}
        return None

    def create_booking_request(self, request_data: dict):
        """Create a new booking request (for appointment-only mode)."""
        from appwrite.id import ID
        try:
            doc_id = ID.unique()
            result = self._make_request(
                "POST",
                f"/databases/{self.db_id}/collections/booking_requests/documents",
                data={
                    "documentId": doc_id,
                    "data": request_data
                }
            )
            logger.info(f"Created booking request: {doc_id}")
            return result
        except Exception as e:
            logger.error(f"Error creating booking request: {e}")
            return None

    def get_booking_requests(self, status: str = None):
        """Get booking requests, optionally filtered by status."""
        try:
            path = f"/databases/{self.db_id}/collections/booking_requests/documents"
            params = {}
            
            if status:
                # FIX: Send a String, not a Dict
                params["queries"] = [f'equal("status", "{status}")']
            
            result = self._make_request("GET", path, params=params)
            return result.get("documents", []) if result else []
        except Exception as e:
            logger.error(f"Error fetching booking requests: {e}")
            return []

    def update_booking_request(self, request_id: str, data: dict):
        """Update a booking request (approve/reject)."""
        try:
            result = self._make_request(
                "PATCH",
                f"/databases/{self.db_id}/collections/booking_requests/documents/{request_id}",
                data={"data": data}
            )
            return result
        except Exception as e:
            logger.error(f"Error updating booking request: {e}")
            return None
    
    def get_booking_requests_by_phone(self, customer_phone: str):
        """Get booking requests for a specific customer by phone number."""
        try:
            path = f"/databases/{self.db_id}/collections/booking_requests/documents"
            result = self._make_request("GET", path)
            
            if result and result.get("documents"):
                # Filter in-memory for reliability
                return [
                    r for r in result["documents"]
                    if r.get("customer_phone") == customer_phone
                ]
            return []
        except Exception as e:
            logger.error(f"Error fetching requests by phone: {e}")
            return []

    # ============ BOOKINGS (Confirmed Appointments) ============
    
    def create_booking(self, booking_data: dict):
        """Create a confirmed booking."""
        from appwrite.id import ID
        try:
            doc_id = ID.unique()
            # Ensure required fields
            booking_data.setdefault("status", "confirmed")
            booking_data.setdefault("created_at", datetime.now().isoformat())
            
            result = self._make_request(
                "POST",
                f"/databases/{self.db_id}/collections/bookings/documents",
                data={
                    "documentId": doc_id,
                    "data": booking_data
                }
            )
            logger.info(f"Created booking: {doc_id}")
            return result
        except Exception as e:
            logger.error(f"Error creating booking: {e}")
            return None
    
    def get_bookings(self, date: str = None, status: str = None):
        """
        Get bookings with optional filters.
        Uses in-memory filtering for reliability across all Appwrite configurations.
        """
        try:
            path = f"/databases/{self.db_id}/collections/bookings/documents"
            result = self._make_request("GET", path)
            bookings = result.get("documents", []) if result else []
            
            # Filter in Python for reliability
            if date:
                bookings = [b for b in bookings if b.get("booking_date") == date]
            if status:
                bookings = [b for b in bookings if b.get("status") == status]
            
            return bookings
        except Exception as e:
            logger.error(f"Error fetching bookings: {e}")
            return []
    
    def get_bookings_range(self, start_date: str, end_date: str):
        """Get bookings within a date range."""
        try:
            path = f"/databases/{self.db_id}/collections/bookings/documents"
            # FIX: Use 'queries' list, _make_request handles indexing
            params = {
                "queries": [
                    f'greaterThanEqual("booking_date", "{start_date}")',
                    f'lessThanEqual("booking_date", "{end_date}")'
                ]
            }
            result = self._make_request("GET", path, params=params)
            return result.get("documents", []) if result else []
        except Exception as e:
            logger.error(f"Error fetching bookings range: {e}")
            return []
    
    def update_booking(self, booking_id: str, data: dict):
        """Update a booking (reschedule, cancel, mark complete)."""
        try:
            result = self._make_request(
                "PATCH",
                f"/databases/{self.db_id}/collections/bookings/documents/{booking_id}",
                data={"data": data}
            )
            return result
        except Exception as e:
            logger.error(f"Error updating booking: {e}")
            return None
    
    def get_availability(self, date: str, start_hour: int = 9, end_hour: int = 18, slot_duration: int = 30):
        """
        Get available time slots for a given date.
        Returns list of available slot times (HH:MM format).
        """
        try:
            # Get existing bookings for the date
            existing = self.get_bookings(date=date, status="confirmed")
            
            # Build list of booked times
            booked_times = set()
            for booking in existing:
                booked_times.add(booking.get("booking_time", ""))
            
            # Generate all possible slots
            available = []
            current_hour = start_hour
            current_min = 0
            
            while current_hour < end_hour:
                time_str = f"{current_hour:02d}:{current_min:02d}"
                if time_str not in booked_times:
                    available.append(time_str)
                
                current_min += slot_duration
                if current_min >= 60:
                    current_min = 0
                    current_hour += 1
            
            return available
        except Exception as e:
            logger.error(f"Error getting availability: {e}")
            return []
    
    # ==================== CUSTOMER ANALYTICS ====================
    
    def update_customer_stats(self, phone: str, action: str, details: dict = None):
        """
        Track customer interaction stats.
        action: 'booking_request', 'approved', 'rejected', 'reschedule', 'cancel', 'first_contact'
        details: Optional dict with service, date, notes etc.
        """
        try:
            now = datetime.now(MELBOURNE_TZ).isoformat()
            
            # Find or create customer
            customer = self._find_customer_by_phone(phone)
            
            if customer:
                customer_id = customer.get("$id")
                # Use preferences_json for stats (Appwrite has attribute limit)
                stats = json.loads(customer.get("preferences_json") or "{}")
            else:
                # Create new customer record
                from appwrite.id import ID
                customer_id = ID.unique()
                stats = {}
                self._make_request(
                    "POST",
                    f"/databases/{self.db_id}/collections/customers/documents",
                    data={
                        "documentId": customer_id,
                        "data": {
                            "whatsapp_id": phone,
                            "business_id": "default_business",
                            "name": details.get("customer_name", "") if details else "",
                            "email": details.get("customer_email", "") if details else "",
                            "preferences_json": "{}",  # Stats stored here
                            "violation_count": 0
                        }
                    }
                )
                logger.info(f"Created new customer: {customer_id}")
            
            # Initialize stats if empty
            if not stats:
                stats = {
                    "total_bookings": 0,
                    "total_cancellations": 0,
                    "total_reschedules": 0,
                    "requests_approved": 0,
                    "requests_rejected": 0,
                    "first_interaction": now,
                    "last_interaction": now,
                    "booking_history": []
                }
            
            # Update last interaction
            stats["last_interaction"] = now
            
            # Increment appropriate counter
            if action == "booking_request":
                stats["total_bookings"] = stats.get("total_bookings", 0) + 1
            elif action == "approved":
                stats["requests_approved"] = stats.get("requests_approved", 0) + 1
            elif action == "rejected":
                stats["requests_rejected"] = stats.get("requests_rejected", 0) + 1
            elif action == "reschedule":
                stats["total_reschedules"] = stats.get("total_reschedules", 0) + 1
            elif action == "cancel":
                stats["total_cancellations"] = stats.get("total_cancellations", 0) + 1
            
            # Add to booking history (keep last 50)
            if details:
                history_entry = {
                    "date": now,
                    "action": action,
                    "service": details.get("service_name", ""),
                    "status": details.get("status", action)
                }
                booking_history = stats.get("booking_history", [])
                booking_history.insert(0, history_entry)
                stats["booking_history"] = booking_history[:50]  # Keep last 50
            
            # Update customer with new stats (using preferences_json field)
            self._make_request(
                "PATCH",
                f"/databases/{self.db_id}/collections/customers/documents/{customer_id}",
                data={"data": {"preferences_json": json.dumps(stats)}}
            )
            
            logger.info(f"Updated stats for {phone}: {action}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating customer stats: {e}")
            return False
    
    def _find_customer_by_phone(self, phone: str):
        """Find customer by WhatsApp ID/phone."""
        try:
            # FIX: Use string format and 'queries' key
            result = self._make_request(
                "GET",
                f"/databases/{self.db_id}/collections/customers/documents",
                params={"queries": [f'equal("whatsapp_id", "{phone}")']}
            )
            docs = result.get("documents", [])
            return docs[0] if docs else None
        except:
            return None
    
    def get_customer_analytics(self, phone: str):
        """Get detailed analytics for a customer."""
        customer = self._find_customer_by_phone(phone)
        if customer:
            stats = json.loads(customer.get("preferences_json") or "{}")
            return {
                "customer_id": customer.get("$id"),
                "name": customer.get("name", "Unknown"),
                "email": customer.get("email"),
                "phone": phone,
                "stats": stats,
                "profile_summary": customer.get("profile_summary", "")
            }
        return None

    # ==================== DEMO ANALYTICS ====================
    
    def create_demo_lead(self, name: str, business_name: str, phone: str, source: str = "website") -> dict:
        """Create a new demo lead when form is submitted."""
        from appwrite.id import ID
        try:
            doc_id = ID.unique()
            now = datetime.now(MELBOURNE_TZ).isoformat()
            
            data = {
                "name": name,
                "business_name": business_name,
                "phone": phone,
                "status": "pending",
                "source": source,
                "created_at": now,
                "updated_at": now
            }
            
            result = self._make_request(
                "POST",
                f"/databases/{self.db_id}/collections/demo_leads/documents",
                data={"documentId": doc_id, "data": data}
            )
            logger.info(f"Created demo lead: {doc_id} for {phone}")
            return result
        except Exception as e:
            logger.error(f"Error creating demo lead: {e}")
            return None
    
    def update_demo_lead(self, lead_id: str = None, phone: str = None, data: dict = None):
        """Update a demo lead by ID or phone."""
        try:
            # Find by phone if ID not provided
            if not lead_id and phone:
                result = self._make_request(
                    "GET",
                    f"/databases/{self.db_id}/collections/demo_leads/documents"
                )
                if result and result.get("documents"):
                    for doc in result["documents"]:
                        if doc.get("phone") == phone:
                            lead_id = doc.get("$id")
                            break
            
            if not lead_id:
                logger.warning(f"Demo lead not found for phone: {phone}")
                return None
            
            data["updated_at"] = datetime.now(MELBOURNE_TZ).isoformat()
            
            result = self._make_request(
                "PATCH",
                f"/databases/{self.db_id}/collections/demo_leads/documents/{lead_id}",
                data={"data": data}
            )
            return result
        except Exception as e:
            logger.error(f"Error updating demo lead: {e}")
            return None
    
    def check_demo_limit(self, phone: str) -> bool:
        """
        Check if phone number has already requested a demo in the last 24 hours.
        Returns: True if allowed, False if blocked.
        """
        try:
            # Check whitelist first
            if is_whitelisted(phone):
                return True
                
            # Calculate time threshold
            now = datetime.now(MELBOURNE_TZ)
            threshold = now - timedelta(hours=self.DEMO_LIMIT_HOURS)
            threshold_str = threshold.isoformat()
            
            # Fetch all demo leads and filter in-memory for reliability
            result = self._make_request(
                "GET",
                f"/databases/{self.db_id}/collections/demo_leads/documents"
            )
            
            if result and result.get("documents"):
                for doc in result["documents"]:
                    if doc.get("phone") == phone:
                        created_at = doc.get("created_at", "")
                        if created_at > threshold_str:
                            logger.info(f"Rate limit: {phone} already requested demo at {created_at}")
                            return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error checking demo limit: {e}")
            return True # Fail open

    def create_demo_transcript(self, phone: str, transcript: list, 
                                exchange_count: int = 0, duration_seconds: int = 0,
                                outcome: str = "completed", call_sid: str = None,
                                demo_lead_id: str = None) -> dict:
        """
        Store a demo call transcript for AI analysis.
        transcript: List of {"role": "ai"|"user", "text": "...", "timestamp": "..."}
        """
        from appwrite.id import ID
        try:
            doc_id = ID.unique()
            now = datetime.now(MELBOURNE_TZ).isoformat()
            
            data = {
                "phone": phone,
                "transcript_json": json.dumps(transcript),
                "exchange_count": exchange_count,
                "duration_seconds": duration_seconds,
                "outcome": outcome,
                "call_sid": call_sid or "",
                "demo_lead_id": demo_lead_id or "",
                "created_at": now
            }
            
            result = self._make_request(
                "POST",
                f"/databases/{self.db_id}/collections/demo_transcripts/documents",
                data={"documentId": doc_id, "data": data}
            )
            logger.info(f"Created demo transcript: {doc_id} ({exchange_count} exchanges)")
            return result
        except Exception as e:
            logger.error(f"Error creating demo transcript: {e}")
            return None
    
    def update_transcript_feedback(self, transcript_id: str, feedback: str, 
                                    score: int = None, issues: list = None):
        """Update transcript with Mistral's AI feedback."""
        try:
            data = {
                "ai_feedback": feedback
            }
            if score is not None:
                data["feedback_score"] = score
            if issues:
                data["issues_found"] = json.dumps(issues)
            
            result = self._make_request(
                "PATCH",
                f"/databases/{self.db_id}/collections/demo_transcripts/documents/{transcript_id}",
                data={"data": data}
            )
            logger.info(f"Updated transcript feedback: {transcript_id}")
            return result
        except Exception as e:
            logger.error(f"Error updating transcript feedback: {e}")
            return None
    
    def get_transcripts_for_review(self, limit: int = 20):
        """Get transcripts that haven't been reviewed yet (no AI feedback)."""
        try:
            result = self._make_request(
                "GET",
                f"/databases/{self.db_id}/collections/demo_transcripts/documents"
            )
            if result and result.get("documents"):
                # Filter for those without feedback
                pending = [
                    t for t in result["documents"]
                    if not t.get("ai_feedback")
                ]
                return pending[:limit]
            return []
        except Exception as e:
            logger.error(f"Error fetching transcripts for review: {e}")
            return []


db_service = AppwriteService()


