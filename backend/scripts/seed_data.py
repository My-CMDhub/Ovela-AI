"""
Seed mock data for dashboard.
Run with: python backend/scripts/seed_data.py
"""

import os
import sys
from datetime import datetime, timedelta
import random
from appwrite.id import ID

# Add project root to path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, "backend"))

from dotenv import load_dotenv
load_dotenv(os.path.join(root_dir, "backend", ".env"))

try:
    from backend.services.appwrite import db_service
except ImportError:
    # Try alternate import if running from root
    from backend.services.appwrite import db_service

def seed_bookings():
    print("🌱 Seeding today's bookings...")
    names = ["Alice Smith", "Bob Jones", "Charlie Brown", "Diana Prince", "Evan Wright"]
    services = ["Consultation", "Follow-up", "Initial Assessment", "Therapy Session", "Check-up"]
    statuses = ["confirmed", "confirmed", "confirmed", "pending", "cancelled"]
    
    now = datetime.now()
    
    for i in range(5):
        start_time = now.replace(hour=9 + i, minute=0, second=0, microsecond=0)
        
        booking = {
            "service_name": services[i],
            "status": statuses[i],
            "customer_name": names[i],
            "customer_email": f"{names[i].lower().replace(' ', '.')}@example.com",
            "customer_phone": f"+6140000000{i}",
            "booking_date": start_time.strftime("%Y-%m-%d"),
            "booking_time": start_time.strftime("%H:%M"),
            "duration_minutes": 30,
            "source": "seed"
        }

        try:
            result = db_service.create_booking(booking)
            if result:
                print(f"✅ Created today's booking for {names[i]}")
        except Exception as e:
            print(f"❌ Failed to create booking: {e}")

def seed_future_bookings():
    print("🌱 Seeding future bookings...")
    names = ["Fiona Green", "George Hill", "Hannah Baker", "Ian Ian", "Jane Doe"]
    services = ["Lash Lift", "Brow Shape", "Facial", "Consultation", "Follow-up"]
    
    now = datetime.now()
    
    for i in range(5):
        # 1-3 days in future
        future_date = now + timedelta(days=i+1)
        start_time = future_date.replace(hour=10 + i, minute=0, second=0, microsecond=0)
        
        booking = {
            "service_name": services[i],
            "status": "confirmed",
            "customer_name": names[i],
            "customer_email": f"{names[i].lower().replace(' ', '.')}@example.com",
            "customer_phone": f"+6140000000{i+5}",
            "booking_date": start_time.strftime("%Y-%m-%d"),
            "booking_time": start_time.strftime("%H:%M"),
            "duration_minutes": 45,
            "source": "seed"
        }

        try:
            result = db_service.create_booking(booking)
            if result:
                print(f"✅ Created future booking for {names[i]}")
        except Exception as e:
            print(f"❌ Failed to create future booking: {e}")

def seed_conversations():
    print("🌱 Seeding conversations...")
    names = ["Sam Wilson", "Jessica Day", "Nick Miller", "Winston Bishop", "Cece Parekh"]
    messages = [
        "Hey, can I reschedule my appointment?",
        "How much is a consultation?",
        "I'm running 5 minutes late!",
        "Thanks for the info.",
        "Do you are open on weekends?"
    ]
    
    for i in range(5):
        whatsapp_id = f"+6141111111{i}"
        
        data = {
            "whatsapp_id": whatsapp_id,
            "business_id": "default_business",
            "status": "active" if i < 3 else "closed",
            "last_message": messages[i],
            "tokens_used_today": random.randint(50, 500),
            "history": "[]"
        }

        try:
            doc_id = ID.unique()
            result = db_service._make_request(
                "POST",
                f"/databases/{db_service.db_id}/collections/conversations/documents",
                data={
                    "documentId": doc_id,
                    "data": data
                }
            )
            
            if result:
                print(f"✅ Created conversation for {names[i]}")
        except Exception as e:
            print(f"❌ Failed to create conversation: {e}")

def seed_customers():
    print("🌱 Seeding customers...")
    names = ["Liam Neeson", "Emma Stone", "Ryan Gosling", "Mila Kunis", "Ashton Kutcher"]
    
    for i, name in enumerate(names):
        phone = f"+6142222222{i}"
        
        try:
            # Fix: use 'phone' argument and pass name/email in details
            db_service.update_customer_stats(
                phone=phone,
                action="first_contact", # Use valid action type
                details={
                    "customer_name": name,
                    "customer_email": f"{name.lower().replace(' ', '.')}@example.com",
                    "service_name": "General Inquiry",
                    "status": "new"
                }
            )
            print(f"✅ Created customer {name} ({phone})")
        except Exception as e:
            print(f"❌ Failed to create customer {name}: {e}")

def seed_requests():
    print("🌱 Seeding booking requests...")
    requests = [
        {"name": "Tom Holland", "service": "Spiderman Suit Fitting", "status": "pending", "notes": "Need it by Friday"},
        {"name": "Zendaya", "service": "Red Carpet Look", "status": "approved", "notes": "VIP"},
        {"name": "Jacob Batalon", "service": "Sidekick Training", "status": "rejected", "notes": "Not a service we offer"},
        {"name": "Benedict Cumberbatch", "service": "Magic Show", "status": "pending", "notes": "Is this real magic?"},
    ]
    
    for i, req in enumerate(requests):
        try:
            data = {
                "business_id": "default_business",
                "customer_name": req["name"],
                "customer_phone": f"+6143333333{i}",
                "customer_email": f"{req['name'].lower().replace(' ', '.')}@example.com",
                "service_name": req["service"],
                "status": req["status"],
                "preferred_date": (datetime.now() + timedelta(days=i+2)).strftime("%Y-%m-%d"),
                "preferred_time": "14:00",
                "notes": req["notes"],
                "source": "web",
                "created_at": datetime.now().isoformat()
            }
            
            db_service._make_request(
                "POST",
                f"/databases/{db_service.db_id}/collections/booking_requests/documents",
                data={
                    "documentId": ID.unique(),
                    "data": data
                }
            )
            print(f"✅ Created {req['status']} request for {req['name']}")
        except Exception as e:
            print(f"❌ Failed to create request for {req['name']}: {e}")

if __name__ == "__main__":
    seed_bookings()
    seed_future_bookings()
    seed_conversations()
    seed_customers()
    seed_requests()
    print("✨ Seeding complete!")
