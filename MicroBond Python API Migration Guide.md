# MicroBond Python API Migration Guide

## Purpose

This guide explains how to update the existing Python API that was built against the original working schema so it can safely use the newer database design.

The actual Python source code was not attached, so this document does not invent your current module names. Instead, it gives the exact responsibilities, table mappings, transaction boundaries, request/response contracts, and implementation order. Map each section to the existing router/service/repository files in your project.

The most important rule is:

> Do not update every endpoint independently. First create shared database, authorization, idempotency, money, audit, and transaction helpers. Then migrate each business feature to those helpers.

---

## 1. What changed from the original working schema

The original API was primarily built around legacy tables such as:

```text
user
group
groupmembership
invite
memberobligation
rotatinggroupdetails
groupwallet
grouppayout
guarantorpledge
ledgerentry
```

The newer design adds or expands:

```text
rotating_cycle
rotating_daily_collection
rotating_payout
rotating_payout_recipient
rotating_reserve_entry
rotating_turn_swap
group_role_grant
group_permission_grant
permission_catalog
payment_webhook_event
backend_job_execution
command_idempotency
audit_event
payoutsignature
rotatingcyclereport
```

It also adds more configuration tables:

```text
groupcommunicationsettings
groupfinancialsettings
groupgovernancesettings
groupvisibilitysettings
groupcommonsettings
targetsavingsgroupdetails
fundraisercampaignconfig
sharedwalletconfig
welfarefundconfig
eventcommitteeconfig
investmentclubconfig
associationduesconfig
billsplitconfig
```

The API must therefore stop treating one large legacy table as the complete source of truth for every operation.

---

## 2. First decisions that must be made before coding

### 2.1 Choose the canonical group identifier

The schema currently has two group identifiers:

```text
group.id        integer primary key
group.group_id  text unique public identifier
```

Most newer tables use the text identifier. `invite.group_id` still uses the integer identifier while `invite.group_public_id` uses the text identifier.

Use this migration rule:

```text
External API URLs: group.group_id
Request payloads: group.group_id
New service methods: group.group_id
New foreign keys: group.group_id where the schema supports it
Internal legacy translation: only at the repository boundary
```

Do not allow each router to decide independently whether `group_id` means integer or text.

Create one helper:

```python
def get_group_by_public_id(session, public_group_id: str) -> Group:
    ...
```

During the compatibility period, invitation code may translate `invite.group_id` to `invite.group_public_id`, but all new code should use `group_public_id`.

### 2.2 Choose the source of truth for rotating groups

The new rotating tables should become the source of truth for new cycles:

```text
rotatinggroupdetails       = current group rules/settings
rotating_cycle             = one cycle
rotating_daily_collection  = one member's obligation for one collection date
rotating_payout            = one cycle payout decision
rotating_payout_recipient  = each recipient in that payout
rotating_reserve_entry     = reserve movement
```

The legacy tables remain for compatibility:

```text
memberobligation
grouppayout
groupwallet
```

Do not silently write both old and new tables from every endpoint. Choose one of these strategies:

1. **Recommended:** new cycles use the new rotating tables; legacy rows are read only or maintained by one compatibility adapter.
2. **Temporary compatibility:** a single transaction writes both old and new records through one service, never through separate routers.
3. **Full migration:** migrate old rows, change all readers, then remove legacy writes.

Never let the API create a new payout in `grouppayout` in one code path and `rotating_payout` in another.

### 2.3 Choose the source of truth for roles

The newer role system is:

```text
group_role_grant
group_permission_grant
permission_catalog
```

Treat `group_role_grant` and `group_permission_grant` as the authority for new authorization checks. Keep `groupmembership.role` only as a legacy display/compatibility field until it is removed.

Create one authorization service instead of checking `membership.role` in every endpoint:

```python
require_permission(
    actor_user_id=actor_id,
    group_id=group_public_id,
    permission="APPROVE_PAYOUT",
)
```

### 2.4 Choose the source of truth for balances

The accounting source of truth must be `ledgerentry` plus reserve/payout records. Fields such as:

```text
group.total_balance
groupwallet.pooled_funds
groupwallet.reserve_funds
```

are projections or caches. They must not be independently changed by ordinary API endpoints.

