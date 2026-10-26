# FieldSales API v1

Base path `/api/v1`. Interactive docs: `/docs` (Swagger) and `/openapi.json`.

**Auth.** `POST /auth/login {username,password}` -> `{access_token, token_type, expires_in, user}` and sets two cookies:
`fs_access` (HttpOnly JWT, for browsers) and `fs_csrf` (readable; echo it in `X-CSRF-Token` on POST/PUT/PATCH/DELETE when using cookies).
Mobile/scripts send `Authorization: Bearer <access_token>` instead (no CSRF header needed). Company is taken from the token's user, never from the request.

**Errors** always look like `{"error": {"code": "...", "message": "...", "details": ...}}`:
400 bad request - 401 not authenticated/expired/revoked - 403 forbidden/inactive account/CSRF - 404 not found *(also returned for other companies' or non-visible records)* - 409 conflict/duplicate/invalid transition - 413/400 upload problems - 422 validation (`details: [{field,message}]`) / invalid relationship - 429 login rate limit - 500 server error (no internals leaked).

**Pagination** `?page=1&page_size=25` -> `{items,total,page,page_size}`. Datetimes are UTC ISO-8601 with `Z`; date filters (`date_from`, `date_to`, `due_from`, `due_to`) are `YYYY-MM-DD`, inclusive.

| Method & path | Permission | Notes |
|---|---|---|
| POST /auth/login, POST /auth/logout, GET/PUT /auth/me, POST /auth/change-password | - | logout revokes the token (denylist) |
| GET /companies, GET/PUT /companies/{id} | Company.View / Company.Edit | own company only |
| GET/POST /branches, GET/PUT/DELETE /branches/{id} | Branch.* | delete blocked while referenced |
| GET/POST /users, GET/PUT/DELETE /users/{id} | User.* | `?q&role_id&status&scope=assigned`; DELETE = deactivate |
| GET /roles, GET /permissions, PUT /roles/{id}/permissions | User.View / Company.Edit | Administrator role locked |
| GET /customers/options | auth | business types / products |
| GET/POST /customers, GET/PUT/DELETE /customers/{id}, PATCH /customers/{id}/status | Customer.* | `?q&status&city&business_type&salesman_id&unassigned`; scoped by visibility |
| POST /customers/{id}/photo | Customer.Edit (or salesman w/ Visit.Create) | multipart `file`; JPEG/PNG/WebP, 5 MB, re-encoded |
| POST/GET /customers/{id}/assignments, GET /assignments | Customer.Assign / Customer.View | POST reassigns; history kept |
| GET /customers/{id}/activity, GET /customers/{id}/followups | Customer.View / FollowUp.View | timeline / follow-up history |
| GET/POST /visits, GET /visits/{id}, POST /visits/{id}/photo | Visit.View / Visit.Create | see below |
| GET/POST /followups, GET/PUT /followups/{id} | FollowUp.* | `?status&customer_id&salesman_id&due_from&due_to&overdue&upcoming` |
| POST /followups/{id}/status, POST /followups/{id}/complete | FollowUp.Edit / FollowUp.Complete | optional `outcome_text` |
| GET/POST /followups/{id}/outcomes | FollowUp.View / FollowUp.Edit | append-only history |
| GET /dashboard?tz_offset_minutes=240 | auth | `kind`: admin / manager / salesman |
| GET /reports/{customers,assignments,visits,salesman-activity,followups,customer-activity} | Reports.View | `?format=csv` downloads; pending/overdue/completed = `followups?status=Pending` / `?overdue=true` / `?status=Completed` |
| GET /files/{customers\|visits}/{name} | auth | private images; served only if the referencing record is visible |
| GET /health, GET /health/db | - | liveness / DB readiness |

### `POST /visits`
```json
{
  "customer_id": 12,                       // XOR with new_customer
  "new_customer": {"name":"Test Cafe","mobile":"+971500000123","city":"Dubai","business_type":"Restaurant"},
  "branch_id": null,                       // optional; must belong to your company (422 otherwise)
  "visit_time": "2026-10-25T08:30:00Z",    // optional, defaults to now (UTC)
  "latitude": 25.2048, "longitude": 55.2708,   // optional, both or neither
  "purpose": "Demo", "notes": "...", "outcome": "Interested",
  "follow_up_date": "2026-10-30T09:00:00Z", // optional -> creates Pending follow-up "Follow-up with {customer}"
  "follow_up_notes": "Send quote"
}
```
Customer (if new), visit and follow-up are saved in **one transaction**. Response is the visit plus `follow_up_id`.

### Default permissions
Administrator: all. Manager: everything except Company.Edit, Branch.Create/Edit/Delete, User.Create/Edit/Delete, Customer.Delete.
Salesman: Company.View, Branch.View, Customer.View, Visit.View/Create, FollowUp.View/Create/Edit/Complete.
