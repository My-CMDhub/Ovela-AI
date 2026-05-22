import pytest
from services.appwrite import db_service

def test_db_service_mixin_integrity():
    # Verify that the AppwriteService successfully inherits and exposes all essential methods
    assert hasattr(db_service, "get_bookings")
    assert hasattr(db_service, "create_booking")
    assert hasattr(db_service, "get_tenant_settings")
    assert hasattr(db_service, "get_tenant_config")
    
    # Assert base DB ID is set
    assert db_service.db_id is not None
    assert db_service.motel_db_id is not None