---

## 3. Required shared API foundation

Build these helpers before migrating feature endpoints.

### 3.1 Transaction helper

Every state-changing operation needs one database transaction.

```python
@contextmanager
def transaction(session: Session):
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
```

For critical operations, use row locks:

```python
statement = (
    select(RotatingCycle)
    .where(RotatingCycle.id == cycle_id)
    .with_for_update()
)
cycle = session.exec(statement).one()
```

Use row locks for:

```text
invite acceptance
cycle opening/closing
collection payment recording
payout creation
payout approval
payout disbursement
webhook processing
turn swap application
role grant changes
```

### 3.2 Idempotency helper

Every client mutation should accept:

```text
client_request_id: string
```

Use `command_idempotency`:

```python
def begin_command(session, user_id, client_request_id):
    existing = session.exec(
        select(CommandIdempotency).where(
            CommandIdempotency.user_id == user_id,
            CommandIdempotency.client_request_id == client_request_id,
        )
    ).first()

    if existing:
        return ExistingCommand(existing)

    command = CommandIdempotency(
        id=uuid4(),
        user_id=user_id,
        client_request_id=client_request_id,
        status="RUNNING",
        created_at=now_ms(),
    )
    session.add(command)
    session.flush()
    return NewCommand(command)
```

If the unique constraint reports a duplicate because two requests raced, reload the existing command and return its stored response.

Store the final response in:

```text
response_code
response_json
status
```

Use idempotency for:

```text
invite creation
invite acceptance
joining request submission
member votes
role grants
payments
collection recording
cycle close
payout creation
payout approval
payout disbursement
turn swaps
```

### 3.3 Authorization helper

Implement permission evaluation in one place:

```python
def has_permission(session, actor_id, group_id, permission_code) -> bool:
    # 1. actor must have an active membership
    # 2. role or explicit permission grant must be active
    # 3. grant must not be expired
    # 4. group must match
    ...
```

Check:

```text
status = ACTIVE
expires_at is null OR expires_at > now
```

For a role, expand the role into permissions through a static permission map or database catalog.

Do not authorize using a client-supplied role, `is_admin` flag, or old `groupmembership.role` alone.

### 3.4 Audit helper

Every sensitive action writes an `audit_event` in the same transaction:

```python
record_audit(
    session=session,
    actor_user_id=actor_id,
    action="PAYOUT_APPROVED",
    entity_type="rotating_payout",
    entity_id=str(payout.id),
    tenant_group_id=group_id,
    request_id=request_id,
    payload={"status": "APPROVED"},
)
```

Never put OTP text, PINs, NINs, document numbers, account numbers, or access tokens in `payload_json`.

Audit actions should include:

```text
INVITE_CREATED
INVITE_ACCEPTED
INVITE_CANCELLED
JOIN_REQUEST_SUBMITTED
GUARANTOR_REQUESTED
GUARANTOR_ACCEPTED
MEMBER_VOTED
MEMBER_APPROVED
MEMBER_REJECTED
ROLE_GRANTED
ROLE_REVOKED
COLLECTION_RECORDED
CYCLE_OPENED
CYCLE_CLOSED
PAYOUT_CREATED
PAYOUT_APPROVED
PAYOUT_DISBURSED
RESERVE_HELD
RESERVE_RELEASED
TURN_SWAP_APPLIED
WEBHOOK_ACCEPTED
WEBHOOK_DUPLICATE
```

### 3.5 Money helper

Do not calculate money with Python `float`.

Use:

```python
from decimal import Decimal, ROUND_HALF_UP
```

or integer minor units consistently.

Every financial service should use a money type and return:

```text
amount
currency
```

Do not accept a client-calculated `net_payout_amount` as authoritative. Calculate it in the service.

### 3.6 Time helper

The schema mixes timestamps, bigint values, dates, and times. Establish one convention in the API:

```text
Instant: timezone-aware datetime / timestamptz
Local date: date
Daily time: time plus IANA timezone
```

For rotating groups, always use:

```text
timezone_name
collection_start_time
collection_end_time
```

Never compare a Kampala local time to a UTC timestamp without converting it first.

---

## 4. Authentication and OTP migration

The OTP model must use:

