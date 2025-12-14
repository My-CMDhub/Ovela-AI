import { Client, Databases } from "node-appwrite";

export default async ({ req, res, log, error }) => {
  // ---------- 1️⃣ Debug start ----------
  log("🔧 Function invoked");
  
  // ---------- 2️⃣ Parse payload ----------
  let payload;
  try {
    payload = typeof req.body === "string" ? JSON.parse(req.body) : req.body;
    log("✅ Payload parsed successfully");
  } catch (e) {
    error(`❌ Failed to parse request body: ${e.message}`);
    return res.json({ success: false, error: "Invalid payload" }, 400);
  }

  // ---------- 3️⃣ Extract data ----------
  // Note: Payload keys match the Appwrite Database Attribute names (Case Sensitive!)
  const { Name, email, phoneNumber, StudioSize, StudioName } = payload;
  if (!Name || !email) {
    error("❌ Missing required fields (Name or email)");
    return res.json({ success: false, error: "Missing name or email" }, 400);
  }
  log(`📧 New waitlist signup: ${Name} from ${StudioName || 'Unknown Studio'} (${email})`);

  // ---------- 4️⃣ Env vars ----------
  const RESEND_API_KEY = process.env.RESEND_API_KEY;
  const FROM_EMAIL = process.env.FROM_EMAIL || "hello@ovela.dev";
  const ADMIN_EMAIL = process.env.ADMIN_EMAIL;

  if (!RESEND_API_KEY) {
    error("❌ RESEND_API_KEY not set in environment");
    return res.json({ success: false, error: "Missing RESEND_API_KEY" }, 500);
  }

  // ---------- 5️⃣ Email template ----------
  
  const isGuideRequest = StudioName === "Popup Capture";
  const emailSubject = isGuideRequest ? "Your Studio Automation Blueprint 📄" : "✨ You’re on the early access list for Ovela";

  // Generate unsubscribe token
  const unsubscribeToken = Buffer.from(email).toString('base64');
  const unsubscribeUrl = `https://ovela.dev/unsubscribe?token=${unsubscribeToken}`;

  const getEmailContent = () => {
    if (isGuideRequest) {
      return {
        badge: "Guide Inside",
        title: "The Studio Automation<br>Blueprint is here.",
        intro: "You're taking the first step towards a stress-free studio. We've compiled the proven workflows top salons use to reclaim 20+ hours a week.",
        subHeading: "What's inside the guide",
        highlightTitle: "Key Strategies",
        steps: [
            "Auto-confirmations that actually reduce no-shows.",
            "Handling rescheduling without a single phone call.",
            "Reactivating dormant clients with automated warmth."
        ],
        buttonText: "View the Guide",
        buttonUrl: "https://ovela.dev/guide"
      };
    }
    return {
      badge: "Welcome to the Waitlist",
      title: `Hey ${Name},`,
      intro: "Thanks for joining the early access list — you’re officially on it.<br><br>Ovela is your upcoming AI receptionist built specifically for beauty and hair studios. It answers calls, handles bookings, and follows up with clients automatically.",
      subHeading: "Why this matters for your studio",
      highlightTitle: "What happens next",
      steps: [
          "We review your studio details to understand your workflow",
          "You’ll get priority access as soon as we open early trials",
          "We’ll reach out with simple onboarding instructions"
      ],
      buttonText: "Visit Website",
      buttonUrl: "https://ovela.dev"
    };
  };

  const content = getEmailContent();

  const welcomeEmailHtml = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="light only">
  <meta name="supported-color-schemes" content="light">
  <style>
    /* Force light mode only */
    :root { color-scheme: light only; supported-color-schemes: light; }
    * { color-scheme: light only !important; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'SF Pro Display', 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #1d1d1f !important; background-color: #f5f5f7 !important; margin: 0; padding: 0; -webkit-font-smoothing: antialiased; }
    .email-wrapper { width: 100%; background-color: #f5f5f7; padding: 40px 10px; }
    .email-container { max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); }
    .email-header { padding: 40px 30px 30px; text-align: center; background: #ffffff; border-bottom: 1px solid #f0f0f0; }
    .brand-logo { font-size: 32px; font-weight: 700; letter-spacing: -0.03em; color: #000000 !important; margin-bottom: 8px; }
    .brand-tagline { font-size: 14px; color: #86868b !important; font-weight: 500; }
    .email-body { padding: 32px 30px; }
    .welcome-badge { display: inline-block; padding: 6px 12px; background: #000000 !important; color: #ffffff !important; border-radius: 20px; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase; margin-bottom: 24px; }
    .greeting { font-size: 24px; font-weight: 700; color: #1d1d1f !important; margin-bottom: 20px; letter-spacing: -0.02em; line-height: 1.3; }
    .intro-text { font-size: 16px; line-height: 1.6; color: #1d1d1f !important; margin-bottom: 20px; }
    .sub-heading { font-size: 18px; font-weight: 700; color: #1d1d1f !important; margin-top: 32px; margin-bottom: 16px; }
    .highlight-box { background: #f9f9fa !important; border: 1px solid #e5e5e7; border-radius: 12px; padding: 24px; margin: 32px 0; }
    .highlight-title { font-size: 16px; font-weight: 700; color: #1d1d1f !important; margin-bottom: 20px; text-transform: uppercase; letter-spacing: 0.5px; }
    .step-table { width: 100%; border-collapse: collapse; }
    .step-cell-num { width: 40px; vertical-align: top; padding-bottom: 24px; padding-top: 4px; }
    .step-cell-content { vertical-align: top; padding-bottom: 24px; font-size: 16px; color: #1d1d1f !important; line-height: 1.6; }
    .step-circle { width: 28px; height: 28px; background: #000000 !important; color: #ffffff !important; border-radius: 50%; text-align: center; line-height: 28px; font-size: 14px; font-weight: 700; display: block; mso-hide: all; }
    .btn { display: inline-block; padding: 14px 28px; background-color: #000000; color: #ffffff !important; text-decoration: none; font-weight: 600; border-radius: 30px; font-size: 15px; margin-top: 10px; }
    .signature-section { margin-top: 40px; padding-top: 30px; border-top: 1px solid #e5e5e7; }
    .signature { font-size: 16px; color: #1d1d1f !important; font-weight: 600; margin-bottom: 4px; }
    .signature-role { font-size: 14px; color: #86868b !important; }
    .email-footer { padding: 30px; text-align: center; background: #f9f9fa; border-top: 1px solid #f0f0f0; }
    .footer-text { font-size: 12px; color: #86868b; line-height: 1.6; margin-bottom: 12px; }
    .footer-links a { color: #0066cc; text-decoration: none; font-size: 12px; margin: 0 10px; }
  </style>
</head>
<body>
  <div class="email-wrapper">
    <div class="email-container">
      <div class="email-header">
        <div class="brand-logo">Ovela</div>
        <div class="brand-tagline">AI Receptionist for Beauty & Hair Studios</div>
      </div>
      
      <div class="email-body">
        <div class="welcome-badge">${content.badge}</div>
        
        <h1 class="greeting">${content.title}</h1>
        
        <p class="intro-text">
          ${content.intro}
        </p>

        <h2 class="sub-heading">${content.subHeading}</h2>
        
        <div class="highlight-box">
          <div class="highlight-title">${content.highlightTitle}</div>
          
          <table class="step-table" border="0" cellpadding="0" cellspacing="0">
            ${content.steps.map((step, index) => `
            <tr>
              <td class="step-cell-num">
                <span class="step-circle">${index + 1}</span>
              </td>
              <td class="step-cell-content">
                ${step}
              </td>
            </tr>`).join('')}
          </table>
        </div>

        ${isGuideRequest ? `<div style="text-align: center; margin-bottom: 30px;"><a href="${content.buttonUrl}" class="btn">${content.buttonText}</a></div>` : ''}
        
        <p class="intro-text">
          ${isGuideRequest ? 'Implement these, and watch your calendar fill up.' : 'Until then, if you have questions or want to share specific challenges you face day-to-day, just reply — we read every message.'}
        </p>
        
        <div class="signature-section">
          <div class="signature">— The Ovela Team</div>
          <div class="signature-role">Building the stress-free studio</div>
        </div>
      </div>
      
      <div class="email-footer">
        <p class="footer-text">
          You received this email because you signed up at ovela.dev<br>
          ${email} • Joined ${new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
        </p>
        
        <div class="footer-links">
          <a href="https://ovela.dev">Visit Website</a>
          <a href="${unsubscribeUrl}">Unsubscribe</a>
        </div>
      </div>
    </div>
  </div>
</body>
</html>`;

  // ---------- 6️⃣ Send welcome email ----------
  try {
    const resp = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${RESEND_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        from: FROM_EMAIL,
        to: email,
        subject: "✨ You’re on the early access list for Ovela",
        html: welcomeEmailHtml,
      }),
    });

    const data = await resp.json();

    if (!resp.ok) {
      error(`❌ Resend API error: ${JSON.stringify(data)}`);
      return res.json({ success: false, error: data }, 500);
    }

    log(`✅ Welcome email sent to ${email} (Resend ID: ${data.id})`);

    // ---------- 7️⃣ Optional admin notification ----------
    if (ADMIN_EMAIL) {
      const adminResp = await fetch("https://api.resend.com/emails", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${RESEND_API_KEY}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          from: FROM_EMAIL,
          to: ADMIN_EMAIL,
          subject: `🔔 New Waitlist Signup: ${Name} from ${StudioName || 'Studio'}`,
          html: `<h2>New waitlist signup!</h2>
                 <ul>
                   <li><strong>Name:</strong> ${Name}</li>
                   <li><strong>Email:</strong> ${email}</li>
                   <li><strong>Phone:</strong> ${phoneNumber || 'Not provided'}</li>
                   <li><strong>Studio Name:</strong> ${StudioName || 'Not provided'}</li>
                   <li><strong>Studio Size:</strong> ${StudioSize}</li>
                 </ul>`,
        }),
      });
      const adminData = await adminResp.json();
      if (adminResp.ok) {
        log(`✅ Admin notification sent (Resend ID: ${adminData.id})`);
      } else {
        error(`❌ Admin notification failed: ${JSON.stringify(adminData)}`);
      }
    }

    return res.json({ success: true, emailId: data.id, message: "Welcome email sent" });
  } catch (e) {
    error(`❌ Unexpected error: ${e.message}`);
    return res.json({ success: false, error: e.message }, 500);
  }
};
