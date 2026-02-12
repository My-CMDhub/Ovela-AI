import asyncio
import os
import aiosmtplib
from email.message import EmailMessage
import sys

# Add parent directory to path to import settings
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.config import settings

async def test_smtp_connection():
    print("--- SMTP Connection Test ---")
    print(f"Host: {settings.SMTP_HOST}")
    print(f"Port: {settings.SMTP_PORT}")
    print(f"User: {settings.SMTP_USER}")
    
    if not settings.SMTP_PASSWORD:
        print("❌ Error: SMTP_PASSWORD is not set in environment.")
        return

    message = EmailMessage()
    message["From"] = settings.MAIL_FROM
    message["To"] = settings.SMTP_USER  # Send to self for test
    message["Subject"] = "Zoho SMTP Test Connection"
    message.set_content("This is a test email to verify Zoho SMTP configuration via aiosmtplib.")

    try:
        use_tls = (settings.SMTP_PORT == 587)
        print(f"Connecting to SMTP (TLS={not use_tls})...")
        
        async with aiosmtplib.SMTP(
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            use_tls=not use_tls
        ) as smtp:
            if use_tls:
                print("Starting TLS...")
                await smtp.starttls()
            
            print("Logging in...")
            await smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            
            print("Sending message...")
            await smtp.send_message(message)
            
        print("✅ Success! Test email sent.")
    except Exception as e:
        print(f"❌ Failed to send test email: {e}")

if __name__ == "__main__":
    asyncio.run(test_smtp_connection())
