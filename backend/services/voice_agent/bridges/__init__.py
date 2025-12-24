"""
Voice Agent Bridges Module.

Handles communication with external APIs: Twilio and Deepgram.
"""

from .twilio import TwilioBridge
from .deepgram import DeepgramBridge

__all__ = ['TwilioBridge', 'DeepgramBridge']
