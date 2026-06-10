import os
import asyncio
import json
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.exception import AppwriteException

async def main():
    from dotenv import load_dotenv
    load_dotenv()
    
    endpoint = os.getenv("APPWRITE_ENDPOINT", "https://api.ovela.dev/v1")
    project_id = os.getenv("APPWRITE_PROJECT_ID")
    api_key = os.getenv("APPWRITE_API_KEY")
    db_id = "6947b8300005f5863f96"
    
    if not project_id or not api_key:
        print("Missing credentials")
        return

    client = Client()
    client.set_endpoint(endpoint)
    client.set_project(project_id)
    client.set_key(api_key)

    databases = Databases(client)

    try:
        # Get coalcreek tenant
        tenants = databases.list_documents(db_id, "tenants", queries=[])
        coalcreek_doc = None
        for t in tenants.get("documents", []):
            if t["slug"] == "coalcreek":
                coalcreek_doc = t
                break
                
        if not coalcreek_doc:
            print("Coalcreek tenant not found! Will create a new one.")
        else:
            print(f"Found coalcreek tenant: {coalcreek_doc['$id']}")
        
        # Build the dynamic config for the user
        config_obj = {
            "voice_settings": {
                "voice_id": "f786b574-daa5-4673-aa0c-cbe3e8534c02",
                "speed": "normal",
                "volume": 0.8,
                "llm_model": "gemini-2.5-flash"
            }
        }
        
        data = {
            "slug": "coalcreek",
            "name": "Coal Creek Motel",
            "twilio_phone": "+61468088990",
            "business_phone": "+61468088990",
            "staff_email": "officialcoalcreek@gmail.com",
            "owner_email": "officialcoalcreek@gmail.com",
            "config": json.dumps(config_obj)
        }
        
        if coalcreek_doc:
            databases.update_document(db_id, "tenants", coalcreek_doc['$id'], data)
            print("Successfully updated coalcreek tenant.")
        else:
            from appwrite.id import ID
            databases.create_document(db_id, "tenants", ID.unique(), data)
            print("Successfully created coalcreek tenant.")
        
    except AppwriteException as e:
        print(f"Appwrite Error: {e.message}")

if __name__ == "__main__":
    asyncio.run(main())
