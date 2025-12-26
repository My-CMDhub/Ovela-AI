from fastapi import APIRouter, Request, HTTPException, Query
from core.config import settings
from services.appwrite import db_service
from services.chat_agent import meta_service, generate_response
from services.customers import customer_service
import json
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/meta")
async def verify_webhook(
    mode: str = Query(..., alias="hub.mode"),
    token: str = Query(..., alias="hub.verify_token"),
    challenge: str = Query(..., alias="hub.challenge")
):
    """
    Verifies the webhook for Meta.
    """
    if mode == "subscribe" and token == settings.META_VERIFY_TOKEN:
        logger.info("Webhook verified successfully!")
        return int(challenge)
    
    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/meta")
async def handle_webhook(request: Request):
    """
    Receives messages from WhatsApp.
    """
    try:
        payload = await request.json()
        # logger.info(f"Received payload: {payload}")
        
        # Check if it's a message
        entry = payload.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        
        if not messages:
            return {"status": "ignored", "reason": "no_messages"}
            
        msg = messages[0]
        whatsapp_id = msg.get("from") # User's phone number
        text_body = msg.get("text", {}).get("body")
        business_phone_id = value.get("metadata", {}).get("phone_number_id")
        
        if not text_body:
             return {"status": "ignored", "reason": "not_text_message"}
             
        # 1. Get/Create Customer & Check Cooldown
        # Provide a default business ID if business_phone_id is missing or specific one
        business_id = business_phone_id or "default_business"
        
        customer = customer_service.get_or_create_customer(whatsapp_id, business_id)
        
        if customer and customer_service.check_cooldown(customer):
            logger.warning(f"Ignoring message from {whatsapp_id} due to cooldown.")
            # Return 200 OK so WhatsApp doesn't retry
            return {"status": "ignored_cooldown"}
            
        customer_context = customer_service.get_customer_context(customer)
        customer_id = customer['$id'] if customer else None
             
        # 2. Get/Create Conversation
        conversation = db_service.get_or_create_conversation(whatsapp_id, business_id)
        if not conversation:
            logger.error("Failed to get/create conversation")
            return {"status": "error"}
            
        conv_id = conversation['$id']
        history_str = conversation.get('history', '[]')
        history = json.loads(history_str) if history_str else []

        # 3. Save User Message
        db_service.append_message(conv_id, "user", text_body, history_str)
        
        # 3.5 Check Token Rate Limit
        business_settings = db_service.get_all_settings()
        business_phone = (business_settings.get("business_phone") if business_settings else None) or "our team"
        
        can_proceed, limit_status, limit_message = db_service.check_token_limit(conversation, business_phone)
        
        if not can_proceed:
            # User is blocked - send block message and don't call AI
            await meta_service.send_text_message(whatsapp_id, limit_message)
            logger.warning(f"Token limit exceeded for {whatsapp_id}")
            return {"status": "rate_limited", "message": limit_message}
        
        # 4. Generate Answer
        # Add user msg to history for AI context
        current_history = history + [{"role": "user", "content": text_body}]
        
        # Generate response passing customer context, ID, and whatsapp_id
        ai_response = await generate_response(
            current_history, 
            customer_context=customer_context,
            customer_id=customer_id,
            whatsapp_id=whatsapp_id
        )
        
        # 4.5 Update Token Usage (estimate: input + output tokens)
        # Rough estimate: 1 token ≈ 4 chars
        estimated_tokens = (len(text_body) + len(ai_response)) // 4
        current_tokens = conversation.get("tokens_used_today", 0) or 0
        db_service.update_token_usage(conv_id, estimated_tokens, current_tokens)
        
        # If approaching limit, append warning to response
        if limit_status == "warning" and limit_message:
            ai_response = f"{ai_response}\n\n---\n\n{limit_message}"
        
        # 5. Save AI Response
        updated_history_str = json.dumps(current_history) # This history doesn't include the new AI msg yet
        # We need to append the AI message to the DB using the `append_message` helper which handles parsing
        # But wait, `append_message` takes `current_history` string? 
        # `db_service.append_message` appends to the history list inside Appwrite.
        # Let's see `db_service.append_message` logic if possible.
        # Assuming usage: db_service.append_message(conv_id, "assistant", ai_response, updated_history_str)
        
        # Actually, let's just use what was working before:
        db_service.append_message(conv_id, "assistant", ai_response, updated_history_str)
        
        # 6. Send back to WhatsApp
        await meta_service.send_text_message(whatsapp_id, ai_response)
        
        logger.info(f"AI Response sent to {whatsapp_id}: {ai_response}")
        
        return {"status": "processed", "reply": ai_response}
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return {"status": "error", "detail": str(e)}

