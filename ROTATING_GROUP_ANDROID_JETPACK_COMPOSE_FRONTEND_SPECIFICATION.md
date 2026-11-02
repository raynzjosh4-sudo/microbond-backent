# Report Sections and Member Visibility: Backend Integration Guide

## Goal

The Save Report page must show:

1. Its nine existing report sections.
2. The group-type-specific settings shown on the admin Member visibility page.

For a regular member, an option is available only when its matching admin visibility setting is enabled. If it is disabled, omit it from the report setup and reject it if a client submits it anyway. Admins may inspect all options. The server is authoritative; filtering in Android is for presentation, not security.

## Current Android Flow

- `SaveReportScreen.kt` defines the nine fixed report choices and receives the active `groupId` and `groupType`.
- It calls `GET /api/v1/groups/{groupId}/settings/member-visibility` and reads `data.toggles` and `data.sections`.
- It enumerates the group's `ADMIN_SHAREABLE` settings via `shareableSettingsByPage(groupType)`. It currently appends a setting to the report choices only when the corresponding visibility value is `true`. If loading fails or a key is absent, that setting stays hidden.
- `ThreadOverlays.kt` passes the active group ID and type through `ThreadAttachmentHandler.kt` to the report screen.
- `ThreadAttachmentHandler.kt` maps the nine report choices to the existing bubble section keys: `WEEK TOTALS`, `DAILY SAVING`, `BALANCE COUNTS`, `MEMBERS`, `ACTIVITY`, and `PAYOUT ROTATION`. It also keeps selected option names in `WeeklyReportData.visibleSections`.
- `MicroBondWeeklyReportBubble.kt` renders those known section keys. It does not yet render arbitrary Member visibility setting names as report data. The backend must supply actual values for any new report option; merely adding a checkbox does not generate its contents.

Current base-section gate mapping in `SaveReportScreen.kt`:

| Report option | Current visibility key |
| --- | --- |
| Week summary | `vis_share_financial_snapshots` |
| Daily records | No dedicated gate yet |
| Member balances | `vis_share_financial_snapshots` |
| Members who saved | No dedicated gate yet |
| Members who missed | No dedicated gate yet |
| Payout rotation | No dedicated gate yet |
| Group activity | `vis_share_financial_snapshots` |
| Contribution history | No dedicated gate yet |
| All members | No dedicated gate yet |

The three rows using `vis_share_financial_snapshots` currently turn on and off together. If admins need independent control, give each report section its own key.

## Existing Database and Important Distinction

`dbtables.sql` defines `public.groupvisibilitysettings`. It already stores many `vis_*` columns for group settings, including:

- Type rules, governance, liquidity, privacy, communications, reminders, and milestones.
- `vis_share_financial_snapshots` and other visibility controls.
- Five report-detail flags: `vis_report_expected_revenue`, `vis_report_actual_collection`, `vis_report_deficit`, `vis_report_reserve_fund`, and `vis_report_escrow_holds`.

Those five flags control report fields/details, not all nine Save Report section choices. The backend must decide and document which data each flag governs, return them to Android, and enforce them while building report payloads. The current Android Member visibility DTO does not expose all five fields.

The existing `public.groupreport` table is for a user reporting a group to moderators (`reason`, `description`, `status`). It is **not** storage for a generated financial report. `public.groupchatmessage.attachments` is JSON and currently can carry report-bubble data, but the client constructs a sample `WeeklyReportData` locally. There is no dedicated generated-report API in this Android client.

`wsql.sql` duplicates much of `dbtables.sql`; keep both schema snapshots aligned if both remain in use. Production changes should be delivered as a versioned database migration, not only by editing a snapshot.

## Database Change for the Nine Report Sections

Recommended: store section-level member visibility in a dedicated table. This avoids adding another nine columns to the already-wide `groupvisibilitysettings` table and gives each report option a stable key.

```sql
CREATE TABLE public.groupreportsectionvisibility (
    group_id character varying NOT NULL
        REFERENCES public.group(group_id) ON DELETE CASCADE,
    section_key character varying NOT NULL,
    visible_to_members boolean NOT NULL DEFAULT false,
    updated_by uuid REFERENCES public.user(id),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT groupreportsectionvisibility_pkey PRIMARY KEY (group_id, section_key),
    CONSTRAINT groupreportsectionvisibility_section_key_check CHECK (
        section_key IN (
            'week_summary',
            'daily_records',
            'member_balances',
            'members_who_saved',
            'members_who_missed',
            'payout_rotation',
            'group_activity',
            'contribution_history',
            'all_members'
        )
    )
);
```

Seed one row for each of the nine keys when a group is created, or lazily insert missing rows with `visible_to_members = false`. This makes a new section hidden by default. Admin changes should be an upsert scoped to the authorized `group_id`.

Continue to store existing Member visibility choices in `groupvisibilitysettings`. Do not copy those values into a second source of truth. If the project later moves those existing wide columns to a normalized `groupmembervisibility(group_id, setting_key, visible_to_members)` table, migrate all existing `vis_*` values and update both the admin UI and report API together.

## Visibility Catalog and Stable Keys

Keep a server-side catalog (or a shared contract) for every option. Each entry should define:

- `key`: stable machine key, never a display label.
- `label` and optional `description` for the UI.
- Applicable group types, if any.
- Source visibility key: one of the nine `groupreportsectionvisibility.section_key` values or an existing `groupvisibilitysettings` key.
- Data resolver: which query/model produces the report value.

Examples:

