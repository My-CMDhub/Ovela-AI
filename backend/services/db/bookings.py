from datetime import datetime
from appwrite.id import ID
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)

class BookingsMixin:
    """
    Handles all Booking related operations.
    Enforces tenant_id isolation where applicable.
    """
    
    # ============ APPOINTMENT BOOKINGS (Legacy/Appointment Mode) ============

    def create_booking_request(self, request_data: dict):
        """Create a new booking request (for appointment-only mode)."""
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

    def get_booking_requests(self, status: str = None, tenant_id: str = None):
        """
        Get booking requests, optionally filtered by status.
        CRITICAL: Now supports filtering by tenant_id via Python filtering.
        """
        try:
            path = f"/databases/{self.db_id}/collections/booking_requests/documents"
            result = self._make_request("GET", path)
            requests = result.get("documents", []) if result else []
            
            # Filter by Tenant (Security Fix)
            # If tenant_id is provided, enforce it.
            # If not provided, behavior depends on caller (legacy might not pass it), 
            # but ideally we should warn or default to something safe.
            # For now, we enforce if passed.
            if tenant_id:
                requests = [r for r in requests if r.get("tenant_id") == tenant_id]
            
            # Filter by Status
            if status:
                requests = [r for r in requests if r.get("status") == status]
            
            return requests
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
    
    def get_booking_requests_by_phone(self, customer_phone: str, tenant_id: str = None):
        """Get booking requests for a specific customer by phone number."""
        try:
            path = f"/databases/{self.db_id}/collections/booking_requests/documents"
            result = self._make_request("GET", path)
            
            if result and result.get("documents"):
                # Filter in-memory for reliability
                requests = [
                    r for r in result["documents"]
                    if r.get("customer_phone") == customer_phone
                ]
                
                # Filter by Tenant if provided
                if tenant_id:
                     requests = [r for r in requests if r.get("tenant_id") == tenant_id]
                
                return requests
            return []
        except Exception as e:
            logger.error(f"Error fetching requests by phone: {e}")
            return []

    # ============ MOTEL BOOKINGS (Confirmed/PMS Mode) ============
    
    def create_booking(self, booking_data: dict):
        """Create a confirmed booking."""
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
    
    def get_bookings(self, date: str = None, status: str = None, tenant_id: str = None):
        """
        Get bookings with optional filters.
        CRITICAL: Added tenant_id support.
        """
        try:
            path = f"/databases/{self.db_id}/collections/bookings/documents"
            result = self._make_request("GET", path)
            bookings = result.get("documents", []) if result else []
            
            # Filter by Tenant
            if tenant_id:
                bookings = [b for b in bookings if b.get("tenant_id") == tenant_id]

            # Filter in Python for reliability
            if date:
                bookings = [b for b in bookings if b.get("booking_date") == date]
            if status:
                bookings = [b for b in bookings if b.get("status") == status]
            
            return bookings
        except Exception as e:
            logger.error(f"Error fetching bookings: {e}")
            return []
    
    def get_bookings_range(self, start_date: str, end_date: str, tenant_id: str = None):
        """Get bookings within a date range."""
        try:
            path = f"/databases/{self.db_id}/collections/bookings/documents"
            params = {
                "queries": [
                    f'greaterThanEqual("booking_date", "{start_date}")',
                    f'lessThanEqual("booking_date", "{end_date}")'
                ]
            }
            # Note: Appwrite queries don't support simple AND with local attribute filters if not indexed.
            # Best to fetch range (which is indexed) and filter tenant locally if index missing.
            
            result = self._make_request("GET", path, params=params)
            bookings = result.get("documents", []) if result else []

            if tenant_id:
                bookings = [b for b in bookings if b.get("tenant_id") == tenant_id]
                
            return bookings
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
    
    def get_availability(self, date: str, start_hour: int = 9, end_hour: int = 18, slot_duration: int = 30, tenant_id: str = None):
        """
        Get available time slots for a given date.
        Returns list of available slot times (HH:MM format).
        """
        try:
            # Get existing bookings for the date
            existing = self.get_bookings(date=date, status="confirmed", tenant_id=tenant_id)
            
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


    # ==================== PAYMENT STATUS TRACKING ====================
    
    def update_booking_payment_status(
        self,
        booking_id: str,
        payment_status: str,
        payment_link_url: str = None,
        stripe_payment_id: str = None,
        tenant_id: str = "coalcreek"
    ) -> dict:
        """
        Update payment status for a booking in motel_reservations.
        """
        try:
            now = datetime.now(ZoneInfo("Australia/Melbourne")).isoformat()
            
            data = {
                "payment_status": payment_status,
                "updated_at": now
            }
            
            if payment_link_url:
                data["payment_link_url"] = payment_link_url
                data["payment_link_sent_at"] = now
                
            if stripe_payment_id:
                data["stripe_payment_id"] = stripe_payment_id
                
            if payment_status == "paid":
                data["payment_received_at"] = now
                data["status"] = "confirmed"  # Auto-confirm when paid
            
            result = self._make_request(
                "PATCH",
                f"/databases/{self.motel_db_id}/collections/motel_reservations/documents/{booking_id}",
                data={"data": data}
            )
            
            if result:
                logger.info(f"💳 [{tenant_id}] Booking {booking_id} → payment_status={payment_status}")
            return result
            
        except Exception as e:
            logger.error(f"Error updating payment status: {e}")
            return None
    
    def get_bookings_by_payment_status(
        self,
        payment_status: str = None,
        tenant_id: str = "coalcreek",
        limit: int = 50
    ) -> list:
        """
        Get bookings filtered by payment status for CRM dashboard.
        """
        try:
            result = self._make_request(
                "GET",
                f"/databases/{self.motel_db_id}/collections/motel_reservations/documents"
            )
            
            bookings = result.get("documents", []) if result else []
            
            # Filter by tenant
            bookings = [b for b in bookings if b.get("tenant_id") == tenant_id]
            
            # Filter by payment status if specified
            if payment_status:
                bookings = [b for b in bookings if b.get("payment_status") == payment_status]
            
            # Sort by created_at descending
            bookings.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            
            return bookings[:limit]
            
        except Exception as e:
            logger.error(f"Error fetching bookings by payment status: {e}")
            return []
    
    def get_booking_by_reference(
        self,
        booking_reference: str,
        tenant_id: str = "coalcreek"
    ) -> dict:
        """
        Find a booking by its reference code.
        """
        try:
            result = self._make_request(
                "GET",
                f"/databases/{self.motel_db_id}/collections/motel_reservations/documents"
            )
            
            bookings = result.get("documents", []) if result else []
            
            for booking in bookings:
                if (booking.get("booking_reference") == booking_reference and 
                    booking.get("tenant_id") == tenant_id):
                    return booking
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding booking by reference: {e}")
            return None
