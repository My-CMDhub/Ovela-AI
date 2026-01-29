import json
from datetime import datetime
from zoneinfo import ZoneInfo
from appwrite.id import ID
import logging

logger = logging.getLogger(__name__)

class CustomersMixin:
    """
    Handles Customer profiles and Stats.
    """
    
    def update_customer_stats(self, phone: str, action: str, details: dict = None, tenant_id: str = "default"):
        """
        Track customer interaction stats.
        CRITICAL: added tenant_id context, though currently customers might be shared or default.
        """
        try:
            MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
            now = datetime.now(MELBOURNE_TZ).isoformat()
            
            # Find or create customer
            customer = self._find_customer_by_phone(phone)
            
            if customer:
                customer_id = customer.get("$id")
                # Use preferences_json for stats (Appwrite has attribute limit)
                stats = json.loads(customer.get("preferences_json") or "{}")
            else:
                # Create new customer record
                customer_id = ID.unique()
                stats = {}
                self._make_request(
                    "POST",
                    f"/databases/{self.db_id}/collections/customers/documents",
                    data={
                        "documentId": customer_id,
                        "data": {
                            "whatsapp_id": phone,
                            "business_id": tenant_id if tenant_id != "default" else "default_business",
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
                    "status": details.get("status", action),
                    "tenant_id": tenant_id # Track which tenant this happened with
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

    def upsert_motel_guest(self, 
                          guest_name: str, 
                          guest_phone: str, 
                          guest_email: str = None, 
                          tenant_id: str = "coalcreek", 
                          status: str = "inquiry") -> dict:
        """
        Create or Update a guest in the Motel CRM.
        tenant_id: Critical for multi-tenant scalability.
        status: 'inquiry' (called but didn't book) or 'guest' (has booking).
        """
        if not guest_phone:
            return None
            
        try:
            # 1. Search for existing guest by phone AND tenant_id
            queries = [
                f'equal("phone", "{guest_phone}")',
                f'equal("tenant_id", "{tenant_id}")'
            ]
            params = {'queries': queries}
            
            endpoint = f"/collections/motel_guests/documents"
            result = self._motel_request("GET", endpoint, params=params)
            
            existing_doc = None
            if result and result.get("documents"):
                existing_doc = result["documents"][0]
            
            now = datetime.now().isoformat()
            
            # Data to save
            data = {
                "name": guest_name,
                "phone": guest_phone,
                "tenant_id": tenant_id,
                "updated_at": now
            }
            if guest_email:
                data["email"] = guest_email
            
            # Logic: If existing status is 'guest', don't downgrade to 'inquiry'
            # If new status is 'guest', upgrade.
            if existing_doc:
                current_status = existing_doc.get("status", "inquiry")
                if status == "guest" or current_status != "guest":
                    data["status"] = status
            else:
                data["status"] = status

            # 2. Update or Create
            if existing_doc:
                doc_id = existing_doc.get("$id")
                # Merge: don't overwrite email with None if existing has it
                if not guest_email and existing_doc.get("email"):
                    del data["email"]
                    
                self._motel_request(
                    "PATCH", 
                    f"/collections/motel_guests/documents/{doc_id}",
                    data={"data": data}
                )
                logger.info(f"Updated motel guest ({tenant_id}): {guest_name}")
                return {"id": doc_id, "status": "updated"}
            else:
                doc_id = ID.unique()
                data["created_at"] = now
                
                self._motel_request(
                    "POST",
                    "/collections/motel_guests/documents",
                    data={
                        "documentId": doc_id,
                        "data": data
                    }
                )
                logger.info(f"Created new motel guest ({tenant_id}): {guest_name}")
                return {"id": doc_id, "status": "created"}

        except Exception as e:
            logger.error(f"Error upserting motel guest: {e}")
            return None
