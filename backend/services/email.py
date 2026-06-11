
"""
Email Service via Zoho SMTP
Handles sending transactional emails for bookings with Ovela-branded design.
"""
import aiosmtplib
from email.message import EmailMessage
from core.config import settings
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, List, Union

logger = logging.getLogger(__name__)
MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")


class EmailService:
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.default_from_email = settings.MAIL_FROM

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
                    Questions? Reply to this email or call us.
                </p>
                <div>
                    <a href="https://ovela.dev" style="color: #0066cc; text-decoration: none; font-size: 12px; margin: 0 10px;">Powered by Ovela</a>
                </div>
            </div>
        </div>
    </div>
</body>
</html>'''

    def _client_template(self, tenant_id: str, context: dict) -> str:
        """
        Load custom client HTML template and inject context variables.
        Fallback to a generic template if tenant specific file doesn't exist.
        """
        import os
        template_dir = os.path.join(os.path.dirname(__file__), "templates")
        template_path = os.path.join(template_dir, f"{tenant_id}.html")
        
        # Determine payment section vs simple confirmed text
        payment_section = ""
        payment_link = context.get("payment_link")
        amount = context.get("amount", 0)
        
        if payment_link:
            is_setup = (amount == 0)
            btn_text = "Save Card to Secure Booking" if is_setup else f"Complete Payment — ${amount} AUD"
            note_text = "No charge is made today. Your card is saved securely to hold the reservation." if is_setup else "Your payment is processed securely via Stripe. Standard cancellation policies apply."
            
            payment_section = f'''
            <div style="margin: 28px 0; padding: 24px; background: #f8f8f8; border: 1px solid #e0e0e0; border-radius: 6px;">
                <div style="font-size: 11px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; color: #888888; margin-bottom: 12px;">Payment Required</div>
                <p style="font-size: 14px; color: #555555; margin: 0 0 20px 0; line-height: 1.6;">{note_text}</p>
                <a href="{payment_link}" style="display: inline-block; padding: 13px 28px; background-color: #111111; color: #ffffff; text-decoration: none; font-weight: 600; border-radius: 5px; font-size: 14px; letter-spacing: 0.2px;">{btn_text}</a>
            </div>
            '''
        
        # Build final context payload
        ctx = {
            "badge": "Action Required" if payment_link else "Booking Confirmed",
            "guest_name": context.get("guest_name", "Guest"),
            "email_content": context.get("content", "Your booking has been approved. Please review the details below."),
            "booking_ref": context.get("booking_ref", "N/A"),
            "room_type": context.get("room_type", "").title() + " Room",
            "check_in": context.get("check_in", ""),
            "check_out": context.get("check_out", ""),
            "payment_section": payment_section
        }
        
        # Load custom template if exists
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                html = f.read()
                # Inject variables defined as {{var_name}}
                for key, val in ctx.items():
                    html = html.replace(f"{{{{{key}}}}}", str(val))
                return html
        
        # M2: Use full motel business name from data config — prevents "Motel" branding leak
        from services.knowledge_base.coalcreek import COALCREEK_DATA as _CC_DATA
        _default_biz_name = _CC_DATA["info"]["name"]
        return self._base_template(
            badge="Booking Confirmed" if not payment_link else "Action Required",
            title=f"Hi {ctx['guest_name']}",
            content=ctx['email_content'],
            business_name=context.get("business_name", _default_biz_name),
            steps=[
                f"<strong>Booking Ref:</strong> {ctx['booking_ref']}",
                f"<strong>Room:</strong> {ctx['room_type']}",
                f"<strong>Check-in:</strong> {ctx['check_in']}",
                f"<strong>Check-out:</strong> {ctx['check_out']}"
            ],
            button_text="Secure Booking" if payment_link else None,
            button_url=payment_link,
            closing_text="Have questions? Reply to this email."
        )

    async def send_email(self, to_email: Union[str, List[str]], subject: str, html_content: str, from_email: str = None):
        """
        Send an email via appropriate SMTP provider (Zoho for Ovela, Gmail for Coal Creek).
        to_email: can be a single email string or a list of email strings.
        """
        try:
            sender = from_email if from_email else self.default_from_email

            # Determine which SMTP provider to use based on sender
            if "officialcoalcreek@gmail.com" in sender or "coalcreekmotel.com.au" in sender:
                # Use Gmail SMTP for Coal Creek Motel
                smtp_host = settings.GMAIL_SMTP_HOST
                smtp_port = settings.GMAIL_SMTP_PORT
                smtp_user = settings.GMAIL_SMTP_USER
                smtp_password = settings.COALCREEK_APP_PASSWORD
                provider_name = "Gmail"
            else:
                # Use Zoho SMTP for Ovela
                smtp_host = self.smtp_host
                smtp_port = self.smtp_port
                smtp_user = self.smtp_user
                smtp_password = self.smtp_password
                provider_name = "Zoho"

            # Ensure we have a list for the 'to' field
            if isinstance(to_email, str):
                recipients = [email.strip() for email in to_email.split(",") if email.strip()]
            else:
                recipients = to_email

            if not recipients:
                logger.warning("No recipients provided for email")
                return False

            message = EmailMessage()
            message["From"] = sender
            message["To"] = ", ".join(recipients)
            message["Subject"] = subject
            message.set_content(html_content, subtype="html")

            # Add anti-spam headers
            message["Reply-To"] = sender
            message["List-Unsubscribe"] = f"<mailto:{sender}>"

            # SMTP Settings
            # Port 465: SSL/TLS from start (use_tls=True)
            # Port 587: STARTTLS (start_tls=True, use_tls=False)
            if smtp_port == 465:
                async with aiosmtplib.SMTP(
                    hostname=smtp_host,
                    port=smtp_port,
                    use_tls=True
                ) as smtp:
                    await smtp.login(smtp_user, smtp_password)
                    await smtp.send_message(message)
            else:  # Port 587 (STARTTLS)
                async with aiosmtplib.SMTP(
                    hostname=smtp_host,
                    port=smtp_port,
                    start_tls=True
                ) as smtp:
                    await smtp.login(smtp_user, smtp_password)
                    await smtp.send_message(message)

            logger.info(f"Email sent successfully to {recipients} via {provider_name} SMTP")
            return True

        except Exception as e:
            logger.error(f"SMTP Error: {e}")
            return False

    async def send_booking_confirmation(self, name: str, email: str, date: str, time: str, service: str = "Beauty Consultation", business_name: str = "ibrow threading"):
        """Send a beautiful booking confirmation email."""
        subject = f"Booking Confirmed — {service}"
        
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
            closing_text="Need to reschedule? Just reply to this email or call us anytime."
        )
        
        # Use bookings alias for customer communications
        sender = f"{business_name} via Ovela <{settings.MAIL_BOOKINGS.split('<')[-1][:-1]}>"
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
            closing_text="Approve this request to confirm."
        )
        
        # Use notifications alias for system alerts
        sender = settings.MAIL_NOTIFICATIONS
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
            closing_text="Need to make more changes? Just reply to this email or call us — happy to help!"
        )
        # Use bookings alias for customer communications
        sender = settings.MAIL_BOOKINGS
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
            button_url="tel:your-phone-number",
            closing_text="Ready to book again? Just call us anytime — we're here for you."
        )
        # Use business name for white-label customer experience
        sender = f"{business_name} via Ovela <{settings.MAIL_BOOKINGS.split('<')[-1][:-1]}>"
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
        sender = settings.MAIL_NOTIFICATIONS
        return await self.send_email(owner_email, subject, html, from_email=sender)

    async def send_human_callback_request(
        self, 
        owner_email: str, 
        customer_name: str, 
        customer_phone: str, 
        reason: str, 
        urgency: str = "medium", 
        business_phone: str = None,
        notification_id: str = None  # NEW: for magic links
    ):
        """Notify business owner that a customer wants to speak to a human."""
        if not owner_email:
            logger.warning("No owner email provided for callback request")
            return False
        
        urgency_labels = {"low": "🟢 Low", "medium": "🟡 Medium", "high": "🔴 High"}
        urgency_display = urgency_labels.get(urgency, "🟡 Medium")
        
        subject = f"📞 Customer Callback Request - {customer_name}"
        if urgency == "high":
            subject = f"🔴 URGENT: Customer Callback Request - {customer_name}"
        
        # Build steps with copy-friendly formatting
        steps = [
            f"<strong>Customer:</strong> {customer_name}",
            f"<strong>Phone:</strong> <a href='tel:{customer_phone}' style='color: #0066cc;'>{customer_phone}</a>",
            f"<strong>Reason:</strong> {reason}",
            f"<strong>Urgency:</strong> {urgency_display}",
            f"<strong>Requested:</strong> {datetime.now(MELBOURNE_TZ).strftime('%I:%M %p, %d %B')}"
        ]
        
        # Generate magic link action buttons if we have a notification ID
        action_buttons_html = ""
        if notification_id:
            from services.magic_links import generate_action_url
            
            complete_url = generate_action_url(notification_id, "complete")
            dismiss_url = generate_action_url(notification_id, "dismiss")
            dashboard_url = "https://ovela.dev/motel/notifications"
            
            action_buttons_html = f'''
            <div style="margin: 32px 0; padding: 24px; background: #f9f9fa; border-radius: 12px; border: 1px solid #e5e5e7;">
                <div style="font-size: 14px; font-weight: 700; color: #1d1d1f; margin-bottom: 16px; text-transform: uppercase; letter-spacing: 0.5px;">Quick Actions</div>
                
                <div style="margin-bottom: 12px;">
                    <a href="{complete_url}" style="display: inline-block; padding: 12px 24px; background: #22c55e; color: white; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 14px;">✅ Called Back - Mark Complete</a>
                </div>
                
                <div style="margin-bottom: 12px;">
                    <a href="{dismiss_url}" style="display: inline-block; padding: 12px 24px; background: #6b7280; color: white; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 14px;">❌ Dismiss</a>
                </div>
                
                <div>
                    <a href="{dashboard_url}" style="display: inline-block; padding: 12px 24px; background: #3b82f6; color: white; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 14px;">📝 Open Dashboard</a>
                </div>
                
                <p style="margin-top: 16px; font-size: 12px; color: #86868b;">Links expire in 48 hours. Use dashboard for changes after that.</p>
            </div>
            
            <div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 12px; margin-top: 16px;">
                <span style="font-size: 14px; color: #856404;">⚠️ <strong>Reminder:</strong> Don't forget to update your CRM too!</span>
            </div>
            '''
        
        # Build custom HTML with action buttons
        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; color: #1d1d1f; background-color: #f5f5f7; margin: 0; padding: 0;">
    <div style="width: 100%; background-color: #f5f5f7; padding: 40px 10px;">
        <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);">
            <div style="padding: 40px 30px 30px; text-align: center; background: #ffffff; border-bottom: 1px solid #f0f0f0;">
                <div style="font-size: 32px; font-weight: 700; color: #2C5F2D;">Coal Creek Motel</div>
                <div style="font-size: 14px; color: #86868b; font-weight: 500;">Staff Notification</div>
            </div>
            
            <div style="padding: 32px 30px;">
                <div style="display: inline-block; padding: 6px 12px; background: #2C5F2D; color: #ffffff; border-radius: 20px; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase; margin-bottom: 24px;">Callback Requested</div>
                
                <h1 style="font-size: 24px; font-weight: 700; color: #1d1d1f; margin-bottom: 20px;">{customer_name} wants to speak with you</h1>
                
                <p style="font-size: 16px; color: #1d1d1f; margin-bottom: 20px;">A guest has requested a callback. Please call them back within 30 minutes.</p>
                
                <div style="background: #f9f9fa; border: 1px solid #e5e5e7; border-radius: 12px; padding: 24px; margin: 24px 0;">
                    <table style="width: 100%;" border="0" cellpadding="0" cellspacing="0">
                        {"".join([f'<tr><td style="padding: 8px 0; font-size: 15px; color: #1d1d1f;">{step}</td></tr>' for step in steps])}
                    </table>
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="tel:{customer_phone}" style="display: inline-block; padding: 14px 28px; background-color: #2C5F2D; color: #ffffff; text-decoration: none; font-weight: 600; border-radius: 30px; font-size: 15px;">📞 Call {customer_name} Now</a>
                </div>
                
                {action_buttons_html}
            </div>
            
            <div style="padding: 30px; text-align: center; background: #f9f9fa; border-top: 1px solid #f0f0f0;">
                <p style="font-size: 12px; color: #86868b;">Powered by Ovela AI</p>
            </div>
        </div>
    </div>
</body>
</html>'''
        
        sender = settings.MAIL_BOOKINGS
        return await self.send_email(owner_email, subject, html, from_email=sender)


    async def send_booking_approval_request(
        self,
        owner_email: str,
        guest_name: str,
        guest_phone: str,
        check_in: str,
        check_out: str,
        room_type: str,
        total_amount: float,
        booking_reference: str,
        num_nights: int = 1,
        notification_id: str = None,
        guest_email: str = None,
        business_name: str = "Coal Creek Motel"
    ):
        """Notify staff about a new booking that needs approval with magic links."""
        if not owner_email:
            logger.warning("No owner email provided for booking approval")
            return False
        
        subject = f"New Booking Request: {guest_name} — {room_type.title()} Room"
        
        # Format dates nicely
        try:
            from datetime import datetime
            ci = datetime.strptime(check_in, "%Y-%m-%d")
            co = datetime.strptime(check_out, "%Y-%m-%d")
            check_in_fmt = ci.strftime("%a, %d %b")
            check_out_fmt = co.strftime("%a, %d %b")
        except:
            check_in_fmt = check_in
            check_out_fmt = check_out
        
        # Generate magic link action buttons
        action_buttons_html = ""
        if notification_id:
            from services.magic_links import generate_action_url
            
            approve_url = generate_action_url(notification_id, "approve")
            reject_url = generate_action_url(notification_id, "reject")
            dashboard_url = "https://ovela.dev/motel/notifications"
            
            action_buttons_html = f'''
            <div style="margin: 28px 0; padding: 24px; background: #f8f8f8; border: 1px solid #e0e0e0; border-radius: 6px;">
                <div style="font-size: 11px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; color: #888888; margin-bottom: 16px;">Actions</div>
                
                <div style="margin-bottom: 10px;">
                    <a href="{approve_url}" style="display: inline-block; padding: 11px 22px; background: #1a7f4b; color: white; text-decoration: none; border-radius: 5px; font-weight: 600; font-size: 13px; letter-spacing: 0.2px;">Approve Booking</a>
                </div>
                
                <div style="margin-bottom: 10px;">
                    <a href="{reject_url}" style="display: inline-block; padding: 11px 22px; background: #c0392b; color: white; text-decoration: none; border-radius: 5px; font-weight: 600; font-size: 13px; letter-spacing: 0.2px;">Decline &amp; Contact Guest</a>
                </div>
                
                <div>
                    <a href="{dashboard_url}" style="display: inline-block; padding: 11px 22px; background: #ffffff; color: #333333; text-decoration: none; border-radius: 5px; font-weight: 600; font-size: 13px; border: 1px solid #cccccc;">Open Dashboard</a>
                </div>
                
                <p style="margin: 16px 0 0 0; font-size: 12px; color: #aaaaaa;">Each link is single-use. Approve sends the guest a confirmation email. Decline cancels the hold and shows you the guest contact details. Links expire in 48 hours.</p>
            </div>
            '''
        
        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #1a1a1a; background-color: #f0f0f0; margin: 0; padding: 0; -webkit-font-smoothing: antialiased;">
    <div style="width: 100%; background-color: #f0f0f0; padding: 40px 10px;">
        <div style="max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.08);">

            <!-- Header -->
            <div style="padding: 32px 40px 24px; border-bottom: 1px solid #e8e8e8;">
                <div style="font-size: 11px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase; color: #888888; margin-bottom: 8px;">Coal Creek Motel &mdash; New Booking</div>
                <div style="font-size: 20px; font-weight: 700; color: #111111; letter-spacing: -0.3px;">Booking Request: Approval Required</div>
            </div>

            <!-- Body -->
            <div style="padding: 28px 40px;">

                <p style="font-size: 15px; line-height: 1.65; color: #555555; margin: 0 0 24px 0;">A new booking request has been received via Ovela AI. Please review the details below and take action.</p>

                <!-- Booking Details -->
                <div style="border: 1px solid #e4e4e4; border-left: 3px solid #1a1a1a; border-radius: 4px; padding: 20px 24px; margin: 0 0 24px 0; background: #fafafa;">
                    <div style="font-size: 11px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; color: #888888; margin-bottom: 8px;">Booking Reference</div>
                    <div style="font-size: 22px; font-weight: 700; color: #111111; margin-bottom: 16px; padding-bottom: 16px; border-bottom: 1px solid #eeeeee;">{booking_reference}</div>
                    <table style="width: 100%; border-collapse: collapse;" border="0" cellpadding="0" cellspacing="0">
                        <tr>
                            <td style="padding: 7px 0; font-size: 13px; color: #888888; width: 100px; vertical-align: top;">Guest</td>
                            <td style="padding: 7px 0; font-size: 13px; color: #333333; font-weight: 600;">{guest_name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 7px 0; font-size: 13px; color: #888888; border-top: 1px solid #eeeeee; vertical-align: top;">Phone</td>
                            <td style="padding: 7px 0; font-size: 13px; color: #333333; border-top: 1px solid #eeeeee;"><a href="tel:{guest_phone}" style="color: #1a1a1a; text-decoration: underline;">{guest_phone}</a></td>
                        </tr>
                        {f'<tr><td style="padding: 7px 0; font-size: 13px; color: #888888; border-top: 1px solid #eeeeee; vertical-align: top;">Email</td><td style="padding: 7px 0; font-size: 13px; color: #333333; border-top: 1px solid #eeeeee;"><a href="mailto:{guest_email}" style="color: #1a1a1a; text-decoration: underline;">{guest_email}</a></td></tr>' if guest_email else ''}
                        <tr>
                            <td style="padding: 7px 0; font-size: 13px; color: #888888; border-top: 1px solid #eeeeee; vertical-align: top;">Room</td>
                            <td style="padding: 7px 0; font-size: 13px; color: #333333; border-top: 1px solid #eeeeee;">{room_type.title()} Room</td>
                        </tr>
                        <tr>
                            <td style="padding: 7px 0; font-size: 13px; color: #888888; border-top: 1px solid #eeeeee; vertical-align: top;">Check-in</td>
                            <td style="padding: 7px 0; font-size: 13px; color: #333333; border-top: 1px solid #eeeeee;">{check_in_fmt}</td>
                        </tr>
                        <tr>
                            <td style="padding: 7px 0; font-size: 13px; color: #888888; border-top: 1px solid #eeeeee; vertical-align: top;">Check-out</td>
                            <td style="padding: 7px 0; font-size: 13px; color: #333333; border-top: 1px solid #eeeeee;">{check_out_fmt}</td>
                        </tr>
                        <tr>
                            <td style="padding: 7px 0; font-size: 13px; color: #888888; border-top: 1px solid #eeeeee; vertical-align: top;">Nights</td>
                            <td style="padding: 7px 0; font-size: 13px; color: #333333; border-top: 1px solid #eeeeee;">{num_nights}</td>
                        </tr>
                        <tr>
                            <td style="padding: 12px 0 8px; font-size: 13px; color: #888888; border-top: 1px solid #dddddd; vertical-align: top; font-weight: 600;">Total</td>
                            <td style="padding: 12px 0 8px; font-size: 18px; color: #111111; border-top: 1px solid #dddddd; font-weight: 700;">${total_amount} AUD</td>
                        </tr>
                    </table>
                </div>

                <p style="font-size: 13px; color: #888888; margin: 0 0 16px 0;">To call the guest directly: <a href="tel:{guest_phone}" style="color: #1a1a1a; font-weight: 600;">{guest_phone}</a></p>

                {action_buttons_html}
            </div>

            <!-- Footer -->
            <div style="padding: 20px 40px; background: #f7f7f7; border-top: 1px solid #e8e8e8;">
                <p style="margin: 0; font-size: 12px; color: #aaaaaa; line-height: 1.6; text-align: center;">Ovela AI &bull; Booking Management System<br>This is a system notification. Please do not reply to this email.</p>
            </div>
        </div>
    </div>
</body>
</html>'''
        
        sender = settings.MAIL_BOOKINGS
        return await self.send_email(owner_email, subject, html, from_email=sender)


    async def send_demo_alert(self, lead_details: dict):
        """Notify team about a new demo request."""
        name = lead_details.get("name", "Unknown")
        business = lead_details.get("business_name", "Unknown")
        phone = lead_details.get("phone", "Unknown")
        created_at = lead_details.get("created_at", datetime.now(MELBOURNE_TZ).isoformat())

        subject = f"🚀 New Demo Request: {business}"
        
        steps = [
            f"<strong>Name:</strong> {name}",
            f"<strong>Business:</strong> {business}",
            f"<strong>Phone:</strong> {phone}",
            f"<strong>Time:</strong> {created_at}"
        ]

        html = self._base_template(
            badge="New Demo Lead",
            title=f"New Demo: {business}",
            content=f"A new user has requested a demo. Here are their details:",
            business_name="Ovela Admin",
            steps=steps,
            button_text="View conversations",
            button_url="https://ovela.dev/login",
            closing_text="Good luck!"
        )

        # Send to internal notification emails
        # Load from whitelist/settings
        recipients_str = settings.DEMO_ALERT_RECIPIENTS
        recipients = [email.strip() for email in recipients_str.split(",") if email.strip()]
        
        # Fallback if empty
        if not recipients:
            recipients = [settings.MAIL_NOTIFICATIONS.split('<')[-1][:-1]]
            
        sender = settings.MAIL_NOTIFICATIONS
        return await self.send_email(recipients, subject, html, from_email=sender)

    async def send_demo_approval_request(self, lead_details: dict):
        """
        Send demo approval request email to team with Approve/Reject magic links.
        """
        name = lead_details.get("name", "Unknown")
        business = lead_details.get("business_name", "Unknown")
        phone = lead_details.get("phone", "Unknown")
        created_at = lead_details.get("created_at", datetime.now(MELBOURNE_TZ).isoformat())
        approve_url = lead_details.get("approve_url", "")
        reject_url = lead_details.get("reject_url", "")

        subject = f"🚀 Demo Request: {name} - {business}"
        
        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; color: #1d1d1f; background-color: #f5f5f7; margin: 0; padding: 0;">
    <div style="width: 100%; background-color: #f5f5f7; padding: 40px 10px;">
        <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);">
            <div style="padding: 40px 30px 30px; text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                <div style="font-size: 32px; font-weight: 700; color: #ffffff;">Ovela</div>
                <div style="font-size: 14px; color: #ffffff99; font-weight: 500;">Demo Request Approval</div>
            </div>
            
            <div style="padding: 32px 30px;">
                <div style="display: inline-block; padding: 6px 12px; background: #fbbf24; color: #1d1d1f; border-radius: 20px; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase; margin-bottom: 24px;">Awaiting Your Approval</div>
                
                <h1 style="font-size: 24px; font-weight: 700; color: #1d1d1f; margin-bottom: 20px;">New demo request from {name}</h1>
                
                <div style="background: #f9f9fa; border: 1px solid #e5e5e7; border-radius: 12px; padding: 24px; margin: 24px 0;">
                    <table style="width: 100%;" border="0" cellpadding="0" cellspacing="0">
                        <tr><td style="padding: 8px 0; font-size: 15px; color: #1d1d1f;"><strong>Name:</strong> {name}</td></tr>
                        <tr><td style="padding: 8px 0; font-size: 15px; color: #1d1d1f;"><strong>Business:</strong> {business}</td></tr>
                        <tr><td style="padding: 8px 0; font-size: 15px; color: #1d1d1f;"><strong>Phone:</strong> <a href="tel:{phone}" style="color: #0066cc;">{phone}</a></td></tr>
                        <tr><td style="padding: 8px 0; font-size: 15px; color: #86868b;"><strong>Requested:</strong> {created_at}</td></tr>
                    </table>
                </div>
                
                <div style="margin: 32px 0; text-align: center;">
                    <p style="margin-bottom: 20px; color: #86868b; font-size: 14px;">Approve to trigger the demo call, or reject if not qualified.</p>
                    
                    <div style="margin-bottom: 16px;">
                        <a href="{approve_url}" style="display: inline-block; padding: 14px 32px; background: #22c55e; color: white; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 16px; margin-right: 12px;">✅ Approve - Call Now</a>
                    </div>
                    
                    <div>
                        <a href="{reject_url}" style="display: inline-block; padding: 14px 32px; background: #ef4444; color: white; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 14px;">❌ Reject</a>
                    </div>
                </div>
                
                <div style="background: #e8f4fd; border: 1px solid #0066cc33; border-radius: 8px; padding: 16px; margin-top: 24px;">
                    <p style="margin: 0; font-size: 13px; color: #1d4ed8;">
                        <strong>ℹ️ How it works:</strong><br>
                        • Approve = AI calls their phone immediately<br>
                        • Reject = Lead marked inactive (no call)<br>
                        • Links expire in 24 hours
                    </p>
                </div>
            </div>
            
            <div style="padding: 30px; text-align: center; background: #f9f9fa; border-top: 1px solid #f0f0f0;">
                <p style="font-size: 12px; color: #86868b;">Powered by Ovela AI</p>
            </div>
        </div>
    </div>
</body>
</html>'''

        # Send to internal notification emails
        recipients_str = settings.DEMO_ALERT_RECIPIENTS
        recipients = [email.strip() for email in recipients_str.split(",") if email.strip()]
        
        if not recipients:
            recipients = [settings.MAIL_NOTIFICATIONS.split('<')[-1][:-1]]
            
        sender = settings.MAIL_NOTIFICATIONS
        return await self.send_email(recipients, subject, html, from_email=sender)


    async def send_guest_booking_confirmation(
        self,
        guest_email: str,
        guest_name: str,
        booking_reference: str,
        room_type: str,
        check_in: str,
        check_out: str,
        num_nights: int,
        total_amount: float,
        business_name: str = "Coal Creek Motel",  # M2: was "Motel" — now correct full brand name
        business_phone: str = "",
        business_location: str = "",
        tenant_id: str = "coalcreek"
    ):
        """Send booking confirmation to guest using CLIENT'S custom template."""
        if not guest_email:
            logger.info("No guest email - skipping confirmation")
            return False
        
        subject = f"Booking Confirmed — {business_name} ({booking_reference})"
        
        # Format dates nicely
        try:
            ci = datetime.strptime(check_in, "%Y-%m-%d")
            co = datetime.strptime(check_out, "%Y-%m-%d")
            check_in_fmt = ci.strftime("%A, %d %B %Y")
            check_out_fmt = co.strftime("%A, %d %B %Y")
        except:
            check_in_fmt = check_in
            check_out_fmt = check_out
        
        html = self._client_template(tenant_id, {
            "guest_name": guest_name,
            "content": f"Thank you for choosing {business_name}. Your booking has been fully confirmed and no further action is required.",
            "booking_ref": booking_reference,
            "room_type": room_type,
            "check_in": check_in_fmt,
            "check_out": check_out_fmt,
            "business_name": business_name
        })
        
        sender = settings.MAIL_BOOKINGS
        success = await self.send_email(guest_email, subject, html, from_email=sender)
        
        if success:
            logger.info(f"Guest confirmation sent to {guest_email} ({booking_reference})")
        
        return success
    
    async def send_staff_payment_notification(
        self,
        staff_email: str,
        booking_reference: str,
        customer_name: str,
        customer_email: str,
        room_type: str,
        check_in: str,
        check_out: str,
        num_nights: int,
        amount_paid: float,
        mode: str = "payment"
    ):
        """
        Notify staff when payment is received (industry best practice).
        Staff can then add the confirmed booking to Update247 CRM.
        """
        if not staff_email:
            logger.info("No staff email - skipping payment notification")
            return False
        
        if mode == "setup":
            subject = f"Card Secured — Booking {booking_reference}"
            title = "Card Secured"
            desc = f"The guest has securely saved their card details via Stripe. Booking {booking_reference} is confirmed and ready to be entered into your property management system."
        else:
            subject = f"Payment Received — Booking {booking_reference}"
            title = "Payment Confirmed"
            desc = f"Payment for booking {booking_reference} has been received in full. Please add this reservation to your property management system at your earliest convenience."
        
        # Format dates nicely
        try:
            ci = datetime.strptime(check_in, "%Y-%m-%d")
            co = datetime.strptime(check_out, "%Y-%m-%d")
            check_in_fmt = ci.strftime("%A, %d %B %Y")
            check_out_fmt = co.strftime("%A, %d %B %Y")
        except:
            check_in_fmt = check_in
            check_out_fmt = check_out
        
        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #1a1a1a; background-color: #f0f0f0; margin: 0; padding: 0; -webkit-font-smoothing: antialiased;">
    <div style="width: 100%; background-color: #f0f0f0; padding: 40px 10px;">
        <div style="max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.08);">

            <!-- Header -->
            <div style="padding: 32px 40px 24px; border-bottom: 1px solid #e8e8e8;">
                <div style="font-size: 11px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase; color: #888888; margin-bottom: 8px;">Coal Creek Motel — Staff Notification</div>
                <div style="font-size: 20px; font-weight: 700; color: #111111; letter-spacing: -0.3px;">{title}</div>
            </div>

            <!-- Body -->
            <div style="padding: 28px 40px;">

                <p style="font-size: 15px; line-height: 1.65; color: #555555; margin: 0 0 24px 0;">{desc}</p>

                <!-- Booking Details -->
                <div style="border: 1px solid #e4e4e4; border-left: 3px solid #1a1a1a; border-radius: 4px; padding: 20px 24px; margin: 0 0 24px 0; background: #fafafa;">
                    <div style="font-size: 11px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; color: #888888; margin-bottom: 8px;">Booking Reference</div>
                    <div style="font-size: 22px; font-weight: 700; color: #111111; margin-bottom: 16px; padding-bottom: 16px; border-bottom: 1px solid #eeeeee;">{booking_reference}</div>
                    <table style="width: 100%; border-collapse: collapse;" border="0" cellpadding="0" cellspacing="0">
                        <tr>
                            <td style="padding: 7px 0; font-size: 13px; color: #888888; width: 100px; vertical-align: top;">Guest</td>
                            <td style="padding: 7px 0; font-size: 13px; color: #333333; font-weight: 600;">{customer_name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 7px 0; font-size: 13px; color: #888888; border-top: 1px solid #eeeeee; vertical-align: top;">Email</td>
                            <td style="padding: 7px 0; font-size: 13px; color: #333333; border-top: 1px solid #eeeeee;">{customer_email}</td>
                        </tr>
                        <tr>
                            <td style="padding: 7px 0; font-size: 13px; color: #888888; border-top: 1px solid #eeeeee; vertical-align: top;">Room</td>
                            <td style="padding: 7px 0; font-size: 13px; color: #333333; border-top: 1px solid #eeeeee;">{room_type.title()} Room</td>
                        </tr>
                        <tr>
                            <td style="padding: 7px 0; font-size: 13px; color: #888888; border-top: 1px solid #eeeeee; vertical-align: top;">Check-in</td>
                            <td style="padding: 7px 0; font-size: 13px; color: #333333; border-top: 1px solid #eeeeee;">{check_in_fmt}</td>
                        </tr>
                        <tr>
                            <td style="padding: 7px 0; font-size: 13px; color: #888888; border-top: 1px solid #eeeeee; vertical-align: top;">Check-out</td>
                            <td style="padding: 7px 0; font-size: 13px; color: #333333; border-top: 1px solid #eeeeee;">{check_out_fmt}</td>
                        </tr>
                        <tr>
                            <td style="padding: 7px 0; font-size: 13px; color: #888888; border-top: 1px solid #eeeeee; vertical-align: top;">Nights</td>
                            <td style="padding: 7px 0; font-size: 13px; color: #333333; border-top: 1px solid #eeeeee;">{num_nights}</td>
                        </tr>
                        <tr>
                            <td style="padding: 12px 0 8px; font-size: 13px; color: #888888; border-top: 1px solid #dddddd; vertical-align: top; font-weight: 600;">Amount</td>
                            <td style="padding: 12px 0 8px; font-size: 18px; color: #1a7f4b; border-top: 1px solid #dddddd; font-weight: 700;">${amount_paid} AUD</td>
                        </tr>
                    </table>
                </div>

                <div style="padding: 16px 20px; background: #f8f8f8; border: 1px solid #e0e0e0; border-radius: 4px; margin-bottom: 24px;">
                    <p style="margin: 0; font-size: 13px; color: #555555; line-height: 1.6;">Please add this booking to your property management system. Guest confirmation has been sent automatically.</p>
                </div>

                <div style="text-align: center;">
                    <a href="https://ovela.dev/dashboard/reservations" style="display: inline-block; padding: 12px 24px; background-color: #111111; color: #ffffff; text-decoration: none; font-weight: 600; border-radius: 5px; font-size: 13px;">View in Dashboard</a>
                </div>
            </div>

            <!-- Footer -->
            <div style="padding: 20px 40px; background: #f7f7f7; border-top: 1px solid #e8e8e8;">
                <p style="margin: 0; font-size: 12px; color: #aaaaaa; line-height: 1.6; text-align: center;">Ovela AI &bull; Booking Management System<br>This notification was sent automatically upon payment confirmation.</p>
            </div>
        </div>
    </div>
</body>
</html>'''
        
        sender = settings.MAIL_NOTIFICATIONS  # Ovela-branded for staff
        success = await self.send_email(staff_email, subject, html, from_email=sender)
        
        if success:
            logger.info(f"Staff payment notification sent to {staff_email} ({booking_reference})")
        
        return success

    async def send_payment_link(
        self,
        to_email: str,
        guest_name: str,
        booking_ref: str,
        payment_link: str,
        room_type: str,
        check_in: str,
        check_out: str,
        amount: float,
        business_name: str = "Motel",
        business_phone: str = "",
        business_location: str = "",
        tenant_id: str = "coalcreek",
        message_context: str = None
    ):
        """Send payment or card setup link to guest using CLIENT'S custom template."""
        if not to_email:
            return False
        
        is_setup = (amount == 0)
        subject_prefix = "Payment Required"
        subject = f"{subject_prefix} - {business_name} ({booking_ref})"
        
        try:
            ci = datetime.strptime(check_in, "%Y-%m-%d")
            co = datetime.strptime(check_out, "%Y-%m-%d")
            check_in_fmt = ci.strftime("%A, %d %B %Y")
            check_out_fmt = co.strftime("%A, %d %B %Y")
        except:
            check_in_fmt, check_out_fmt = check_in, check_out

        if message_context:
            content = message_context
        else:
            action_text = "To confirm your reservation, please securely save your card details via the button below. (No charge is made today)." if is_setup else "To secure your room, please complete payment using the secure link below."
            content = f"Your booking has been confirmed. {action_text}"
        
        html = self._client_template(tenant_id, {
            "guest_name": guest_name,
            "content": content,
            "booking_ref": booking_ref,
            "room_type": room_type,
            "check_in": check_in_fmt,
            "check_out": check_out_fmt,
            "amount": amount,
            "payment_link": payment_link,
            "business_name": business_name
        })
        
        sender = settings.MAIL_BOOKINGS
        return await self.send_email(to_email, subject, html, from_email=sender)


email_service = EmailService()

