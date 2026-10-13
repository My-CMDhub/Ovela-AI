"""
tests/test_demo_email_escaping.py — a website visitor's words can't rewrite the
team's demo-approval email.

name, business and phone come from a public form and were interpolated raw
into the HTML the team reads next to real Approve/Reject buttons, and into the
subject header.
"""

from unittest.mock import AsyncMock

from services.email import email_service

EVIL = '"><a href="https://evil.example">✅ Approve</a>'


async def test_visitor_values_are_escaped_and_the_subject_has_no_line_breaks(monkeypatch):
    sent = AsyncMock(return_value=True)
    monkeypatch.setattr(email_service, "send_email", sent)

    await email_service.send_demo_approval_request({
        "name": "Mallory\r\nBcc: victim@example.com",
        "business_name": "<script>x</script>",
        "phone": EVIL,
        "approve_url": "https://ok/approve",
        "reject_url": "https://ok/reject",
    })

    _recipients, subject, html = sent.await_args.args[:3]
    assert "\r" not in subject and "\n" not in subject
    assert "<script>x</script>" not in html
    assert 'href="https://evil.example"' not in html
    assert "&lt;script&gt;" in html
    assert "https://ok/approve" in html          # the real buttons survive