```text
phone_number
code_hash
is_used
created_at
expires_at
```

The API must not insert `code`.

Flow:

```text
Generate OTP in Python
→ hash with server pepper
→ store code_hash
→ send plaintext OTP through SMS provider
→ receive submitted OTP
→ hash submitted value
→ query unused and unexpired record
→ mark is_used in a transaction
```

Do not return the OTP or its hash. Do not log it.

The same pattern applies to:

```text
usersecurityemail.verification_token_hash
guarantorpledge.pledge_token_hash
invite.invite_token_hash
```

If the live database still contains `otprecord.code`, deploy the API hash change first, then remove the column.

---

## 5. Invite and joining-request API

The current schema has an `invite` table but no fully separate joining-request table. If the product needs a multi-step process, add a dedicated table such as:

```text
membership_join_request
```

Recommended fields:

```text
id uuid primary key
invite_id integer not null
user_id uuid
public_status text not null
phone_verified_at timestamptz
kyc_submitted_at timestamptz
guarantor_status text
voting_status text
admin_status text
submitted_at timestamptz
approved_at timestamptz
rejected_at timestamptz
cancelled_at timestamptz
created_at timestamptz
updated_at timestamptz
```

If you do not add this table, the API will be forced to overload `invite.status`, which makes the workflow difficult to audit.

### 5.1 Create invitation

Endpoint shape:

```text
POST /groups/{group_id}/invitations
```

Request:

```json
{
  "invitee_phone": "+2567...",
  "requires_admin_approval": true,
  "requires_member_vote": true,
  "required_votes": 5,
  "requires_guarantor": true,
  "expires_in_hours": 48,
  "client_request_id": "..."
}
```

Transaction:

1. Resolve canonical group by text `group_id`.
2. Require `INVITE_MEMBERS` permission.
3. Validate group is open and not at capacity.
4. Normalize the invitee phone.
5. Check for an existing active invite for the same group and phone.
6. Generate a random raw invite token.
7. Store only `invite_token_hash`.
8. Store `group_public_id`.
9. Set `status = SENT` and expiry.
10. Write audit event.
11. Commit.
12. Send SMS after commit or enqueue an outbox job.

Response:

```json
{
  "invite_id": 123,
  "status": "SENT",
  "expires_at": "2026-11-15T12:00:00Z"
}
```

The raw token may be returned once for link sharing, but never store it in the database or logs.

### 5.2 Open invitation

Endpoint:

```text
GET /invitations/{raw_token}
```

The API hashes the token and loads the invite. Return only safe group information:

```json
{
  "group_id": "FKR-THE-MAZE",
  "group_name": "FKR THE MAZE",
  "daily_contribution": "10000.00",
  "currency": "UGX",
  "requires_guarantor": true,
  "requires_admin_approval": true,
  "required_votes": 5,
  "expires_at": "..."
}
```

Do not return inviter phone, invitee phone, token hash, private KYC, account details, or internal IDs unnecessarily.

### 5.3 Accept invitation

Endpoint:

```text
POST /invitations/{raw_token}/accept
```

Transaction with invite row lock:

1. Hash the raw token.
2. Lock the invite.
3. Check status, expiry, revocation, and uses.
4. Resolve or create the authenticated user.
5. Create a joining request or update the invite state.
6. Increment `uses_count` exactly once.
7. Set `accepted_at`.
8. Write audit event.
9. Commit.

Do not create `groupmembership` yet.

### 5.4 Submit joining request

Endpoint:

```text
POST /groups/{group_id}/join-requests
```

The service verifies:

```text
invite accepted
phone verified
required profile fields complete
KYC requirement complete
required guarantor accepted
```

Then it sets the request to a review state. It does not create active membership until every condition passes.

### 5.5 Final approval

Only one service should activate membership:

```text
approve_join_request()
```

Transaction:

1. Lock the joining request.
2. Check all requirements.
3. Check member capacity.
4. Check the user is not already an active member.
5. Create `groupmembership` with `status = ACTIVE`.
6. Assign role through the role-grant system.
7. Assign payout position if the rotating rules require it.
8. Create first-cycle obligations only if the cycle is open and the product rules require it.
9. Update request and invite status.
10. Write audit events.
11. Commit.

