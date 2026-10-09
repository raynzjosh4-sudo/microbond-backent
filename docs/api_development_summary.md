# Microbond Backend – Development Summary

## 1. Group Creation Hardening

**Files:** `app/api/routes/group/rotating.py`, `app/api/routes/group/target_savings.py`

- Strict response schemas: `RotatingGroupCreateResponse`, `TargetSavingsGroupCreateResponse`.
- Each route wraps DB work in `try...except`; on failure it calls `session.rollback()` so no partial group is saved.
- Phone numbers are cleaned with `sanitize_uganda_phone`. It raises `ValueError`, which the route converts to `400 Bad Request`.
- OpenAPI metadata (`summary`, `description`, `response_model`, `status_code`) is added to every route, so the FastAPI docs at `/docs` are usable for testing.
- Missing rotating-group settings (e.g. max capacity, extra time to pay, late penalty) block creation. Auto-calculated fields are computed by the backend.

## 2. Group Settings Update (RBAC)

The Android app (`feature_settings`, `GroupSettingsAccessState.kt`) controls which settings each role can see and edit. The backend now supports this.

| Piece | File | Purpose |
|---|---|---|
| Model | `app/models/group/settings.py` | New JSON column `member_visibility_overrides` stores admin-defined visibility for members |
| Schema | `app/schemas/group_settings_update_request.py` | `GroupSettingsUpdateRequest`; every field is `Optional` for partial updates |
| Route | `app/api/routes/group/settings.py` | `PATCH /api/v1/groups/{group_id}/settings` |
| Registration | `app/main.py` | Settings router included |

**Behaviour**
- Only a group `ADMIN` can update settings.
- Only the fields sent in the request are changed.
- Works for all group types (rotating, target savings and others).
- `member_visibility_overrides` is a dict such as `{"late_penalty": false}`. It tells the app which settings standard members can see.

> After adding the JSON column, run a migration (like `migrate_rotating_group.py`) on existing databases.

## 3. Pending Work
- Trust score calculation service
- Admin payout-order update endpoint (rotating groups)
- Emergency/Welfare group type
- Long-term saving group settings table
