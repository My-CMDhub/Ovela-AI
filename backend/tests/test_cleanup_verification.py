import pytest

def test_whatsapp_imports_are_purged():
    with pytest.raises(ImportError):
        import api.chat
    with pytest.raises(ImportError):
        import services.meta
    with pytest.raises(ImportError):
        import services.chat_agent

def test_dhruv_personal_imports_are_purged():
    with pytest.raises(ImportError):
        import services.voice_agent.prompts_dhruv
    with pytest.raises(ImportError):
        import services.voice_agent.functions.dhruv_personal