If any step fails, none of the membership changes should remain.

---

## 6. Guarantor API

Use `guarantorpledge` for the guarantor relationship.

### Request guarantor

```text
POST /join-requests/{request_id}/guarantor
```

Checks:

```text
request belongs to authenticated applicant
selected guarantor is an active member of the same group
guarantor is not the applicant
guarantor meets minimum KYC/trust requirement
no active conflicting pledge exists
```

Create a pledge with:

```text
status = PENDING
borrower_user_id = applicant
 guarantor_user_id = selected member
group_id = canonical group ID
```

### Accept or decline

```text
POST /guarantor-pledges/{pledge_id}/accept
POST /guarantor-pledges/{pledge_id}/decline
```

The API must verify that the authenticated user is the guarantor, not merely a group member.

Every transition should be locked and audited.

---

## 7. Member voting API

The current schema has `grouppoll` and `grouppollvote`, but joining approval needs a stable target. Add or use a specific poll/request reference.

Recommended request:

```text
POST /join-requests/{request_id}/vote
```

Transaction:

1. Verify the voter is an eligible active member.
2. Verify voting is enabled for the group.
3. Verify the request is still in voting.
4. Verify the voter has not already voted.
5. Insert one vote.
6. Recalculate the approval count.
7. Move the request to the next state if quorum is reached.
8. Write audit event.

The database must enforce one vote per request/member with a unique key:

```text
(join_request_id, voter_user_id)
```

Do not expose private voter identities by default.

---

## 8. Rotating group API migration

### 8.1 Create rotating group settings

Create or update `rotatinggroupdetails` through a settings service.

Validate:

```text
contribution_amount > 0
cycle_length_days between 1 and 366
recipients_per_cycle >= 1
reserve_percentage between 0 and 100
collection_start_time < collection_end_time
collection_frequency_days > 0
```

Store:

```text
currency_code
timezone_name
collection_start_time
collection_end_time
cycle_length_days
recipients_per_cycle
reserve_percentage
payout_requires_full_collection
```

Do not let clients directly update current cycle state fields such as `current_cycle` or payout readiness.

### 8.2 Create a cycle

Endpoint:

```text
POST /groups/{group_id}/rotating/cycles
```

Transaction:

1. Require `EDIT_SETTINGS` or a dedicated cycle permission.
2. Lock the group rotating settings.
3. Calculate start/end timestamps using the group timezone.
4. Determine the next cycle number.
5. Insert one `rotating_cycle`.
6. Snapshot relevant settings into the cycle if you need historical reproducibility.
7. Create one daily collection row per active eligible member per collection date, or create them just-in-time through one idempotent service.
8. Write audit event.
9. Commit.

Never trust the client to provide `expected_pool_amount` without recalculating it.

For 20 members contributing UGX 10,000 daily for 30 days:

```text
expected pool = 20 × 10,000 × 30
              = UGX 6,000,000
```

### 8.3 Record a daily collection

Endpoint:

```text
POST /cycles/{cycle_id}/collections/{collection_id}/pay
```

Transaction:

1. Lock the collection row.
2. Verify the payer and group membership.
3. Verify the collection window or allowed late-payment rule.
4. Verify the payment reference is idempotent.
5. Update `amount_paid` without exceeding `amount_due`.
6. Set status to `PAID`, `PARTIALLY_PAID`, or `LATE`.
7. Insert a `ledgerentry`.
8. Update a projection only if the ledger write succeeds.
9. Audit.
10. Commit.

Do not update the wallet first and create the ledger later.

### 8.4 Close a cycle

Endpoint:

```text
POST /cycles/{cycle_id}/close
```

Transaction with cycle lock:

1. Verify the cycle is open.
2. Recalculate collections from `rotating_daily_collection`.
3. Mark unpaid rows late/defaulted according to rules.
4. Calculate reserve amount.
5. Calculate available payout amount.
6. Set cycle status to `CLOSED` or `READY_FOR_REVIEW`.
7. Write audit event.
8. Commit.

The API must reject a second close request through idempotency and the cycle status check.

### 8.5 Create a payout

Endpoint:

```text
POST /cycles/{cycle_id}/payout
```

Transaction:

