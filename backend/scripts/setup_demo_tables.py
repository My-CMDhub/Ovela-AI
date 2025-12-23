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


def wait_for_attribute(databases, db_id, col_id, attr_key):
    """Wait for an attribute to become available."""
    print(f"  - Waiting for attribute '{attr_key}'...")
    for _ in range(20):  # Wait up to 20 seconds
        try:
            attr = databases.get_attribute(db_id, col_id, attr_key)
            if attr.get('status') == 'available':
                print(f"  - Attribute '{attr_key}' is available.")
                return True
            if attr.get('error'):
                print(f"  ⚠️ Attribute '{attr_key}' error: {attr['error']}")
                return False
        except:
            pass
        time.sleep(1)
    print(f"  ⚠️ Timeout waiting for attribute '{attr_key}'.")
    return False


def setup_demo_tables(clean=True):
    """Create demo analytics collections in Appwrite."""
    client = Client()
    client.set_endpoint(settings.APPWRITE_ENDPOINT)
    client.set_project(settings.APPWRITE_PROJECT_ID)
    client.set_key(settings.APPWRITE_API_KEY)

    databases = Databases(client)
    db_id = "ovela_db"

    # Define new collections for demo analytics
    collections = {
        "demo_leads": {
            "name": "Demo Leads",
            "attributes": [
                {"key": "name", "type": "string", "size": 255, "required": True},
                {"key": "business_name", "type": "string", "size": 255, "required": False},
                {"key": "phone", "type": "string", "size": 50, "required": True},
                {"key": "status", "type": "string", "size": 50, "required": True},  # pending, called, completed, failed
                {"key": "call_sid", "type": "string", "size": 100, "required": False},  # Twilio Call SID
                {"key": "call_duration_seconds", "type": "integer", "required": False, "default": 0},
                {"key": "source", "type": "string", "size": 50, "required": False},  # website, landing_page, etc.
                {"key": "created_at", "type": "string", "size": 100, "required": False},
                {"key": "updated_at", "type": "string", "size": 100, "required": False},
            ]
        },
        "demo_transcripts": {
            "name": "Demo Transcripts",
            "attributes": [
                {"key": "demo_lead_id", "type": "string", "size": 100, "required": False},  # Link to demo_leads
                {"key": "call_sid", "type": "string", "size": 100, "required": False},  # Twilio Call SID for lookup
                {"key": "phone", "type": "string", "size": 50, "required": True},
                {"key": "transcript_json", "type": "string", "size": 100000, "required": False},  # Full transcript
                {"key": "exchange_count", "type": "integer", "required": False, "default": 0},
                {"key": "duration_seconds", "type": "integer", "required": False, "default": 0},
                {"key": "outcome", "type": "string", "size": 50, "required": False},  # completed, abandoned, limit_reached, silence_timeout
                {"key": "ai_feedback", "type": "string", "size": 10000, "required": False},  # Mistral's analysis
                {"key": "feedback_score", "type": "integer", "required": False},  # 1-10 quality score
                {"key": "issues_found", "type": "string", "size": 5000, "required": False},  # JSON array of issues
                {"key": "created_at", "type": "string", "size": 100, "required": False},
            ]
        }
    }

    # Clean existing collections if requested
    if clean:
        for col_id in collections.keys():
            try:
                print(f"Deleting existing collection '{col_id}' for a clean start...")
                databases.delete_collection(database_id=db_id, collection_id=col_id)
                time.sleep(2)  # Wait for deletion
            except:
                pass

    # Create collections and attributes
    for col_id, col_data in collections.items():
        try:
            print(f"Creating collection '{col_data['name']}' ({col_id})...")
            databases.create_collection(
                database_id=db_id,
                collection_id=col_id,
                name=col_data['name'],
                document_security=True,
            )
            # Set permissions
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
        except AppwriteException as e:
            if "already exists" not in str(e):
                print(f"⚠️ Error creating collection '{col_id}': {e}")
                continue

        # Create attributes and WAIT for each
        for attr in col_data['attributes']:
            try:
                print(f"  - Creating attribute '{attr['key']}'...")
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
                        max=10000000,
                        default=attr.get('default')
                    )
                
                # WAIT for attribute to be ready
                wait_for_attribute(databases, db_id, col_id, attr['key'])
                
            except AppwriteException as e:
                if "already exists" not in str(e):
                    print(f"    ⚠️ Error creating attribute '{attr['key']}': {e}")

    # Create indexes ONLY after attributes are ready
    print("\n--- Creating Indexes ---")
    indexes = [
        {"collection": "demo_leads", "key": "idx_phone", "type": "key", "attributes": ["phone"]},
        {"collection": "demo_leads", "key": "idx_status", "type": "key", "attributes": ["status"]},
        {"collection": "demo_transcripts", "key": "idx_call_sid", "type": "key", "attributes": ["call_sid"]},
        {"collection": "demo_transcripts", "key": "idx_phone", "type": "key", "attributes": ["phone"]},
    ]

    for idx in indexes:
        try:
            print(f"Creating index '{idx['key']}' on {idx['collection']}...")
            databases.create_index(
                database_id=db_id,
                collection_id=idx["collection"],
                key=idx["key"],
                type=idx["type"],
                attributes=idx["attributes"]
            )
            print(f"✅ Created index '{idx['key']}'")
        except AppwriteException as e:
            print(f"⚠️ Error creating index '{idx['key']}': {e}")

    print("\n✅ Demo analytics tables setup complete!")


if __name__ == "__main__":
    setup_demo_tables(clean=True)

