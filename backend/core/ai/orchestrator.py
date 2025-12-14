"""
AI Response Orchestrator
Main entry point for generating AI responses with OpenAI.
Coordinates prompt building, tool execution, and multi-step conversations.
"""
from openai import OpenAI
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json
import logging

from core.config import settings
from .prompts import build_enhanced_prompt
from .tools import TOOLS
from .handlers import execute_tool

client = OpenAI(api_key=settings.OPENAI_API_KEY)
logger = logging.getLogger(__name__)
MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")


async def generate_response(history: list, customer_context: str = "", customer_id: str = None, whatsapp_id: str = None) -> str:
    """
    Generates a response from OpenAI with tool calling support.
    Uses business settings from dashboard if configured.
    """
    now = datetime.now(MELBOURNE_TZ)
    current_dt = now.strftime("%A, %B %d, %Y at %I:%M %p Melbourne time")
    
    # Build mini-calendar for next 7 days
    upcoming_lines = ["- Upcoming Days:"]
    for i in range(7):
        future_date = now + timedelta(days=i)
        day_name = future_date.strftime("%A")
        date_str = future_date.strftime("%B %d")
        upcoming_lines.append(f"  • {date_str} = {day_name}")
    upcoming_days = "\n".join(upcoming_lines)
    
    # Build system prompt with customizations
    system = build_enhanced_prompt(
        current_datetime=current_dt,
        upcoming_days=upcoming_days,
        customer_context=customer_context
    )
    
    messages = [{"role": "system", "content": system}]
    
    # Add conversation history (limit to last 15 messages)
    valid_roles = ["user", "assistant", "system", "tool"]
    recent_history = history[-15:] if len(history) > 15 else history
    for msg in recent_history:
        if msg.get("role") in valid_roles:
            messages.append({"role": msg["role"], "content": msg["content"]})
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.7,
            max_tokens=400
        )
        
        assistant_message = response.choices[0].message
        
        if assistant_message.tool_calls:
            return await _handle_tool_calls(
                client, messages, assistant_message,
                customer_id, whatsapp_id
            )
        else:
            logger.info(f"AI direct response (no tools)")
        
        return assistant_message.content
        
    except Exception as e:
        logger.error(f"OpenAI Error: {e}")
        return "I'm having a little trouble right now. Please try again in a moment."


async def _handle_tool_calls(client, messages: list, assistant_message, customer_id: str, whatsapp_id: str) -> str:
    """Handle initial and follow-up tool calls."""
    
    logger.info(f"AI is calling {len(assistant_message.tool_calls)} tool(s)")
    
    # Add assistant message with tool calls
    messages.append({
        "role": "assistant",
        "content": assistant_message.content or "",
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments}
            }
            for tc in assistant_message.tool_calls
        ]
    })
    
    # Execute initial tools
    for tool_call in assistant_message.tool_calls:
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)
        
        logger.info(f"Executing tool: {tool_name}")
        tool_result = await execute_tool(tool_name, tool_args, customer_id, whatsapp_id)
        
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": tool_result
        })
    
    # Handle follow-up tool calls (multi-step operations)
    MAX_FOLLOW_UPS = 5
    for iteration in range(MAX_FOLLOW_UPS):
        follow_up_response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.7,
            max_tokens=400
        )
        
        follow_up_message = follow_up_response.choices[0].message
        
        if follow_up_message.tool_calls:
            logger.info(f"Follow-up iteration {iteration + 1}: {len(follow_up_message.tool_calls)} call(s)")
            
            messages.append({
                "role": "assistant",
                "content": follow_up_message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                    }
                    for tc in follow_up_message.tool_calls
                ]
            })
            
            for tool_call in follow_up_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                tool_result = await execute_tool(tool_name, tool_args, customer_id, whatsapp_id)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result
                })
        else:
            return follow_up_message.content
    
    # Exhausted follow-ups, generate final response
    final_response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.7,
        max_tokens=400
    )
    return final_response.choices[0].message.content