1. Lock the cycle.
2. Verify collection completion rules.
3. Calculate gross pool.
4. Calculate reserve.
5. Calculate net payout.
6. Determine recipients according to the locked payout order.
7. Insert one `rotating_payout`.
8. Insert one `rotating_payout_recipient` row per recipient.
9. Insert reserve entry if required.
10. Set approval status.
11. Audit.
12. Commit.

For two equal recipients and no reserve:

```text
gross_pool_amount = 6,000,000
reserve_amount = 0
net_payout_amount = 6,000,000
recipient_count = 2
amount_per_recipient = 3,000,000
```

The API must calculate this; the client should only request the action.

### 8.6 Approve and sign a payout

Use:

```text
rotating_payout
payoutsignature
```

Endpoints:

```text
POST /payouts/{payout_id}/approve
POST /payouts/{payout_id}/sign
```

Checks:

```text
actor has APPROVE_PAYOUT or SIGN_PAYOUT
actor is active in the group
actor has not already signed the same payout
payout is in an approvable state
approval count is below the required count
```

Do not treat `pin_verified = true` as proof by itself. It must be set only after the API verifies the current user’s PIN through the secure authentication service.

### 8.7 Disburse a payout

Disbursement must be a worker-safe state machine:

```text
APPROVED
→ DISBURSING
→ DISBURSED
```

On provider failure:

```text
DISBURSING
→ FAILED
```

Use an idempotency key based on payout recipient and provider operation. Never send money twice because a worker timed out after the provider accepted the first request.

---

## 9. Reserve and early-turn handling

Use `rotating_reserve_entry` for actual reserve movements.

Do not treat `reserve_amount` on `rotating_cycle` as the only accounting record. It is a summary; the reserve entry is the movement record.

Endpoints:

```text
POST /cycles/{cycle_id}/reserve/hold
POST /cycles/{cycle_id}/reserve/release
POST /cycles/{cycle_id}/reserve/refund
```

Every reserve movement must create a ledger entry or be traceable to one.

---

## 10. Turn swap API

Use `rotating_turn_swap`.

Endpoints:

```text
POST /groups/{group_id}/turn-swaps
POST /turn-swaps/{id}/approve
POST /turn-swaps/{id}/reject
POST /turn-swaps/{id}/apply
POST /turn-swaps/{id}/cancel
```

Checks:

```text
requester and target are different users
both are active members of the same group
cycle numbers are valid
swap is not already active/applied
payout order is not locked past the allowed point
both required parties approved
```

Applying a swap must lock the relevant membership or roster rows and update the payout order atomically.

---

## 11. Payment webhook API

Endpoint:

```text
POST /webhooks/{provider}
```

Process the webhook in this order:

1. Verify provider signature in Python.
2. Read provider event ID.
3. Start a transaction.
4. Insert `payment_webhook_event` with `(provider_name, provider_event_id)`.
5. If it already exists, return the stored result without applying the payment again.
6. Validate payload hash.
7. Apply the payment state transition through one service.
8. Set webhook status to `PROCESSED`.
9. Commit.
10. Return success.

Never apply a payment update before inserting the deduplication record.

---

## 12. Role and permission API

Endpoints:

```text
POST /groups/{group_id}/roles
DELETE /groups/{group_id}/roles/{grant_id}
POST /groups/{group_id}/permissions
DELETE /groups/{group_id}/permissions/{grant_id}
GET /groups/{group_id}/permissions/me
```

For granting a role:

1. Require `MANAGE_ROLES`.
2. Verify target user is an active member of the group.
3. Verify the requested role is allowed.
4. Insert `group_role_grant`.
5. Prevent duplicate active grants.
6. Write audit event.

For revoking:

1. Lock the grant.
2. Require authorization.
3. Set `status = REVOKED`, `revoked_at`, and `revoked_by_user_id`.
4. Do not delete the historical grant.
5. Audit.

---

## 13. Chat, notification, and report API changes

### Chat

Use `groupchatmessage.sender_user_id` as the future canonical sender reference. Keep legacy `sender_id` only during migration.

Every message endpoint must verify:

```text
sender is an active group member
message group matches the sender's membership
reply target belongs to the same group
```

### Notifications

A notification must not reveal private KYC, account, or voting details. `notification.group_id` should reference the group if the live database supports it.

