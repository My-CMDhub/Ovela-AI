"""
Lock/Unlock Industry Script
This script allows you to lock or unlock the industry setting for a specific business.
When locked, the business owner cannot change the industry from the settings page.

Usage:
    python lock_industry.py lock beauty
    python lock_industry.py unlock
    python lock_industry.py status
"""
import sys
import json
import os
from dotenv import load_dotenv
from appwrite.client import Client
from appwrite.services.databases import Databases

# Load environment variables
load_dotenv()

# Appwrite configuration
APPWRITE_ENDPOINT = os.getenv("APPWRITE_ENDPOINT", "https://cloud.appwrite.io/v1")
APPWRITE_PROJECT_ID = os.getenv("APPWRITE_PROJECT_ID")
APPWRITE_API_KEY = os.getenv("APPWRITE_API_KEY")
DATABASE_ID = os.getenv("APPWRITE_DATABASE_ID", "ovela_db")
BUSINESSES_COLLECTION_ID = "businesses"

DEFAULT_BUSINESS_ID = "default_business"

# Initialize Appwrite client
client = Client()
client.set_endpoint(APPWRITE_ENDPOINT)
client.set_project(APPWRITE_PROJECT_ID)
client.set_key(APPWRITE_API_KEY)

databases = Databases(client)


def lock_industry(business_id: str, industry: str):
    """
    Lock a business to a specific industry.
    
    Args:
        business_id: The business ID to lock
        industry: The industry to lock to (beauty, health, fitness, professional, hospitality, retail)
    """
    try:
        # Get existing business
        business = databases.get_document(DATABASE_ID, BUSINESSES_COLLECTION_ID, business_id)
        
        # Get existing settings
        settings_json = business.get("system_prompt_override", "{}")
        try:
            settings = json.loads(settings_json)
        except json.JSONDecodeError:
            settings = {}
        
        # Add industry lock
        settings["industry_locked"] = True
        
        # Update business with locked industry
        databases.update_document(
            DATABASE_ID,
            BUSINESSES_COLLECTION_ID,
            business_id,
            {
                "industry": industry,
                "system_prompt_override": json.dumps(settings)
            }
        )
        
        print(f"✅ Successfully locked '{business_id}' to '{industry}' industry")
        print(f"   The business owner can no longer change the industry setting.")
        return True
        
    except Exception as e:
        print(f"❌ Error locking industry: {e}")
        return False


def unlock_industry(business_id: str):
    """
    Unlock the industry setting for a business.
    
    Args:
        business_id: The business ID to unlock
    """
    try:
        # Get existing business
        business = databases.get_document(DATABASE_ID, BUSINESSES_COLLECTION_ID, business_id)
        
        # Get existing settings
        settings_json = business.get("system_prompt_override", "{}")
        try:
            settings = json.loads(settings_json)
        except json.JSONDecodeError:
            settings = {}
        
        # Remove industry lock
        settings["industry_locked"] = False
        
        # Update business
        databases.update_document(
            DATABASE_ID,
            BUSINESSES_COLLECTION_ID,
            business_id,
            {
                "system_prompt_override": json.dumps(settings)
            }
        )
        
        print(f"✅ Successfully unlocked industry for '{business_id}'")
        print(f"   The business owner can now change the industry setting.")
        return True
        
    except Exception as e:
        print(f"❌ Error unlocking industry: {e}")
        return False


def check_lock_status(business_id: str):
    """Check if industry is locked for a business."""
    try:
        business = databases.get_document(DATABASE_ID, BUSINESSES_COLLECTION_ID, business_id)
        
        settings_json = business.get("system_prompt_override", "{}")
        try:
            settings = json.loads(settings_json)
        except json.JSONDecodeError:
            settings = {}
        
        is_locked = settings.get("industry_locked", False)
        current_industry = business.get("industry", "unknown")
        
        print(f"\n📊 Lock Status for '{business_id}':")
        print(f"   Industry: {current_industry}")
        print(f"   Locked: {'🔒 Yes' if is_locked else '🔓 No'}")
        
    except Exception as e:
        print(f"❌ Error checking lock status: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("Industry Lock Manager")
    print("=" * 60)
    
    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  Lock:   python lock_industry.py lock <industry>")
        print("  Unlock: python lock_industry.py unlock")
        print("  Status: python lock_industry.py status")
        print("\nIndustries: beauty, health, fitness, professional, hospitality, retail")
        print("\nExample:")
        print("  python lock_industry.py lock beauty")
        sys.exit(1)
    
    action = sys.argv[1].lower()
    
    if action == "lock":
        if len(sys.argv) < 3:
            print("❌ Please specify an industry to lock to")
            print("   Industries: beauty, health, fitness, professional, hospitality, retail")
            sys.exit(1)
        
        industry = sys.argv[2].lower()
        valid_industries = ["beauty", "health", "fitness", "professional", "hospitality", "retail"]
        
        if industry not in valid_industries:
            print(f"❌ Invalid industry '{industry}'")
            print(f"   Valid industries: {', '.join(valid_industries)}")
            sys.exit(1)
        
        lock_industry(DEFAULT_BUSINESS_ID, industry)
        
    elif action == "unlock":
        unlock_industry(DEFAULT_BUSINESS_ID)
        
    elif action == "status":
        check_lock_status(DEFAULT_BUSINESS_ID)
        
    else:
        print(f"❌ Unknown action '{action}'")
        print("   Valid actions: lock, unlock, status")
        sys.exit(1)
    
    print("=" * 60)
