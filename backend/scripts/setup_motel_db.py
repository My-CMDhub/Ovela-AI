"""
Motel/Hotel Database Setup Script
Creates collections specifically for accommodation bookings via voice demo.

This is SEPARATE from the WhatsApp/salon collections in setup_appwrite.py.
Run this to set up motel-specific tables for voice booking demos.
"""
import os
import sys
import time
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.exception import AppwriteException

# Ensure the project root is in PYTHONPATH
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from core.config import settings


def wait_for_attribute(databases, db_id, col_id, attr_key, max_wait=20):
    """Wait for an attribute to become available."""
    for _ in range(max_wait):
        try:
            attr = databases.get_attribute(db_id, col_id, attr_key)
            if attr.get('status') == 'available':
                return True
            if attr.get('error'):
                return False
        except:
            pass
        time.sleep(1)
    return False


def setup_motel_database(clean=False):
    """
    Create motel/hotel-specific collections in Appwrite.
    
    Collections created:
    - motel_reservations: Room bookings with check-in/check-out dates
    - motel_rooms: Room inventory and pricing
    - motel_guests: Guest profiles for voice bookings
    """
    client = Client()
    client.set_endpoint(settings.APPWRITE_ENDPOINT)
    client.set_project(settings.APPWRITE_PROJECT_ID)
    client.set_key(settings.APPWRITE_API_KEY)

    databases = Databases(client)
    db_id = "6947b8300005f5863f96"

    print("=" * 60)
    print("🏨 MOTEL/HOTEL DATABASE SETUP")
    print("=" * 60)
    print(f"Database: {db_id}")
    print(f"Endpoint: {settings.APPWRITE_ENDPOINT}")
    print()

    # Define motel-specific collections
    collections = {
        "motel_reservations": {
            "name": "Motel Reservations",
            "description": "Room reservations made via voice or dashboard",
            "attributes": [
                # Guest Information
                {"key": "guest_name", "type": "string", "size": 255, "required": True},
                {"key": "guest_phone", "type": "string", "size": 50, "required": True},
                {"key": "guest_email", "type": "string", "size": 255, "required": False},
                {"key": "num_guests", "type": "integer", "required": False, "default": 1},
                
                # Room Details
                {"key": "room_type", "type": "string", "size": 50, "required": True},  # queen, twin, family, accessible
                {"key": "room_number", "type": "string", "size": 10, "required": False},  # Assigned at check-in
                
                # Dates
                {"key": "check_in_date", "type": "string", "size": 20, "required": True},  # YYYY-MM-DD
                {"key": "check_out_date", "type": "string", "size": 20, "required": True},  # YYYY-MM-DD
                {"key": "num_nights", "type": "integer", "required": False, "default": 1},
                
                # Pricing
                {"key": "rate_per_night", "type": "integer", "required": False, "default": 130},
                {"key": "total_amount", "type": "integer", "required": False, "default": 0},
                {"key": "deposit_paid", "type": "integer", "required": False, "default": 0},
                
                # Status & Tracking
                {"key": "status", "type": "string", "size": 50, "required": True},
                # Statuses: pending, confirmed, checked_in, checked_out, cancelled, no_show
                {"key": "source", "type": "string", "size": 50, "required": False},  # voice_call, website, walk_in, phone
                {"key": "booking_reference", "type": "string", "size": 50, "required": False},  # LM-XXXXXX
                
                # Special Requests
                {"key": "notes", "type": "string", "size": 2000, "required": False},  # Ground floor, extra pillows, etc.
                {"key": "arrival_time", "type": "string", "size": 20, "required": False},  # Expected arrival
                
                # Metadata
                {"key": "created_at", "type": "string", "size": 100, "required": False},
                {"key": "updated_at", "type": "string", "size": 100, "required": False},
                {"key": "created_by", "type": "string", "size": 50, "required": False},  # AI, reception, website
            ]
        },
        "motel_rooms": {
            "name": "Motel Rooms",
            "description": "Room inventory and pricing configuration",
            "attributes": [
                {"key": "room_number", "type": "string", "size": 10, "required": True},  # e.g., "1", "2A"
                {"key": "room_type", "type": "string", "size": 50, "required": True},  # queen, twin, family, accessible
                {"key": "room_name", "type": "string", "size": 100, "required": False},  # Display name
                {"key": "base_rate", "type": "integer", "required": True},  # Price per night in AUD
                {"key": "max_guests", "type": "integer", "required": False, "default": 2},
                {"key": "bed_configuration", "type": "string", "size": 100, "required": False},  # "1 Queen", "1 Queen + 1 Single"
                {"key": "amenities", "type": "string", "size": 500, "required": False},  # JSON array: ["wifi", "tv", "aircon"]
                {"key": "is_accessible", "type": "string", "size": 10, "required": False},  # "true" or "false"
                {"key": "floor_level", "type": "string", "size": 20, "required": False},  # ground, first
                {"key": "status", "type": "string", "size": 50, "required": True},  # available, occupied, maintenance
                {"key": "notes", "type": "string", "size": 500, "required": False},
            ]
        },
        "motel_guests": {
            "name": "Motel Guests",
            "description": "Guest profiles for returning customers",
            "attributes": [
                {"key": "name", "type": "string", "size": 255, "required": True},
                {"key": "phone", "type": "string", "size": 50, "required": True},
                {"key": "email", "type": "string", "size": 255, "required": False},
                {"key": "total_stays", "type": "integer", "required": False, "default": 0},
                {"key": "last_stay_date", "type": "string", "size": 20, "required": False},
                {"key": "preferred_room_type", "type": "string", "size": 50, "required": False},
                {"key": "notes", "type": "string", "size": 2000, "required": False},  # Preferences, allergies, etc.
                {"key": "is_vip", "type": "string", "size": 10, "required": False},  # "true" or "false"
                {"key": "created_at", "type": "string", "size": 100, "required": False},
            ]
        }
    }

    # Clean existing collections if requested
    if clean:
        print("🧹 Cleaning existing motel collections...")
        for col_id in collections.keys():
            try:
                databases.delete_collection(database_id=db_id, collection_id=col_id)
                print(f"  - Deleted '{col_id}'")
                time.sleep(2)
            except:
                pass
        print()

    # Create collections
    for col_id, col_data in collections.items():
        print(f"📦 Creating collection: {col_data['name']} ({col_id})")
        
        try:
            databases.create_collection(
                database_id=db_id,
                collection_id=col_id,
                name=col_data['name'],
                document_security=True,
            )
            # Set permissions for API access
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
            print(f"   ✅ Collection created with permissions")
        except AppwriteException as e:
            if "already exists" in str(e) or "409" in str(e):
                print(f"   ✅ Collection already exists - updating permissions")
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
                except:
                    pass
            else:
                print(f"   ⚠️ Error: {e}")
                continue

        # Create attributes
        print(f"   Creating {len(col_data['attributes'])} attributes...")
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
                
                # Wait for attribute to be ready
                wait_for_attribute(databases, db_id, col_id, attr['key'])
                
            except AppwriteException as e:
                if "already exists" not in str(e) and "409" not in str(e):
                    print(f"      ⚠️ Error creating '{attr['key']}': {e}")
        
        print(f"   ✅ Attributes created")
        print()

    # Create indexes for efficient querying
    print("📇 Creating indexes...")
    indexes = [
        # Reservation indexes
        {"collection": "motel_reservations", "key": "idx_checkin", "type": "key", "attributes": ["check_in_date"]},
        {"collection": "motel_reservations", "key": "idx_status", "type": "key", "attributes": ["status"]},
        {"collection": "motel_reservations", "key": "idx_guest_phone", "type": "key", "attributes": ["guest_phone"]},
        {"collection": "motel_reservations", "key": "idx_room_type", "type": "key", "attributes": ["room_type"]},
        {"collection": "motel_reservations", "key": "idx_booking_ref", "type": "key", "attributes": ["booking_reference"]},
        
        # Room indexes
        {"collection": "motel_rooms", "key": "idx_room_type", "type": "key", "attributes": ["room_type"]},
        {"collection": "motel_rooms", "key": "idx_room_status", "type": "key", "attributes": ["status"]},
        
        # Guest indexes
        {"collection": "motel_guests", "key": "idx_guest_phone", "type": "key", "attributes": ["phone"]},
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
            print(f"   ✅ Index '{idx['key']}' on {idx['collection']}")
        except AppwriteException as e:
            if "already exists" in str(e) or "409" in str(e):
                print(f"   ✅ Index '{idx['key']}' already exists")
            else:
                print(f"   ⚠️ Error: {e}")

    print()
    print("=" * 60)
    print("✅ MOTEL DATABASE SETUP COMPLETE!")
    print("=" * 60)
    print()
    print("Collections created:")
    print("  • motel_reservations - Room bookings with dates/pricing")
    print("  • motel_rooms - Room inventory and configuration")
    print("  • motel_guests - Guest profiles")
    print()
    print("Next: Update voice_deepgram_agent.py to use these collections")
    print()


def seed_room_inventory():
    """Seed the motel_rooms collection with The Lydoun Motel's rooms."""
    client = Client()
    client.set_endpoint(settings.APPWRITE_ENDPOINT)
    client.set_project(settings.APPWRITE_PROJECT_ID)
    client.set_key(settings.APPWRITE_API_KEY)

    databases = Databases(client)
    db_id = "ovela_db"
    
    print("🛏️ Seeding room inventory for The Lydoun Motel...")
    
    from appwrite.id import ID
    
    rooms = [
        # Queen Rooms (6 total)
        {"room_number": "1", "room_type": "queen", "room_name": "Queen Room", "base_rate": 130, "max_guests": 2, "bed_configuration": "1 Queen", "floor_level": "ground", "status": "available"},
        {"room_number": "2", "room_type": "queen", "room_name": "Queen Room", "base_rate": 130, "max_guests": 2, "bed_configuration": "1 Queen", "floor_level": "ground", "status": "available"},
        {"room_number": "3", "room_type": "queen", "room_name": "Queen Room", "base_rate": 130, "max_guests": 2, "bed_configuration": "1 Queen", "floor_level": "ground", "status": "available"},
        {"room_number": "4", "room_type": "queen", "room_name": "Queen Room", "base_rate": 130, "max_guests": 2, "bed_configuration": "1 Queen", "floor_level": "ground", "status": "available"},
        {"room_number": "5", "room_type": "queen", "room_name": "Queen Room", "base_rate": 130, "max_guests": 2, "bed_configuration": "1 Queen", "floor_level": "ground", "status": "available"},
        {"room_number": "6", "room_type": "queen", "room_name": "Queen Room", "base_rate": 130, "max_guests": 2, "bed_configuration": "1 Queen", "floor_level": "ground", "status": "available"},
        
        # Twin Rooms (4 total)
        {"room_number": "7", "room_type": "twin", "room_name": "Twin Room", "base_rate": 140, "max_guests": 3, "bed_configuration": "1 Queen + 1 Single", "floor_level": "ground", "status": "available"},
        {"room_number": "8", "room_type": "twin", "room_name": "Twin Room", "base_rate": 140, "max_guests": 3, "bed_configuration": "1 Queen + 1 Single", "floor_level": "ground", "status": "available"},
        {"room_number": "9", "room_type": "twin", "room_name": "Twin Room", "base_rate": 140, "max_guests": 3, "bed_configuration": "1 Queen + 1 Single", "floor_level": "ground", "status": "available"},
        {"room_number": "10", "room_type": "twin", "room_name": "Twin Room", "base_rate": 140, "max_guests": 3, "bed_configuration": "1 Queen + 1 Single", "floor_level": "ground", "status": "available"},
        
        # Family Rooms (3 total)
        {"room_number": "11", "room_type": "family", "room_name": "Family Room", "base_rate": 160, "max_guests": 4, "bed_configuration": "1 Queen + 2 Singles", "floor_level": "ground", "status": "available"},
        {"room_number": "12", "room_type": "family", "room_name": "Family Room", "base_rate": 160, "max_guests": 4, "bed_configuration": "1 Queen + 2 Singles", "floor_level": "ground", "status": "available"},
        {"room_number": "13", "room_type": "family", "room_name": "Family Room", "base_rate": 160, "max_guests": 4, "bed_configuration": "1 Queen + 2 Singles", "floor_level": "ground", "status": "available"},
        
        # Accessible Rooms (2 total)
        {"room_number": "14", "room_type": "accessible", "room_name": "Accessible Room", "base_rate": 130, "max_guests": 2, "bed_configuration": "1 Queen", "is_accessible": "true", "floor_level": "ground", "status": "available", "notes": "Flat floor entry, open shower with rails and stool"},
        {"room_number": "15", "room_type": "accessible", "room_name": "Accessible Room", "base_rate": 130, "max_guests": 2, "bed_configuration": "1 Queen", "is_accessible": "true", "floor_level": "ground", "status": "available", "notes": "Flat floor entry, open shower with rails and stool"},
    ]
    
    for room in rooms:
        try:
            result = databases.create_document(
                database_id=db_id,
                collection_id="motel_rooms",
                document_id=ID.unique(),
                data=room
            )
            print(f"  ✅ Room {room['room_number']} ({room['room_type']}) created")
        except AppwriteException as e:
            print(f"  ⚠️ Error creating room {room['room_number']}: {e}")
    
    print()
    print("✅ Room inventory seeded!")
    print("   Total: 15 rooms (6 Queen, 4 Twin, 3 Family, 2 Accessible)")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Setup motel database collections")
    parser.add_argument("--clean", action="store_true", help="Delete and recreate collections")
    parser.add_argument("--seed", action="store_true", help="Seed room inventory after setup")
    args = parser.parse_args()
    
    setup_motel_database(clean=args.clean)
    
    if args.seed:
        seed_room_inventory()