Use `dedupe_key` to avoid sending the same approval or payment notification repeatedly.

### Reports

Reports should be generated from authorized queries, not from client-supplied row IDs. Check the requester’s group permission before exposing:

```text
ledger
balances
member arrears
payout details
KYC status
```

---

## 14. Product-specific modules

The new schema contains several product types. Do not implement them all as variations of the rotating-group endpoint.

Create separate service modules with a shared financial/authorization foundation:

```text
services/rotating_groups.py
services/target_savings.py
services/fundraisers.py
services/shared_wallets.py
services/welfare_funds.py
services/event_committees.py
services/investment_clubs.py
services/association_dues.py
services/bill_split.py
services/loans.py
```

Each module should have:

```text
settings read/update
membership eligibility
contribution/obligation creation
payment recording
approval/voting
payout/disbursement
ledger integration
notifications
reports
```

Do not allow one module to update another module’s settings tables directly.

---

## 15. Repository/model changes

Update the SQLModel/ORM layer to include the new tables and columns:

```text
RotatingCycle
RotatingDailyCollection
RotatingPayout
RotatingPayoutRecipient
RotatingReserveEntry
RotatingTurnSwap
GroupRoleGrant
GroupPermissionGrant
PermissionCatalog
PaymentWebhookEvent
BackendJobExecution
CommandIdempotency
AuditEvent
PayoutSignature
```

Use relationships carefully. Avoid loading sensitive columns by default in general user queries.

Create explicit projection models such as:

```python
class SafeKycSummary(BaseModel):
    current_tier: str
    overall_status: str
    nin_last4: str | None
    document_id_last4: str | None

class SafePayoutDestination(BaseModel):
    provider_name: str
    account_type: str
    account_name: str | None
    account_last4: str | None
    is_verified: bool
```

Do not return ORM objects directly from endpoints.

---

## 16. API state machines

Do not let routers assign arbitrary status strings. Define transition functions.

### Invitation

```text
SENT → OPENED → ACCEPTED
SENT → EXPIRED
SENT → REVOKED
OPENED → DECLINED
```

### Joining request

```text
DRAFT
→ PHONE_VERIFIED
→ KYC_SUBMITTED
→ GUARANTOR_PENDING
→ GUARANTOR_ACCEPTED
→ VOTING
→ ADMIN_REVIEW
→ APPROVED
```

Failure paths:

```text
DRAFT → CANCELLED
VOTING → REJECTED
ADMIN_REVIEW → REJECTED
GUARANTOR_PENDING → CANCELLED
```

### Cycle

```text
PLANNED → OPEN → CLOSED → COMPLETED
PLANNED → CANCELLED
OPEN → ON_HOLD
```

### Payout

```text
PENDING
→ READY_FOR_REVIEW
→ APPROVAL_REQUIRED
→ APPROVED
→ DISBURSING
→ DISBURSED
```

Failure paths:

```text
PENDING → CANCELLED
DISBURSING → FAILED
APPROVED → ON_HOLD
```

Create a single transition method per stateful entity and reject invalid transitions.

---

## 17. Testing plan before switching production behavior

### Schema and repository tests

- Every new table can be inserted and read through the ORM.
- Every foreign key uses the expected type.
- Group public IDs resolve correctly.
- Sensitive fields are excluded from public response models.

### Invitation tests

- Duplicate active invite is rejected.
- Expired invite cannot be accepted.
- Cancelled invite cannot be accepted.
- Invite acceptance is safe under two simultaneous requests.
- Accepted invite cannot create two memberships.

### Guarantor tests

- Non-member cannot be selected as guarantor.
- Applicant cannot guarantee themselves.
- Guarantor can accept only their own request.
- Replacing a pending guarantor does not leave two active pledges.

### Voting tests

- Ineligible member cannot vote.
- Same member cannot vote twice.
- Vote count reaches quorum exactly once.
- Private voter identity is not returned.

### Rotating-cycle tests

- A group cannot have duplicate cycle numbers.
- A member cannot have duplicate collection rows for one date.
- Amount paid cannot exceed amount due.
- Cycle close is idempotent.
- Payout creation is idempotent.
- Recipient belongs to the payout’s group.
- Destination belongs to the recipient.
- Reserve is not counted twice.

