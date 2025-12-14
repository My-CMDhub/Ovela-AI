from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.query import Query
from core.config import settings
import sys

def test_query():
    client = Client()
    client.set_endpoint(settings.APPWRITE_ENDPOINT)
    client.set_project(settings.APPWRITE_PROJECT_ID)
    client.set_key(settings.APPWRITE_API_KEY)
    
    databases = Databases(client)
    db_id = "ovela_db"
    
    print(f"Testing connection to {settings.APPWRITE_ENDPOINT}...")
    
    try:
        # Try a simple GET first
        print("1. Testing databases.get()...")
        databases.get(db_id)
        print("✅ databases.get() passed.")
    except Exception as e:
        print(f"❌ databases.get() failed: {e}")

    try:
        # Try list_documents with queries
        print("2. Testing list_documents with queries...")
        whatsapp_id = "test_user_123"
        business_id = "default_business"
        
        result = databases.list_documents(
            database_id=db_id,
            collection_id="conversations",
            queries=[
                Query.equal("whatsapp_id", whatsapp_id),
                Query.equal("business_id", business_id)
            ]
        )
        print(f"✅ list_documents passed. Found: {len(result['documents'])}")
    except Exception as e:
        print(f"❌ list_documents failed: {e}")

if __name__ == "__main__":
    test_query()
