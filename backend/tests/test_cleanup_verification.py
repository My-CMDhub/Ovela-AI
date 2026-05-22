import pytest

def test_whatsapp_imports_are_purged():
    with pytest.raises(ImportError):
        import api.chat
    with pytest.raises(ImportError):
        import services.meta
    with pytest.raises(ImportError):
        import services.chat_agent
