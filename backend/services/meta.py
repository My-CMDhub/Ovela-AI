"""
Meta (WhatsApp) Service - Compatibility Shim.

This file re-exports MetaService from its new location in services.chat_agent.
Maintained for backwards compatibility with existing imports.

New code should import from: services.chat_agent.meta_service
"""

from services.chat_agent.meta_service import MetaService, meta_service

__all__ = ['MetaService', 'meta_service']