### Payment tests

- Same webhook event is processed once.
- Same client request returns the original response.
- Provider timeout does not cause double disbursement.
- Failed disbursement can be retried safely.

### Authorization tests

- Member cannot manage roles.
- Member cannot approve a payout unless granted permission.
- User cannot read another group’s ledger.
- User cannot read another user’s KYC or account number.
- Service-only tables are inaccessible through direct client roles.

---

## 18. Recommended implementation order

### Phase 1 — compatibility foundation

1. Update ORM models for new columns and tables.
2. Choose canonical group ID handling.
3. Add timezone and money helpers.
4. Add transaction helper.
5. Add idempotency helper.
6. Add authorization helper.
7. Add audit helper.
8. Update OTP to `code_hash`.

### Phase 2 — identity and joining

1. Update invite creation.
2. Update invite link lookup.
3. Add accept-invite transaction.
4. Add joining-request state model.
5. Add guarantor workflow.
6. Add voting workflow.
7. Add admin approval.
8. Create active membership only after final approval.

### Phase 3 — rotating groups

1. Update rotating settings endpoint.
2. Add cycle creation.
3. Add daily collection generation.
4. Add collection payment recording.
5. Add cycle close.
6. Add payout creation.
7. Add reserve entries.
8. Add approval/signature flow.
9. Add disbursement worker.
10. Add turn swaps.

### Phase 4 — payment and operations

1. Add webhook deduplication.
2. Add backend job claiming and leases.
3. Add ledger reconciliation.
4. Add reports.
5. Add notifications and dedupe keys.

### Phase 5 — remaining product modules

Migrate target savings, fundraisers, shared wallets, welfare funds, event committees, investment clubs, association dues, bill split, and loans one module at a time using the same foundation.

---

## 19. What must not be done

Do not:

- Send `code_hash`, OTP text, PIN hash, NIN, full document number, or full account number to clients.
- Use `SELECT *` in public API endpoints.
- Trust client-supplied roles, balances, approval counts, or payout amounts.
- Write both legacy and new financial tables from unrelated endpoints.
- Mark a user active before final joining approval.
- Accept a guarantor who is not an active member of the same group.
- Allow a member to vote twice.
- Process a webhook before deduplicating it.
- Disburse a payout without an idempotency key.
- Update the wallet without a ledger entry.
- Use Python floats for money.
- Mix milliseconds and seconds without a documented conversion helper.
- Use the old `groupmembership.role` as the only authorization check after role grants are enabled.

---

## 20. Minimum files to add or update in the Python API

Your exact names may differ, but the project needs equivalents of:

```text
app/models/auth/otp.py
app/models/groups/invite.py
app/models/groups/join_request.py
app/models/groups/membership.py
app/models/groups/role_grant.py
app/models/groups/permission_grant.py
app/models/rotating/cycle.py
app/models/rotating/collection.py
app/models/rotating/payout.py
app/models/rotating/reserve.py
app/models/rotating/turn_swap.py
app/models/payments/webhook_event.py
app/models/jobs/backend_job.py
app/models/audit/audit_event.py
app/services/idempotency.py
app/services/authorization.py
app/services/audit.py
app/services/invitations.py
app/services/join_requests.py
app/services/guarantors.py
app/services/member_voting.py
app/services/rotating_groups.py
app/services/payouts.py
app/services/webhooks.py
app/services/ledger.py
app/utils/money.py
app/utils/time.py
app/api/invitations.py
app/api/join_requests.py
app/api/rotating_groups.py
app/api/payouts.py
app/api/webhooks.py
```

The most important architectural change is that routers should become thin. Business rules belong in services, and all writes should pass through transaction-aware services.

---

## Final migration principle

The new database contains more tables because the product now has more explicit states:

```text
invitation
joining request
active membership
cycle
collection
ledger entry
payout
recipient
reserve
approval
signature
job
webhook
role grant
permission grant
```

The Python API must reflect those states instead of pretending that one row or one status field represents the whole process.

Implement the foundation first, then migrate invitations and joining, then rotating cycles and payouts, then the remaining financial modules. That order keeps the existing working API understandable while gradually moving it to the new design.
