"""
Email Service via Resend
Handles sending transactional emails for bookings with Ovela-branded design.
"""
import httpx
from core.config import settings
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")


class EmailService:
    API_URL = "https://api.resend.com/emails"
    
    def __init__(self):
        self.api_key = settings.RESEND_API_KEY
        self.default_from_email = settings.RESEND_FROM_EMAIL or "Ovela <appointments@ovela.dev>"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _base_template(self, badge: str, title: str, content: str, business_name: str = "Ovela Business", steps: list = None, button_text: str = None, button_url: str = None, closing_text: str = "") -> str:
        """Generate Ovela-branded email HTML matching the waitlist design."""
        
        steps_html = ""
        if steps:
            steps_html = f"""
            <div style="background: #f9f9fa; border: 1px solid #e5e5e7; border-radius: 12px; padding: 24px; margin: 32px 0;">
                <div style="font-size: 14px; font-weight: 700; color: #1d1d1f; margin-bottom: 20px; text-transform: uppercase; letter-spacing: 0.5px;">Appointment Details</div>
                <table style="width: 100%; border-collapse: collapse;" border="0" cellpadding="0" cellspacing="0">
                    {"".join([f'''
                    <tr>
                        <td style="width: 40px; vertical-align: top; padding-bottom: 16px; padding-top: 4px;">
                            <span style="width: 28px; height: 28px; background: #000000; color: #ffffff; border-radius: 50%; text-align: center; line-height: 28px; font-size: 14px; font-weight: 700; display: inline-block;">{i+1}</span>
                        </td>
                        <td style="vertical-align: top; padding-bottom: 16px; font-size: 16px; color: #1d1d1f; line-height: 1.6;">
                            {step}
                        </td>
                    </tr>''' for i, step in enumerate(steps)])}
                </table>
            </div>
            """
        
        button_html = ""
        if button_text and button_url:
            button_html = f'''<div style="text-align: center; margin: 30px 0;">
                <a href="{button_url}" style="display: inline-block; padding: 14px 28px; background-color: #000000; color: #ffffff; text-decoration: none; font-weight: 600; border-radius: 30px; font-size: 15px;">{button_text}</a>
            </div>'''
        
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="color-scheme" content="light only">
    <meta name="supported-color-schemes" content="light">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'SF Pro Display', 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #1d1d1f; background-color: #f5f5f7; margin: 0; padding: 0; -webkit-font-smoothing: antialiased;">
    <div style="width: 100%; background-color: #f5f5f7; padding: 40px 10px;">
        <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);">
            <!-- Header -->
            <div style="padding: 40px 30px 30px; text-align: center; background: #ffffff; border-bottom: 1px solid #f0f0f0;">
                <div style="font-size: 32px; font-weight: 700; letter-spacing: -0.03em; color: #000000; margin-bottom: 8px;">{business_name}</div>
                <div style="font-size: 14px; color: #86868b; font-weight: 500;">Powered by Ovela AI</div>
            </div>
            
            <!-- Body -->
            <div style="padding: 32px 30px;">
                <div style="display: inline-block; padding: 6px 12px; background: #000000; color: #ffffff; border-radius: 20px; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase; margin-bottom: 24px;">{badge}</div>
                
                <h1 style="font-size: 24px; font-weight: 700; color: #1d1d1f; margin-bottom: 20px; letter-spacing: -0.02em; line-height: 1.3;">{title}</h1>
                
                <p style="font-size: 16px; line-height: 1.6; color: #1d1d1f; margin-bottom: 20px;">{content}</p>
                
                {steps_html}
                
                {button_html}
                
                <p style="font-size: 16px; line-height: 1.6; color: #1d1d1f; margin-bottom: 20px;">{closing_text}</p>
                
                <div style="margin-top: 40px; padding-top: 30px; border-top: 1px solid #e5e5e7;">
                    <div style="font-size: 16px; color: #1d1d1f; font-weight: 600; margin-bottom: 4px;">— {business_name}</div>
                </div>
            </div>
            
            <!-- Footer -->
            <div style="padding: 30px; text-align: center; background: #f9f9fa; border-top: 1px solid #f0f0f0;">
                <p style="font-size: 12px; color: #86868b; line-height: 1.6; margin-bottom: 12px;">
                    Questions? Reply to this email or message us on WhatsApp.
                </p>
                <div>
                    <a href="https://ovela.dev" style="color: #0066cc; text-decoration: none; font-size: 12px; margin: 0 10px;">Powered by Ovela</a>
                </div>
            </div>
        </div>
    </div>
