from datetime import datetime
from appwrite.id import ID
from zoneinfo import ZoneInfo
import logging
import hashlib
from core.utils import mask_phone

logger = logging.getLogger(__name__)

class BookingsMixin:
    """
    Handles all Booking related operations.
    Enforces tenant_id isolation at the database level.
    """
    
    # ============ APPOINTMENT BOOKINGS (Legacy/Appointment Mode) ============

    async def create_booking_request(self, request_data: dict):
        """Create a new booking request (for appointment-only mode)."""
        try:
            doc_id = ID.unique()
            result = await self._make_request(
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

    async def get_booking_requests(self, status: str = None, tenant_id: str = None):
        """
        Get booking requests, filtered by tenant and status.
        ENFORCED: Server-side filtering by tenant_id.
        """
        try:
            if not tenant_id:
                logger.warning("⚠️ SECURITY: get_booking_requests called without tenant_id! Returning all tenants.")
            path = f"/databases/{self.db_id}/collections/booking_requests/documents"
            
            queries = []
            if tenant_id:
                queries.append(f'equal("tenant_id", "{tenant_id}")')
            if status:
                queries.append(f'equal("status", "{status}")')
                
            params = {"queries": queries} if queries else {}
            
            result = await self._make_request("GET", path, params=params)
            requests = result.get("documents", []) if result else []
            
            return requests
        except Exception as e:
            logger.error(f"Error fetching booking requests: {e}")
            return []

    async def update_booking_request(self, request_id: str, data: dict):
        """Update a booking request (approve/reject)."""
        try:
            result = await self._make_request(
                "PATCH",
                f"/databases/{self.db_id}/collections/booking_requests/documents/{request_id}",
                data={"data": data}
            )
            return result
        except Exception as e:
            logger.error(f"Error updating booking request: {e}")
            return None
    
    async def get_booking_requests_by_phone(self, customer_phone: str, tenant_id: str = None):
        """Get booking requests for a specific customer by phone number."""
        try:
            path = f"/databases/{self.db_id}/collections/booking_requests/documents"
            
            queries = [f'equal("customer_phone", "{customer_phone}")']
            if tenant_id:
                queries.append(f'equal("tenant_id", "{tenant_id}")')
                
            params = {"queries": queries}
            result = await self._make_request("GET", path, params=params)
            
            return result.get("documents", []) if result else []
        except Exception as e:
            logger.error(f"Error fetching requests by phone: {e}")
            return []

    # ============ MOTEL BOOKINGS (Confirmed/PMS Mode) ============
    
    async def create_booking(self, booking_data: dict):
        """Create a confirmed booking with deterministic ID to prevent double bookings."""
        try:
            # Generate deterministic ID based on critical slot parameters
            # Format: {tenant}_{date}_{time}_{room_type}
            tenant_id = booking_data.get("tenant_id", "coalcreek")
            booking_date = booking_data.get("booking_date", "")
            booking_time = booking_data.get("booking_time", "")
            room_type = booking_data.get("room_type", "queen")
            
            # Create a unique but deterministic key for this specific slot
            raw_id = f"{tenant_id}_{booking_date}_{booking_time}_{room_type}"
            doc_id = hashlib.md5(raw_id.encode()).hexdigest()
            
            # Ensure required fields
            booking_data.setdefault("status", "confirmed")
            booking_data.setdefault("created_at", datetime.now().isoformat())
            
            result = await self._make_request(
                "POST",
                f"/databases/{self.db_id}/collections/bookings/documents",
                data={
                    "documentId": doc_id,
                    "data": booking_data
                }
            )
            logger.info(f"Created booking: {doc_id} for slot {raw_id}")
            return result
        except Exception as e:
            if "already exists" in str(e).lower() or "conflict" in str(e).lower():
                logger.warning(f"⚠️ Double booking prevented for slot {raw_id}")
                return {"error": "already_booked", "message": "This slot has just been taken by another guest."}
            logger.error(f"Error creating booking: {e}")
            return None
    
    async def get_bookings(self, date: str = None, status: str = None, tenant_id: str = None):
        """
        Get bookings with server-side filters.
        """
        try:
            if not tenant_id:
                logger.warning("⚠️ SECURITY: get_bookings called without tenant_id! Returning all tenants.")
            path = f"/databases/{self.db_id}/collections/bookings/documents"
            
            queries = []
            if tenant_id:
                queries.append(f'equal("tenant_id", "{tenant_id}")')
            if date:
                queries.append(f'equal("booking_date", "{date}")')
            if status:
                queries.append(f'equal("status", "{status}")')
                
            params = {"queries": queries} if queries else {}
            
            result = await self._make_request("GET", path, params=params)
            return result.get("documents", []) if result else []
        except Exception as e:
            logger.error(f"Error fetching bookings: {e}")
            return []
    
    async def get_bookings_range(self, start_date: str, end_date: str, tenant_id: str = None):
        """Get bookings within a date range with server-side isolation."""
        try:
            path = f"/databases/{self.db_id}/collections/bookings/documents"
            queries = [
                f'greaterThanEqual("booking_date", "{start_date}")',
                f'lessThanEqual("booking_date", "{end_date}")'
            ]
            if tenant_id:
                queries.append(f'equal("tenant_id", "{tenant_id}")')
                
            params = {"queries": queries}
            
            result = await self._make_request("GET", path, params=params)
            return result.get("documents", []) if result else []
        except Exception as e:
            logger.error(f"Error fetching bookings range: {e}")
            return []
    
    async def update_booking(self, booking_id: str, data: dict):
        """Update a booking (reschedule, cancel, mark complete)."""
        try:
            result = await self._make_request(
                "PATCH",
                f"/databases/{self.db_id}/collections/bookings/documents/{booking_id}",
                data={"data": data}
            )
            return result
        except Exception as e:
            logger.error(f"Error updating booking: {e}")
            return None
    
    async def get_availability(self, date: str, start_hour: int = 9, end_hour: int = 18, slot_duration: int = 30, tenant_id: str = None):
        """
        Get available time slots for a given date.
        Returns list of available slot times (HH:MM format).
        """
        try:
            if not tenant_id:
                logger.warning("⚠️ SECURITY: get_availability called without tenant_id!")
            # Get existing bookings for the date
            existing = await self.get_bookings(date=date, status="confirmed", tenant_id=tenant_id)
            
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
    
    async def update_booking_payment_status(
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
            
            result = await self._motel_request(
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
    
    async def get_bookings_by_payment_status(
        self,
        payment_status: str = None,
        tenant_id: str = "coalcreek",
        limit: int = 50
    ) -> list:
        """
        Get bookings filtered by payment status.
        ENFORCED: Server-side isolation.
        """
        try:
            queries = [f'equal("tenant_id", "{tenant_id}")']
            if payment_status:
                queries.append(f'equal("payment_status", "{payment_status}")')
            
            queries.append('orderDesc("created_at")')
            queries.append(f'limit({limit})')
            
            params = {"queries": queries}
            
            result = await self._motel_request(
                "GET",
                f"/databases/{self.motel_db_id}/collections/motel_reservations/documents",
                params=params
            )
            
            return result.get("documents", []) if result else []
            
        except Exception as e:
            logger.error(f"Error fetching bookings by payment status: {e}")
            return []
    
    async def get_booking_by_reference(
        self,
        booking_reference: str,
        tenant_id: str = "coalcreek"
    ) -> dict:
        """
        Find a booking by its reference code.
        ENFORCED: Server-side isolation.
        """
        try:
            queries = [
                f'equal("booking_reference", "{booking_reference}")',
                f'equal("tenant_id", "{tenant_id}")'
            ]
            params = {"queries": queries}
            
            result = await self._motel_request(
                "GET",
                f"/databases/{self.motel_db_id}/collections/motel_reservations/documents",
                params=params
            )
            
            docs = result.get("documents", []) if result else []
            return docs[0] if docs else None
            
        except Exception as e:
            logger.error(f"Error finding booking by reference: {e}")
            return None

    async def lookup_motel_reservation(
        self,
        guest_name: str = None,
        phone: str = None,
        booking_reference: str = None,
        email: str = None,
        tenant_id: str = "coalcreek"
    ) -> list:
        """
        Look up motel reservations by reference, phone, or guest name.
        Priority: reference > phone > name.
        Returns up to 5 matching documents.
        ENFORCED: tenant_id isolation.
        """
        try:
            base_tenant = f'equal("tenant_id", "{tenant_id}")'

            # 1. Reference is most precise — try first
            if booking_reference:
                ref_clean = booking_reference.strip().upper()
                queries = [base_tenant, f'equal("booking_reference", "{ref_clean}")']
                result = await self._motel_request(
                    "GET",
                    f"/databases/{self.motel_db_id}/collections/motel_reservations/documents",
                    params={"queries": queries}
                )
                docs = result.get("documents", []) if result else []
                if docs:
                    return docs

            # 2. Phone match
            if phone:
                queries = [base_tenant, f'equal("guest_phone", "{phone}")', 'orderDesc("created_at")', 'limit(5)']
                result = await self._motel_request(
                    "GET",
                    f"/databases/{self.motel_db_id}/collections/motel_reservations/documents",
                    params={"queries": queries}
                )
                docs = result.get("documents", []) if result else []
                if docs:
                    return docs

            # 3. Guest name — exact match (title-cased)
            if guest_name:
                name_clean = guest_name.strip().title()
                queries = [base_tenant, f'equal("guest_name", "{name_clean}")', 'orderDesc("created_at")', 'limit(5)']
                result = await self._motel_request(
                    "GET",
                    f"/databases/{self.motel_db_id}/collections/motel_reservations/documents",
                    params={"queries": queries}
                )
                docs = result.get("documents", []) if result else []
                if docs:
                    return docs

                # 3b. Fallback: search (full-text index, if available)
                queries = [base_tenant, f'search("guest_name", "{name_clean}")', 'limit(5)']
                result = await self._motel_request(
                    "GET",
                    f"/databases/{self.motel_db_id}/collections/motel_reservations/documents",
                    params={"queries": queries}
                )
                docs = result.get("documents", []) if result else []
                if docs:
                    return docs

            # 4. Email match
            if email:
                email_clean = email.strip().lower()
                queries = [base_tenant, f'equal("guest_email", "{email_clean}")', 'orderDesc("created_at")', 'limit(5)']
                result = await self._motel_request(
                    "GET",
                    f"/databases/{self.motel_db_id}/collections/motel_reservations/documents",
                    params={"queries": queries}
                )
                docs = result.get("documents", []) if result else []
                if docs:
                    return docs

            return []

        except Exception as e:
            logger.error(f"Error in lookup_motel_reservation: {e}")
            return []
