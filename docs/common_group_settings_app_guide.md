# Common Group Settings: App Integration Guide

Use the common-settings API to load and update a group's shared settings from
the app. The settings route is registered under `/api/v1/groups`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/groups/{group_id}/settings/common` | Load settings for the group |
| `PATCH` | `/api/v1/groups/{group_id}/settings/common` | Update one or more settings |

Send the signed-in user's access token with both requests:

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

An active group member can read settings. Only an active group admin can update
them. Use the `group_id` from the selected group; do not use the group's display
name or the current user's ID in its place.

## Loading settings

Call the GET endpoint when opening the group's settings screen and when
refreshing it. A successful response has this shape:

```json
{
  "status": "success",
  "data": {
    "allow_partial_payments": false,
    "minimum_partial_payment_amount": null,
    "minimum_kyc_tier": 1,
    "group_start_time": 1792842962000,
    "require_guarantor": false,
    "maximum_member_capacity": 20,
    "collection_frequency_days": 7,
    "grace_period_hours": 24,
    "late_payment_policy": "STRIKE_AND_KEEP",
    "payment_approval_threshold": null,
    "allow_advance_payments": true
  }
}
```

`data` is the settings object to display. `null` means a value is not set where
the setting is optional.

## Updating settings

PATCH is a partial update: include only the setting or settings the admin
changed. Do not send the entire screen model by default. For example, enabling
partial payments requires the minimum amount in the same request unless one is
already saved:

```http
PATCH /api/v1/groups/{group_id}/settings/common
```

```json
{
  "allow_partial_payments": true,
  "minimum_partial_payment_amount": 1000
}
```

A successful update returns the current settings object:

```json
{
  "status": "success",
  "message": "Common settings updated.",
  "data": {
    "allow_partial_payments": true,
    "minimum_partial_payment_amount": 1000,
    "minimum_kyc_tier": 1,
    "group_start_time": 1792842962000,
    "require_guarantor": false,
    "maximum_member_capacity": 20,
    "collection_frequency_days": 7,
    "grace_period_hours": 24,
    "late_payment_policy": "STRIKE_AND_KEEP",
    "payment_approval_threshold": null,
    "allow_advance_payments": true
  }
}
```

Use the returned `data` to refresh the screen after a successful update. If the
request fails, keep the previous UI value and show the API error instead of
showing the unsaved value as successful.

## Settings and values

| JSON field | App behavior / value |
|---|---|
| `allow_partial_payments` | Boolean. When `true`, members may pay in installments. A positive `minimum_partial_payment_amount` is required. |
| `minimum_partial_payment_amount` | Positive amount in UGX required when partial payments are enabled. |
| `minimum_kyc_tier` | Integer from `0` to `3`, inclusive. |
| `group_start_time` | Unix epoch timestamp in milliseconds. |
| `require_guarantor` | Boolean. Whether the group requires a guarantor. |
| `maximum_member_capacity` | Positive integer, or `null` for no configured limit. The limit cannot be lowered below the current active-member count. |
| `collection_frequency_days` | Non-negative integer. `0` means daily/flexible; a positive value is the interval in days. |
| `grace_period_hours` | Non-negative integer number of hours. |
| `late_payment_policy` | Policy identifier; the accepted values depend on group type (see below). |
| `payment_approval_threshold` | Optional non-negative payment amount in UGX. The settings API saves and returns this value; the payment-processing flow must also read and enforce it for it to change payment approval behavior. |
| `allow_advance_payments` | Boolean. Whether members may pay ahead toward upcoming contributions. |

### Late payment policy values

The API accepts these identifiers, with additional group-type restrictions:

- `MERRY_GO_ROUND`: `STRIKE_AND_KEEP`, `KICK_AND_BAN`,
  `USE_GUARANTOR_FUNDS`
- `GOAL_SAVINGS`: `RECORD_STRIKE`, `REMOVE_AND_REFUND`
- `WELFARE_FUND`: `SUSPEND_CLAIM_RIGHTS`, `RECORD_STRIKE`
- Other group types: any of the six identifiers above passes the common-setting
  validation.

Send and retain the exact identifier; the app can map it to a localized label
for display.

## Validation and errors

- `401`: the request is unauthenticated or the token is invalid.
- `403`: the user is not an active member for GET, or is not an active admin for
  PATCH.
- `404`: the group does not exist.
- `400`: no fields were supplied, or capacity would be set below the active
  member count.
- `422`: a value is outside its allowed range, a policy is invalid for the
  group type, or partial payments are enabled without a positive minimum.

When disabling partial payments, the minimum can remain saved; it is ignored
while `allow_partial_payments` is `false`.

## Group chat system messages

The backend automatically creates one `SYSTEM_EVENT` group-chat message for
each setting whose value actually changes. Each message is saved against the
same `group_id` used in the PATCH request, identifies the admin by name, states
the new value, and explains the effect. The app does not need to create a
second chat message itself. Messages are sent through the existing group-chat
broadcast flow.

The message attachment includes:

```json
{
  "category": "SETTINGS_UPDATE",
  "setting_type": "COMMON",
  "setting": "allow_partial_payments",
  "admin_id": "<admin_user_id>",
  "admin_name": "Group Admin",
  "changes_count": 1
}
```

Use the app's existing group-chat message/real-time update handling to display
these messages. PATCHing a value to the value it already has creates no
message.

## App implementation flow

1. Open a group settings screen and GET `/settings/common` for that group's ID.
2. Populate controls from `data`; keep `null` values as unset rather than
   displaying them as zero.
3. Only show editable controls when the current user is an admin; still handle
   a `403` in case membership or role changed.
4. On Save, PATCH only changed fields. When enabling partial payments, include
   a valid minimum payment amount in that request or ensure one is already
   saved.
5. Replace the screen state with the returned `data`.
6. Let the existing group-chat flow display the system message(s) created by
   the backend.

## Implementation references

- API route: `app/api/routes/group/settings/commonsetting/common_settings.py`
- System-message formatter/broadcaster:
  `app/api/routes/group/settings/common_settings_messages.py`
- Settings model: `app/models/group/settings/group_common_settings.py`
- API tests: `tests/test_group_common_settings.py`
