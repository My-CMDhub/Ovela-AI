from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.exception import AppwriteException
import os
import sys
# Ensure the project root is in PYTHONPATH for script execution
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)
from core.config import settings

def setup_schema():
    client = Client()
    client.set_endpoint(settings.APPWRITE_ENDPOINT)
    client.set_project(settings.APPWRITE_PROJECT_ID)
    client.set_key(settings.APPWRITE_API_KEY)

    databases = Databases(client)
    db_name = "OvelaDB"
    db_id = "ovela_db" # Fixed ID for simplicity

    # 1. Create Database
    # 1. Create Database
    try:
        print(f"Creating database '{db_name}' ({db_id})...")
        databases.create(database_id=db_id, name=db_name)
        print("✅ Database created.")
    except AppwriteException as e:
        if "already exists" in str(e) or "409" in str(e):
            print(f"✅ Database '{db_name}' already exists.")
        else:
            print(f"⚠️ Error creating database: {e}")

    # 2. Create Collections
    collections = {
        "businesses": {
            "name": "Businesses",
            "attributes": [
                {"key": "name", "type": "string", "size": 255, "required": True},
                {"key": "whatsapp_business_id", "type": "string", "size": 255, "required": True},
                {"key": "industry", "type": "string", "size": 50, "required": True}, # beauty, dental, real_estate
                {"key": "system_prompt_override", "type": "string", "size": 5000, "required": False},  # Stores all settings as JSON
                {"key": "owner_email", "type": "string", "size": 255, "required": False},  # For notifications
                {"key": "business_phone", "type": "string", "size": 50, "required": False},  # Shown to customers
            ]
        },
        "conversations": {
            "name": "Conversations",
            "attributes": [
                {"key": "whatsapp_id", "type": "string", "size": 50, "required": True}, # User's phone number
                {"key": "business_id", "type": "string", "size": 255, "required": True}, # Link to Business
                {"key": "last_message", "type": "string", "size": 5000, "required": False},
                {"key": "status", "type": "string", "size": 50, "required": True}, # active, archived
                {"key": "history", "type": "string", "size": 100000, "required": False}, # JSON string of last N messages
                {"key": "session_summary", "type": "string", "size": 5000, "required": False}, # Summary of this session
                {"key": "tokens_used_today", "type": "integer", "required": False, "default": 0},  # Token rate limiting
                {"key": "token_reset_at", "type": "string", "size": 50, "required": False},  # ISO datetime for reset
            ]
        },
        "bookings": {
            "name": "Bookings",
            "attributes": [
                {"key": "customer_name", "type": "string", "size": 255, "required": True},
                {"key": "customer_phone", "type": "string", "size": 50, "required": True},
                {"key": "customer_email", "type": "string", "size": 255, "required": False},
                {"key": "service_name", "type": "string", "size": 255, "required": True},
                {"key": "booking_date", "type": "string", "size": 20, "required": True},  # YYYY-MM-DD
                {"key": "booking_time", "type": "string", "size": 10, "required": True},  # HH:MM
                {"key": "duration_minutes", "type": "integer", "required": False, "default": 30},
                {"key": "status", "type": "string", "size": 50, "required": True},  # confirmed, completed, cancelled, no-show
                {"key": "notes", "type": "string", "size": 2000, "required": False},
                {"key": "source", "type": "string", "size": 50, "required": False},  # whatsapp, phone, dashboard
                {"key": "created_at", "type": "string", "size": 100, "required": False},
            ]
        },
        "customers": {
            "name": "Customers",
            "attributes": [
                {"key": "whatsapp_id", "type": "string", "size": 50, "required": True},
                {"key": "business_id", "type": "string", "size": 255, "required": True},
                {"key": "name", "type": "string", "size": 255, "required": False},
                {"key": "email", "type": "string", "size": 255, "required": False},
                {"key": "profile_summary", "type": "string", "size": 5000, "required": False}, # AI memory of user
                {"key": "preferences_json", "type": "string", "size": 5000, "required": False},
                {"key": "stats_json", "type": "string", "size": 10000, "required": False},  # Analytics data
                # stats_json structure: {
                #   "total_bookings": 0, "total_cancellations": 0, "total_reschedules": 0,
                #   "requests_approved": 0, "requests_rejected": 0,
                #   "first_interaction": "ISO", "last_interaction": "ISO",
                #   "booking_history": [{"date": "...", "service": "...", "status": "..."}]
                # }
                {"key": "violation_count", "type": "integer", "required": False, "default": 0},
                {"key": "cooldown_until", "type": "datetime", "required": False}
            ]
        },
        "booking_requests": {
            "name": "Booking Requests",
            "attributes": [
                {"key": "business_id", "type": "string", "size": 255, "required": True},
                {"key": "customer_name", "type": "string", "size": 255, "required": True},
                {"key": "customer_phone", "type": "string", "size": 50, "required": True},
                {"key": "customer_email", "type": "string", "size": 255, "required": False},  # NEW
                {"key": "service_name", "type": "string", "size": 255, "required": False},
                {"key": "preferred_date", "type": "string", "size": 100, "required": False},
                {"key": "preferred_time", "type": "string", "size": 100, "required": False},
                {"key": "notes", "type": "string", "size": 2000, "required": False},
                {"key": "status", "type": "string", "size": 50, "required": True},  # pending, approved, rejected
                {"key": "source", "type": "string", "size": 50, "required": False},  # missed_call, whatsapp, reschedule
                {"key": "original_booking_id", "type": "string", "size": 50, "required": False},  # For reschedule requests
                {"key": "created_at", "type": "string", "size": 100, "required": False}
            ]
        }
    }

    for col_id, col_data in collections.items():

        try:
            print(f"Creating collection '{col_data['name']}' ({col_id})...")
            # Enable document security and set permissions for server access
            databases.create_collection(
                database_id=db_id, 
                collection_id=col_id, 
                name=col_data['name'],
                document_security=True,  # Allow document-level permissions
            )
            # Update collection permissions to allow any user/API key access
            databases.update_collection(
                database_id=db_id,
                collection_id=col_id,
                name=col_data['name'],
                permissions=[
                    'read("any")',
                    'create("any")',
                    'update("any")',
                    'delete("any")'
                ]
            )
            print(f"✅ Collection '{col_data['name']}' created with permissions.")
        except AppwriteException as e:
            if "already exists" in str(e) or "409" in str(e):
                print(f"✅ Collection '{col_data['name']}' already exists.")
                # Try to update permissions on existing collection
                try:
                    databases.update_collection(
                        database_id=db_id,
                        collection_id=col_id,
                        name=col_data['name'],
                        permissions=[
                            'read("any")',
                            'create("any")',
                            'update("any")',
                            'delete("any")'
                        ]
                    )
                    print(f"  → Updated permissions for '{col_data['name']}'.")
                except:
                    pass
            else:
                print(f"⚠️ Error creating collection '{col_data['name']}': {e}")

        # Ensure Attributes exist (run this even if collection exists)
        print(f"Checking attributes for '{col_data['name']}'...")
        for attr in col_data['attributes']:
            try:
                if attr['type'] == 'string':
                    databases.create_string_attribute(
                        database_id=db_id, 
                        collection_id=col_id, 
                        key=attr['key'], 
                        size=attr['size'], 
                        required=attr['required'],
                        default=attr.get('default')
                    )
                elif attr['type'] == 'datetime':
                    databases.create_datetime_attribute(
                        database_id=db_id, 
                        collection_id=col_id, 
                        key=attr['key'], 
                        required=attr['required'],
                        default=attr.get('default')
                    )
                elif attr['type'] == 'integer':
                    databases.create_integer_attribute(
                        database_id=db_id,
                        collection_id=col_id,
                        key=attr['key'],
                        required=attr['required'],
                        min=0,
                        max=1000000,
                        default=attr.get('default')
                    )
                print(f"  - Created attribute '{attr['key']}'")
            except AppwriteException as e:
                # Ignore if attribute already exists
                if "Attribute already exists" in str(e) or "409" in str(e):
                    pass # print(f"  - Attribute '{attr['key']}' exists.")
                else:
                    print(f"    ⚠️ Error creating attribute '{attr['key']}': {e}")

    # 3. Create Indexes for queryable fields
    print("\n--- Creating Indexes ---")
    indexes = [
        {"collection": "bookings", "key": "idx_status", "type": "key", "attributes": ["status"]},
        {"collection": "bookings", "key": "idx_booking_date", "type": "key", "attributes": ["booking_date"]},
        {"collection": "bookings", "key": "idx_date_status", "type": "key", "attributes": ["booking_date", "status"]},
        {"collection": "booking_requests", "key": "idx_req_status", "type": "key", "attributes": ["status"]},
    ]
    
    for idx in indexes:
        try:
            databases.create_index(
                database_id=db_id,
                collection_id=idx["collection"],
                key=idx["key"],
                type=idx["type"],
                attributes=idx["attributes"]
            )
            print(f"✅ Created index '{idx['key']}' on {idx['collection']}")
        except AppwriteException as e:
            if "already exists" in str(e) or "409" in str(e):
                print(f"✅ Index '{idx['key']}' already exists")
            else:
                print(f"⚠️ Error creating index '{idx['key']}': {e}")

if __name__ == "__main__":
    setup_schema()

