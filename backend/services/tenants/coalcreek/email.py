"""
Coal Creek Motel - Email Service
================================
Tenant-specific email templates and methods.

Usage:
    from services.tenants.coalcreek.email import coalcreek_email_service
    await coalcreek_email_service.send_booking_approval_request(...)
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from services.email import EmailService
from .config import COALCREEK_CONFIG

logger = logging.getLogger(__name__)
MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")


class CoalCreekEmailService(EmailService):
    """Coal Creek Motel branded email service."""
    
    def __init__(self):
        super().__init__()
        self.config = COALCREEK_CONFIG
        self.tenant_id = "coalcreek"
    
    def _template(
        self,
        title: str,
        content: str,
        details: list = None,
        button_text: str = None,
        button_url: str = None,
        action_buttons_html: str = ""
    ) -> str:
        """Generate Coal Creek branded email HTML."""
        primary = self.config["primary_color"]
        logo_url = self.config["logo_url"]
        address = self.config["address"]
        phone = self.config["phone"]
        
        details_html = ""
        if details:
            details_html = f'''
            <div style="background: #f9f9fa; border: 1px solid #e5e5e7; border-radius: 12px; padding: 24px; margin: 24px 0;">
                <table style="width: 100%;" border="0" cellpadding="0" cellspacing="0">
                    {"".join([f'<tr><td style="padding: 8px 0; font-size: 15px; color: #1d1d1f;">{d}</td></tr>' for d in details])}
                </table>
            </div>
            '''
        
        button_html = ""
        if button_text and button_url:
            button_html = f'''
            <div style="text-align: center; margin: 30px 0;">
                <a href="{button_url}" style="display: inline-block; padding: 14px 28px; background-color: {primary}; color: #ffffff; text-decoration: none; font-weight: 600; border-radius: 30px; font-size: 15px;">{button_text}</a>
            </div>
            '''
        
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; color: #1d1d1f; background-color: #f5f5f7; margin: 0; padding: 0;">
    <div style="width: 100%; background-color: #f5f5f7; padding: 40px 10px;">
        <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);">
            <div style="padding: 40px 30px 30px; text-align: center; background: {primary};">
                <img src="{logo_url}" alt="Coal Creek Motel" style="max-width: 150px; margin-bottom: 10px;" onerror="this.style.display='none'">
                <div style="font-size: 28px; font-weight: 700; color: #ffffff;">Coal Creek Motel</div>
                <div style="font-size: 14px; color: #ffffff99; font-weight: 500;">South Gippsland, Victoria</div>
            </div>
            
            <div style="padding: 32px 30px;">
                <h1 style="font-size: 24px; font-weight: 700; color: #1d1d1f; margin-bottom: 20px;">{title}</h1>
                <p style="font-size: 16px; color: #1d1d1f; margin-bottom: 20px;">{content}</p>
                {details_html}
                {button_html}
                {action_buttons_html}
            </div>
            
            <div style="padding: 30px; text-align: center; background: #f9f9fa; border-top: 1px solid #f0f0f0;">
                <p style="font-size: 12px; color: #86868b; margin-bottom: 4px;">{address}</p>
                <p style="font-size: 12px; color: #86868b;">📞 {phone} | Powered by Ovela AI</p>
            </div>
        </div>
    </div>
</body>
</html>'''

    async def send_booking_approval_request(
        self,
        staff_email: str,
        guest_name: str,
        guest_phone: str,
        check_in: str,
        check_out: str,
        room_type: str,
        total_amount: float,
        booking_reference: str,
        num_nights: int = 1,
        notification_id: str = None,
        guest_email: str = None
    ):
        """Send Coal Creek branded booking approval request to staff."""
        if not staff_email:
            staff_email = self.config["staff_email"]
        
        subject = f"📋 NEW BOOKING: {guest_name} - {room_type.title()} Room"
        
        # Format dates
        try:
            ci = datetime.strptime(check_in, "%Y-%m-%d")
            co = datetime.strptime(check_out, "%Y-%m-%d")
            check_in_fmt = ci.strftime("%a, %d %b")
            check_out_fmt = co.strftime("%a, %d %b")
        except:
            check_in_fmt, check_out_fmt = check_in, check_out
        
        # Build action buttons
        action_html = ""
        if notification_id:
            from services.magic_links import generate_action_url
            approve_url = generate_action_url(notification_id, "approve")
            reject_url = generate_action_url(notification_id, "reject")
            
            action_html = f'''
            <div style="margin: 32px 0; padding: 24px; background: #f9f9fa; border-radius: 12px;">
                <div style="font-weight: 700; margin-bottom: 16px;">Quick Actions</div>
                <div style="margin-bottom: 12px;">
                    <a href="{approve_url}" style="display: inline-block; padding: 12px 24px; background: #22c55e; color: white; text-decoration: none; border-radius: 8px; font-weight: 600;">✅ Approve</a>
                </div>
                <div><a href="{reject_url}" style="display: inline-block; padding: 12px 24px; background: #ef4444; color: white; text-decoration: none; border-radius: 8px; font-weight: 600;">❌ Reject</a></div>
            </div>
            '''
        
        details = [
            f"<strong>Guest:</strong> {guest_name}",
            f"<strong>Phone:</strong> <a href='tel:{guest_phone}'>{guest_phone}</a>",
            f"<strong>Email:</strong> {guest_email or 'Not provided'}",
            f"<strong>Room:</strong> {room_type.title()} Room",
            f"<strong>Check-in:</strong> {check_in_fmt}",
            f"<strong>Check-out:</strong> {check_out_fmt}",
            f"<strong>Nights:</strong> {num_nights}",
            f"<strong style='font-size: 18px;'>Total: ${total_amount}</strong>",
            f"<span style='color: #86868b;'>Ref: {booking_reference}</span>"
        ]
        
        html = self._template(
            title=f"New booking from {guest_name}",
            content="Please review and approve or reject.",
            details=details,
            button_text=f"📞 Call {guest_name}",
            button_url=f"tel:{guest_phone}",
            action_buttons_html=action_html
        )
        
        sender = f"Coal Creek Motel <notifications@ovela.dev>"
        return await self.send_email(staff_email, subject, html, from_email=sender)

    async def send_guest_confirmation(
        self,
        guest_email: str,
        guest_name: str,
        booking_reference: str,
        room_type: str,
        check_in: str,
        check_out: str,
        num_nights: int,
        total_amount: float
    ):
        """Send Coal Creek branded confirmation to guest."""
        if not guest_email:
            logger.info("No guest email - skipping confirmation")
            return False
        
        subject = f"✅ Booking Confirmed - Coal Creek Motel ({booking_reference})"
        
        try:
            ci = datetime.strptime(check_in, "%Y-%m-%d")
            co = datetime.strptime(check_out, "%Y-%m-%d")
            check_in_fmt = ci.strftime("%A, %d %B %Y")
            check_out_fmt = co.strftime("%A, %d %B %Y")
        except:
            check_in_fmt, check_out_fmt = check_in, check_out
        
        details = [
            f"<strong>Booking Ref:</strong> <span style='font-size: 18px; font-weight: 700;'>{booking_reference}</span>",
            f"<strong>Room:</strong> {room_type.title()} Room",
            f"<strong>Check-in:</strong> {check_in_fmt} (from 2:00 PM)",
            f"<strong>Check-out:</strong> {check_out_fmt} (by 10:00 AM)",
            f"<strong>Nights:</strong> {num_nights}",
            f"<strong style='font-size: 18px;'>Total: ${total_amount}</strong>"
        ]
        
        html = self._template(
            title=f"Your booking is confirmed, {guest_name}!",
            content="Thank you for choosing Coal Creek Motel. We look forward to welcoming you!",
            details=details,
            button_text=f"📞 Call Us: {self.config['phone']}",
            button_url=f"tel:{self.config['phone'].replace(' ', '')}"
        )
        
        sender = "Coal Creek Motel <notifications@ovela.dev>"
        return await self.send_email(guest_email, subject, html, from_email=sender)

    async def send_payment_notification(
        self,
        staff_email: str,
        booking_reference: str,
        customer_name: str,
        customer_email: str,
        room_type: str,
        check_in: str,
        check_out: str,
        num_nights: int,
        amount_paid: float
    ):
        """Notify staff when payment is received."""
        if not staff_email:
            staff_email = self.config["staff_email"]
        
        subject = f"💰 Payment Received - Booking {booking_reference}"
        
        try:
            ci = datetime.strptime(check_in, "%Y-%m-%d")
            co = datetime.strptime(check_out, "%Y-%m-%d")
            check_in_fmt = ci.strftime("%A, %d %B %Y")
            check_out_fmt = co.strftime("%A, %d %B %Y")
        except:
            check_in_fmt, check_out_fmt = check_in, check_out
        
        if amount_paid > 0:
            title = "Booking Paid & Confirmed"
            content = "The customer has completed payment."
            amount_display = f"<strong style='font-size: 22px; color: #22c55e;'>Amount Paid: ${amount_paid}</strong>"
        else:
            title = "Card Verified & Secured" 
            content = "The customer has successfully saved their card on file (Pre-Auth)."
            amount_display = "<strong style='font-size: 22px; color: #22c55e;'>✅ Card Secured (No Charge)</strong>"

        details = [
            f"<strong>Booking Ref:</strong> <span style='font-size: 18px; font-weight: 700;'>{booking_reference}</span>",
            f"<strong>Customer:</strong> {customer_name}",
            f"<strong>Email:</strong> {customer_email}",
            f"<strong>Room:</strong> {room_type.title()} Room",
            f"<strong>Check-in:</strong> {check_in_fmt}",
            f"<strong>Check-out:</strong> {check_out_fmt}",
            amount_display
        ]
        
        action_html = '''
        <div style="background: #dbeafe; border: 1px solid #3b82f6; border-radius: 8px; padding: 16px; margin: 24px 0;">
            <p style="margin: 0; font-size: 14px; color: #1e40af;">
                <strong>✅ Next Step:</strong> Add this booking to Update247 CRM
            </p>
        </div>
        '''
        
        html = self._template(
            title=title,
            content=content,
            details=details,
            action_buttons_html=action_html
        )
        
        sender = "Coal Creek Motel <notifications@ovela.dev>"
        return await self.send_email(staff_email, subject, html, from_email=sender)

    async def send_expiry_notification(
        self,
        staff_email: str,
        booking_ref: str,
        customer_name: str,
        room_type: str,
        check_in: str
    ):
        """Notify staff that a booking link expired."""
        if not staff_email:
            staff_email = self.config["staff_email"]
            
        subject = f"⚠️ Booking Expired - Dates Released ({booking_ref})"
        
        details = [
            f"<strong>Booking Ref:</strong> {booking_ref}",
            f"<strong>Guest:</strong> {customer_name}",
            f"<strong>Room:</strong> {room_type}",
            f"<strong>Check-in:</strong> {check_in}"
        ]
        
        content = "The payment/setup link for this booking has expired (24 hours passed).<br>The booking is now marked as <strong>EXPIRED</strong> and dates are released."
        
        html = self._template(
            title="Booking Expired / Cancelled",
            content=content,
            details=details
        )
        
        sender = "Coal Creek Motel <notifications@ovela.dev>"
        return await self.send_email(staff_email, subject, html, from_email=sender)

    async def send_payment_link(
        self,
        to_email: str,
        guest_name: str,
        booking_ref: str,
        payment_link: str,
        room_type: str,
        check_in: str,
        check_out: str,
        amount: float
    ):
        """Send payment link to guest."""
        if not to_email:
            return False
        
        is_setup = (amount == 0)
        subject_prefix = "Secure Your Booking" if is_setup else "Payment Required"
        subject = f"{subject_prefix} - Booking {booking_ref}"
        
        try:
            ci = datetime.strptime(check_in, "%Y-%m-%d")
            co = datetime.strptime(check_out, "%Y-%m-%d")
            check_in_fmt = ci.strftime("%A, %d %B %Y")
            check_out_fmt = co.strftime("%A, %d %B %Y")
        except:
            check_in_fmt, check_out_fmt = check_in, check_out
            
        amount_display = f"<strong style='font-size: 18px;'>TOTAL TO PAY: ${amount}</strong>"
        if is_setup:
            amount_display = "<strong>Secure Card (No charge today)</strong>"

        details = [
            f"<strong>Booking Ref:</strong> {booking_ref}",
            f"<strong>Room:</strong> {room_type.title()} Room",
            f"<strong>Check-in:</strong> {check_in_fmt}",
            f"<strong>Check-out:</strong> {check_out_fmt}",
            amount_display
        ]
        
        action_text = "To secure your room, please securely save your card details below." if is_setup else "To secure your room, please complete payment using the secure link below."
        content = f"Hi {guest_name},<br><br>Your booking request has been approved! {action_text}"
        
        btn_text = "💳 Secure Booking" if is_setup else "💳 Pay Securely Now"
        title_text = "Booking Approved - Security Required" if is_setup else "Booking Approved - Payment Required"
        
        html = self._template(
            title=title_text,
            content=content,
            details=details,
            button_text=btn_text,
            button_url=payment_link
        )
        
        sender = "Coal Creek Motel <notifications@ovela.dev>"
        return await self.send_email(to_email, subject, html, from_email=sender)


# Singleton instance
coalcreek_email_service = CoalCreekEmailService()
