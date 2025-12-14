# Employee/Staff Management Implementation Plan

## Goal
Enable business owners to manage staff members with optional availability schedules. Support staff-specific booking requests with dynamic AI behavior and owner approval workflow.

---

## User Review Required

> [!IMPORTANT]
> **New Appwrite Collection**: A new `staff_members` collection will be created to store employee data.

> [!WARNING]
> **Booking Request Workflow**: When a customer requests a specific staff member who doesn't have availability configured, the AI will inform them that owner approval is needed. The request will appear in a new "Pending Requests" section in the dashboard.

---

## Proposed Changes

### Database Schema

#### [NEW] `staff_members` Collection
Attributes:
- `business_id` (string, required) — Link to business
- `name` (string, required) — Staff member name
- `services` (string, optional) — JSON array of service names they can provide
- `availability` (string, optional) — JSON object with schedule (e.g., `{"monday": ["9:00-12:00", "14:00-17:00"]}`)
- `is_active` (boolean, default: true) — Whether staff member is currently active

#### [NEW] `booking_requests` Collection
Attributes:
- `business_id` (string, required)
- `customer_id` (string, required)
- `whatsapp_id` (string, required)
- `staff_member_id` (string, required) — Requested staff member
- `service_name` (string, required)
- `preferred_date` (string, optional) — Customer's preferred date
- `status` (string, required) — `pending`, `approved`, `rejected`
- `created_at` (datetime)
- `conversation_id` (string) — Link back to conversation

---

### Frontend Changes

#### [NEW] `/dashboard/staff/page.tsx`
Staff management page with:
- Table listing all staff members
- "Add Staff" button → Opens modal
- Edit/Delete actions per row
- Toggle for active/inactive status

#### [NEW] `/dashboard/staff/[id]/page.tsx` (Optional Detail View)
Staff member detail page with:
- Name, services, availability editor
- Visual weekly calendar for availability
- Save/Cancel buttons

#### [NEW] `/dashboard/requests/page.tsx`
Pending booking requests page with:
- Table showing customer name, requested staff, service, date
- Approve/Reject buttons
- Filter by status (pending/approved/rejected)

#### [MODIFY] `DashboardSidebar.tsx`
Add navigation links:
- "Staff" (Users icon)
- "Requests" (ClipboardList icon) with badge showing pending count

---

### Backend Changes

#### [NEW] `/api/dashboard/staff` Endpoints
- `GET /api/dashboard/staff` — List all staff for business
- `POST /api/dashboard/staff` — Create new staff member
- `PATCH /api/dashboard/staff/{id}` — Update staff member
- `DELETE /api/dashboard/staff/{id}` — Delete staff member

#### [NEW] `/api/dashboard/requests` Endpoints
- `GET /api/dashboard/requests` — List booking requests (with filters)
- `PATCH /api/dashboard/requests/{id}/approve` — Approve request
- `PATCH /api/dashboard/requests/{id}/reject` — Reject request

#### [MODIFY] `backend/core/ai.py`
Update AI prompt with staff-aware logic:
- If staff configured with availability → Check their schedule
- If staff exists but no availability → Create booking request, inform customer
- If no staff preference → Book normally (any available slot)

#### [NEW] `backend/services/staff.py`
Service layer for:
- `get_staff_members(business_id)` — Fetch all staff
- `get_staff_availability(staff_id, date)` — Check if staff available
- `create_booking_request(...)` — Create pending request
- `notify_customer_on_approval(request_id)` — Send WhatsApp message when approved

---

## AI Behavior Flow

### Scenario 1: Staff with Full Availability
**Customer:** "Book me with Sarah tomorrow at 2pm"
**AI:** 
1. Checks if Sarah exists
2. Checks Sarah's availability for tomorrow 2pm
3. If available → Books directly
4. If not → Suggests Sarah's next available slot

### Scenario 2: Staff without Availability
**Customer:** "I want an appointment with John"
**AI:**
1. Checks if John exists
2. Sees John has no availability configured
3. Creates booking request
4. Response: "I've sent your request to book with John to the owner. They'll confirm availability and get back to you soon! You can also call us at [phone] if it's urgent."

### Scenario 3: No Staff Preference
**Customer:** "Book me a facial tomorrow"
**AI:**
1. Doesn't mention staff at all
2. Books normally with any available slot

---

## Verification Plan

### Manual Testing
1. **Staff CRUD**: Add/edit/delete staff members in dashboard
2. **Availability Config**: Set weekly schedule for a staff member
3. **AI with Availability**: Request specific staff → AI checks schedule
4. **AI without Availability**: Request unconfigured staff → Creates request
5. **Approval Flow**: Owner approves request → Customer gets WhatsApp notification
6. **Rejection Flow**: Owner rejects → Customer gets polite message

### Edge Cases
- Customer requests non-existent staff name → AI politely says "We don't have that staff member"
- Multiple staff with same name → AI asks for clarification
- Staff deleted while request pending → Handle gracefully
