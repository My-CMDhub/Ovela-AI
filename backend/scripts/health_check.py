from appwrite.client import Client
from appwrite.services.databases import Databases
import os
import sys

# Setup paths
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)

from core.config import settings

def check_health():
    print("🏥 Checking Appwrite API Health...")
    
    client = Client()
    client.set_endpoint(settings.APPWRITE_ENDPOINT)
    client.set_project(settings.APPWRITE_PROJECT_ID)
    client.set_key(settings.APPWRITE_API_KEY)
    
    databases = Databases(client)
    db_id = "ovela_db"
    
    try:
        # 1. Try to fetch Database details
        print(f"👉 Fetching database '{db_id}'...")
        db = databases.get(db_id)
        print(f"✅ Database OK: {db.get('name')} (ID: {db.get('$id')})")
        
        # 2. Try to fetch Collections
        print("👉 Fetching collections...")
        collections = databases.list_collections(db_id)
        count = collections.get('total', 0)
        print(f"✅ Collections OK: Found {count}")
        for col in collections.get('collections', []):
            print(f"   - {col.get('name')} ({col.get('$id')})")
            
        # 3. Try to fetch a Business Document (Settings)
        print("👉 Fetching business settings (using default_business)...")
        try:
            doc = databases.get_document(db_id, "businesses", "default_business")
            print(f"✅ Settings OK: {doc.get('name')}")
        except Exception as e:
            print(f"⚠️ Could not fetch default business (might not exist yet): {e}")

        print("\n🎉 CONCLUSION: Appwrite API is WORKING for this project.")
        print("The '500 Error' in the console is likely a transient UI/Cloud issue, not an API outage.")
        
    except Exception as e:
        print("\n❌ APPWRITE API FAILED")
        print(f"Error: {e}")

if __name__ == "__main__":
    check_health()