</body>
</html>'''

    async def send_email(self, to_email: str, subject: str, html_content: str, from_email: str = None):
        """Send an email via Resend API."""
        try:
            sender = from_email if from_email else self.default_from_email
            
            payload = {
                "from": sender,
                "to": [to_email],
                "subject": subject,
                "html": html_content
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.API_URL,
                    headers=self.headers,
                    json=payload
                )
                
                if response.status_code in [200, 201]:
                    logger.info(f"Email sent to {to_email}")
                    return True
                else:
                    logger.error(f"Resend Error: {response.text}")
                    return False
        except Exception as e:
            logger.error(f"Email Exception: {e}")
            return False

    async def send_booking_confirmation(self, name: str, email: str, date: str, time: str, service: str = "Beauty Consultation", business_name: str = "ibrow threading"):
        """Send a beautiful booking confirmation email."""
        subject = f"✨ Booking Confirmed - {service}"
        
        html = self._base_template(
            badge="Booking Confirmed",
            title=f"Hey {name}, you're all set!",
            content="Your appointment has been successfully booked. We're looking forward to seeing you!",
            business_name=business_name,
            steps=[
                f"<strong>Service:</strong> {service}",
                f"<strong>Date:</strong> {date}",
                f"<strong>Time:</strong> {time}"
            ],
            closing_text="Need to reschedule? Just message us on WhatsApp anytime."
        )
        
        # Use appointments alias for customer communications
        sender = f"{business_name} via Ovela <appointments@ovela.dev>"
        return await self.send_email(email, subject, html, from_email=sender)

    async def send_owner_notification(self, owner_email: str, customer_phone: str, business_name: str, source: str = "Missed Call"):
        """Send notification to business owner about new request."""
        subject = f"📞 New Booking Request - {source}"
        
        html = self._base_template(
            badge="New Request",
            title="You have a new booking request!",
            content=f"A customer is waiting for your approval. They reached out via {source}.",
            business_name="Ovela Dashboard",
            steps=[
                f"<strong>Customer:</strong> {customer_phone}",
                f"<strong>Source:</strong> {source}",
                f"<strong>Time:</strong> {datetime.now().strftime('%I:%M %p')}"
            ],
            button_text="Review in Dashboard",
            button_url="https://ovela.dev/dashboard/requests",
            closing_text="Approve this request to automatically notify the customer on WhatsApp."
        )
        
        # Use notifications alias for system alerts
        sender = "Ovela Notifications <notifications@ovela.dev>"
        return await self.send_email(owner_email, subject, html, from_email=sender)

    async def send_reschedule_confirmation(self, email: str = None, booking_id: str = None, new_time: str = None, name: str = "there", location: str = None):
        """Send reschedule confirmation email."""
        if not email:
            logger.warning("No email provided for reschedule confirmation")
            return False
        
        # Format the new time nicely
        formatted_time = new_time
        try:
            if new_time:
                dt = datetime.fromisoformat(new_time.replace("Z", "+00:00"))
                dt_melb = dt.astimezone(MELBOURNE_TZ)
                formatted_time = dt_melb.strftime("%A, %d %B %Y at %I:%M %p")
        except:
            pass
        
        # Build steps - only include location if provided
        steps = [f"<strong>New Time:</strong> {formatted_time}"]
        if location:
            steps.append(f"<strong>Location:</strong> {location}")
            
        subject = "📅 Appointment Rescheduled"
        html = self._base_template(
            badge="Rescheduled",
            title=f"Hey {name}, your appointment has been moved.",
            content="No worries — we've updated your booking to the new time below.",
            steps=steps,
            closing_text="Need to make more changes? Just message us on WhatsApp — happy to help!"
        )
        # Use appointments alias for customer communications
        sender = "Ovela Appointments <appointments@ovela.dev>"
        return await self.send_email(email, subject, html, from_email=sender)

    async def send_cancellation_confirmation(self, email: str = None, booking_id: str = None, name: str = "there", business_name: str = "Your Business"):
        """Send cancellation confirmation email to customer."""
        if not email:
            logger.warning("No email provided for cancellation confirmation")
            return False
            
        subject = "Appointment Cancelled"
        html = self._base_template(
            badge="Cancelled",
            title=f"Hey {name}, your appointment has been cancelled.",
            content="We've cancelled your booking as requested. We'd love to see you again soon!",
            business_name=business_name,
            steps=[],
            button_text="Book Again",
            button_url="https://wa.me/your-whatsapp-number",
            closing_text="Ready to book again? Just message us on WhatsApp anytime — we're here for you."
        )
        # Use business name for white-label customer experience
        sender = f"{business_name} via Ovela <appointments@ovela.dev>"
        return await self.send_email(email, subject, html, from_email=sender)

    async def send_owner_cancellation_notification(self, owner_email: str, customer_name: str, customer_phone: str, service_name: str, booking_date: str, booking_time: str):
        """Notify business owner when a customer cancels their appointment."""
        if not owner_email:
            logger.warning("No owner email provided for cancellation notification")
            return False
        
        # Format date nicely
        formatted_date = booking_date
        try:
            from datetime import datetime
            dt = datetime.strptime(booking_date, "%Y-%m-%d")
            formatted_date = dt.strftime("%A, %d %B %Y")
        except:
            pass
            
        subject = f"❌ Appointment Cancelled - {customer_name}"
        html = self._base_template(
            badge="Cancellation Notice",
            title=f"{customer_name} has cancelled their appointment.",
            content="A customer has cancelled their booking. Here are the details:",
            business_name="Ovela Dashboard",  # Platform notification, not white-label
            steps=[
                f"<strong>Customer:</strong> {customer_name}",
                f"<strong>Phone:</strong> {customer_phone}",
                f"<strong>Service:</strong> {service_name}",
                f"<strong>Original Time:</strong> {formatted_date} at {booking_time}"
            ],
            button_text="View Dashboard",
            button_url="https://ovela.dev/dashboard/bookings",
            closing_text="This time slot is now available for other customers."
        )
        # Use notifications alias for owner/platform communications
        sender = "Ovela Notifications <notifications@ovela.dev>"
        return await self.send_email(owner_email, subject, html, from_email=sender)

    async def send_human_callback_request(self, owner_email: str, customer_name: str, customer_phone: str, reason: str, urgency: str = "medium", business_phone: str = None):
        """Notify business owner that a customer wants to speak to a human."""
        if not owner_email:
            logger.warning("No owner email provided for callback request")
            return False
        
        urgency_labels = {"low": "🟢 Low", "medium": "🟡 Medium", "high": "🔴 High"}
        urgency_display = urgency_labels.get(urgency, "🟡 Medium")
        
        subject = f"📞 Customer Callback Request - {customer_name}"
        if urgency == "high":
            subject = f"🔴 URGENT: Customer Callback Request - {customer_name}"
        
        # Build steps
        steps = [
            f"<strong>Customer:</strong> {customer_name}",
            f"<strong>Phone:</strong> <a href='tel:{customer_phone}' style='color: #0066cc;'>{customer_phone}</a>",
            f"<strong>Reason:</strong> {reason}",
            f"<strong>Urgency:</strong> {urgency_display}",
            f"<strong>Requested:</strong> {datetime.now(MELBOURNE_TZ).strftime('%I:%M %p, %d %B')}"
        ]
        
        html = self._base_template(
            badge="Callback Requested",
            title=f"{customer_name} wants to speak with you",
            content="A customer has requested a callback. They've asked to speak with someone from your team directly. Please call them back within 30 minutes.",
            business_name="Ovela Dashboard",
            steps=steps,
            button_text=f"Call {customer_name} Now",
            button_url=f"tel:{customer_phone}",
            closing_text="Tap the button above to call the customer directly from your phone."
        )
        
        sender = "Ovela Notifications <notifications@ovela.dev>"
        return await self.send_email(owner_email, subject, html, from_email=sender)


email_service = EmailService()
