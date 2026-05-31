"""
Memory Consolidation Service
Handles conversation summarization and token-efficient memory management.
"""
import os
from google import genai
from core.config import settings
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json
import logging

logger = logging.getLogger(__name__)
client = genai.Client(
    vertexai=True,
    project=os.getenv("GOOGLE_CLOUD_PROJECT", "project-bd29d7f8-c65f-4597-b7b"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
)

MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")

# Thresholds for consolidation
MESSAGE_THRESHOLD = 20  # Consolidate after this many messages
INACTIVITY_HOURS = 1    # Consolidate after this much inactivity
MAX_SUMMARY_LENGTH = 1000  # Max chars for summary
MAX_PROFILE_LENGTH = 500   # Max chars for ultra-compact profile

CONSOLIDATION_PROMPT = """You are a memory consolidation assistant. Create a VERY concise summary of this conversation.

Include ONLY:
- Customer's name and email (if mentioned)
- Services they were interested in or booked
- Their preferences (time, specific treatments)
- Any important notes (allergies, special requests)

EXCLUDE:
- Greetings, pleasantries
- Off-topic discussion
- Repeated information

Output format (JSON):
{
    "name": "Customer Name or null",
    "email": "email@example.com or null",
    "services_discussed": ["service1", "service2"],
    "preferences": "Brief note about preferences",
    "bookings_made": ["booking_id1"],
    "summary": "1-2 sentence summary of the conversation"
}
"""

ULTRA_COMPACT_PROMPT = """You are compressing a customer profile that has grown too large.

Create an ULTRA-COMPACT profile with ONLY:
- Name
- Email  
- Last 10-15 services they've used (most recent)
- Key preferences (1 sentence max)
- Total booking count

Output as a single paragraph, max 500 characters.
"""


class MemoryService:
    """Handles conversation summarization and memory consolidation."""
    
    def should_consolidate(self, conversation: dict, last_interaction: str = None) -> bool:
        """
        Determine if conversation should be consolidated.
        Returns True if:
        - Messages exceed threshold OR
        - User has been inactive for > INACTIVITY_HOURS
        """
        try:
            history = conversation.get("history", "[]")
            if isinstance(history, str):
                history = json.loads(history)
            
            # Check message count
            if len(history) >= MESSAGE_THRESHOLD:
                return True
            
            # Check inactivity
            if last_interaction:
                try:
                    last_dt = datetime.fromisoformat(last_interaction.replace("Z", "+00:00"))
                    now = datetime.now(MELBOURNE_TZ)
                    if (now - last_dt.astimezone(MELBOURNE_TZ)) > timedelta(hours=INACTIVITY_HOURS):
                        return True
                except:
                    pass
            
            return False
        except Exception as e:
            logger.error(f"Error checking consolidation: {e}")
            return False
    
    async def consolidate_conversation(self, history: list) -> dict:
        """
        Use Gemini 2.5 Flash via Vertex AI to summarize a conversation into structured memory.
        Returns dict with extracted info.
        """
        try:
            import asyncio
            # Build conversation text
            conv_text = "\n".join([
                f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
                for msg in history
            ])
            
            response = await asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.5-flash",
                contents=conv_text,
                config=genai.types.GenerateContentConfig(
                    system_instruction=CONSOLIDATION_PROMPT,
                    temperature=0.3,
                    max_tokens=300
                )
            )
            
            result_text = response.text
            
            # Try to parse as JSON
            try:
                # Clean up potential markdown
                if "```json" in result_text:
                    result_text = result_text.split("```json")[1].split("```")[0]
                elif "```" in result_text:
                    result_text = result_text.split("```")[1].split("```")[0]
                
                return json.loads(result_text.strip())
            except json.JSONDecodeError:
                # Fallback: return as plain summary
                return {"summary": result_text[:MAX_SUMMARY_LENGTH]}
                
        except Exception as e:
            logger.error(f"Error consolidating conversation: {e}")
            return {"summary": "Unable to summarize", "error": str(e)}
    
    async def compact_profile(self, current_summary: str) -> str:
        """
        Ultra-compact a profile that has grown too large using Gemini 2.5 Flash.
        Used when even summaries get too long over time.
        """
        try:
            if len(current_summary) <= MAX_PROFILE_LENGTH:
                return current_summary
            
            import asyncio
            response = await asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.5-flash",
                contents=current_summary,
                config=genai.types.GenerateContentConfig(
                    system_instruction=ULTRA_COMPACT_PROMPT,
                    temperature=0.3,
                    max_tokens=200
                )
            )
            
            compacted = response.text
            return compacted[:MAX_PROFILE_LENGTH]
            
        except Exception as e:
            logger.error(f"Error compacting profile: {e}")
            # Fallback: just truncate
            return current_summary[:MAX_PROFILE_LENGTH]
    
    def build_context_from_summary(self, summary_data: dict) -> str:
        """
        Build AI context string from consolidated summary.
        """
        parts = []
        
        if summary_data.get("name"):
            parts.append(f"Name: {summary_data['name']}")
        if summary_data.get("email"):
            parts.append(f"Email: {summary_data['email']}")
        if summary_data.get("services_discussed"):
            parts.append(f"Interested in: {', '.join(summary_data['services_discussed'][:5])}")
        if summary_data.get("preferences"):
            parts.append(f"Preferences: {summary_data['preferences']}")
        if summary_data.get("summary"):
            parts.append(f"Summary: {summary_data['summary']}")
        
        return "\n".join(parts) if parts else ""


memory_service = MemoryService()