| Report option | Stable report key | Visibility source |
| --- | --- | --- |
| Week summary | `week_summary` | `groupreportsectionvisibility.week_summary` |
| Daily records | `daily_records` | `groupreportsectionvisibility.daily_records` |
| Member balances | `member_balances` | `groupreportsectionvisibility.member_balances` plus applicable `vis_report_*` field flags |
| Members who saved | `members_who_saved` | `groupreportsectionvisibility.members_who_saved` |
| Members who missed | `members_who_missed` | `groupreportsectionvisibility.members_who_missed` |
| Payout rotation | `payout_rotation` | `groupreportsectionvisibility.payout_rotation` and the group's payout rules |
| Group activity | `group_activity` | `groupreportsectionvisibility.group_activity` |
| Contribution history | `contribution_history` | `groupreportsectionvisibility.contribution_history` |
| All members | `all_members` | `groupreportsectionvisibility.all_members` |

For the additional Member visibility settings in the report list, reuse their existing stable `vis_*` keys. The label/catalog comes from the current `SavingsGroupType` settings catalog (`shareableSettingsByPage(groupType)` in Android today); the server needs an equivalent catalog or a shared definition so labels and keys do not drift.

## API Contract

### Admin updates visibility

Keep the existing endpoint and extend its request/response contract for the nine report-section keys:

```http
PATCH /api/v1/groups/{group_id}/settings/member-visibility
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "report_sections": {
    "week_summary": false,
    "daily_records": true,
    "member_balances": false,
    "members_who_saved": true,
    "members_who_missed": true,
    "payout_rotation": true,
    "group_activity": false,
    "contribution_history": true,
    "all_members": false
  }
}
```

The backend must verify the caller is an admin of that group before updating. Keep existing visibility request fields working during migration; do not silently drop old `vis_*` values.

### Member or admin loads report choices

Add a report-specific resolver endpoint:

```http
GET /api/v1/groups/{group_id}/reports/available-sections
Authorization: Bearer <token>
```

Example response:

```json
{
  "data": {
    "group_id": "GROUP_ID",
    "group_type": "GOAL_SAVINGS",
    "viewer_role": "MEMBER",
    "sections": [
      {
        "key": "week_summary",
        "label": "Week summary",
        "description": "Totals, success rate, key highlights"
      },
      {
        "key": "members_who_saved",
        "label": "Members who saved",
        "description": "List of members who made savings"
      }
    ]
  }
}
```

For regular members, return only entries whose visibility is enabled. For admins, return the full applicable catalog. The backend should resolve the group type, evaluate the nine report-section rows, then evaluate the existing Member visibility settings that are report-eligible. Do not accept client-supplied visibility values as authority.

### Create the report

```http
POST /api/v1/groups/{group_id}/reports
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "included_sections": ["week_summary", "members_who_saved"],
  "period": {"type": "WEEK", "selected_date": "2026-11-02"}
}
```

Before reading report data, the backend must validate every `included_sections` key against the current user's available-section set. Reject unknown or disabled keys (for example with HTTP 403) and generate no report containing them. Recheck at creation time even if the UI previously fetched the allowed list; an admin may have changed visibility in between.

The server should return an immutable report snapshot with its included keys and resolved data. Persist it in a dedicated table such as `groupfinancialreport` (group, requester, date range, included-section keys, payload JSON, creation time, optional chat message ID), or explicitly define the chat-message attachment JSON as the canonical immutable snapshot. Do not store generated reports in `groupreport`.

## Backend Resolution Algorithm

1. Authenticate the user and confirm they can access the group.
2. Load group type and role.
3. Load `groupreportsectionvisibility` for the group.
4. Load the existing `groupvisibilitysettings` row and map its enabled `vis_*` columns to stable settings keys.
5. Build the group-type catalog of report sections and Member visibility settings.
6. For a member, keep only entries whose matching visibility is true. Missing rows/keys are false (fail closed). For an admin, return all applicable entries.
7. On POST, repeat steps 1-6 and reject any selected key not in the allowed set.
8. Fetch only data for allowed selected keys, applying the five existing `vis_report_*` field flags to the relevant report values.
9. Store the generated snapshot and return the report ID/payload.

The SQL may load the existing wide visibility row with a fixed, typed query. Avoid constructing SQL column names from request keys. For the normalized report-section table, use parameterized queries:

```sql
SELECT section_key, visible_to_members
FROM public.groupreportsectionvisibility
WHERE group_id = $1;
```

## Android Work Needed After the API Exists

- Add DTOs and Retrofit methods for `available-sections` and report creation.
- Replace local report-option visibility decisions with the server-returned catalog. Keep a loading state; hide gated options until the response succeeds. Show a clear retry/error state rather than defaulting to visible.
- Send stable keys, not labels, in `included_sections`.
- Replace the locally constructed sample `WeeklyReportData` in `ThreadAttachmentHandler.kt` with the report-creation response.
- Map returned report data into `WeeklyReportData` / `MicroBondWeeklyReportBubble`; the bubble currently renders only the known canonical categories.
- Keep an admin view that can configure all nine report visibility switches in Member visibility. Members should not get those controls.

## Acceptance Checks

- Admin can turn each of the nine report-section switches on/off per group.
- Member report setup omits every disabled section and includes each enabled applicable section.
- Additional Member visibility settings appear only when their existing visibility switches are on.
- Missing visibility rows/keys and visibility API failures never expose gated sections to members.
- A crafted POST containing a disabled key is rejected by the server.
- Changing group type changes the applicable catalog and data resolver.
- Report snapshot records exactly the allowed selected keys and data, so later settings changes do not alter an already-generated report.
