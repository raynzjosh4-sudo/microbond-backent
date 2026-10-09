# Microbond Data Structures & Models Outline

Based on the source code from the Android project, here is a structured breakdown of the app's data models. This outline maps the Kotlin data classes to conceptual entities for the FastAPI/SQLModel backend.

## 1. Core Enums (Database `ENUM` Types)
These enums dictate states and types across the system:

* **`MessageStatus`**: `PENDING`, `SENT`, `DELIVERED`, `READ`, `FAILED`
* **`MemberSaveStatus`**: `SAVED`, `MISSED`, `PENDING`
* **`SavingsGroupType`**: Defines the fundamental logic for a group:
  * `MERRY_GO_ROUND` (Rotating Savings)
  * `GOAL_SAVINGS` (Goal Savings)
  * `BILL_SPLIT` (Bill Split)
  * `WELFARE_FUND` (Welfare & Emergency)
  * `EVENT_COMMITTEE` (Event Committee)
  * `INVESTMENT_CLUB` (Investment Club)
  * `FUNDRAISER` (Public Fundraiser)
  * `SHARED_WALLET` (Shared Wallet)
  * `ASSOCIATION_DUES` (Membership Dues)
* **`ThreadBubbleType`**: Very extensive! Controls how messages are rendered (`TEXT`, `DEPOSIT`, `STAT_GROUP_PROGRESS`, `SECURITY_RULES`, `POLL`, etc.).

---

## 2. Core Entities

### Users & Members
* **`GroupMemberSummary`**
  * Represents a user in the context of a group.
  * Fields: `name`, `phoneNumber`, `role`, `trustScore`, `contributionStatus`.

### Groups & Settings
Groups are heavily customizable. A group record will likely need one-to-one relations with settings tables and a polymorphic "Purpose" table.
* **`GroupAdminSettings`**: Permissions (e.g., `membersCanEditInfo`, `requireMultiSignature`, `minimumTrustScore`).
* **`GroupPrivateSettings`**: User-specific settings per group (e.g., `muted`, `linkedPaymentMethod`, `autoPayEnabled`).

### Group Purpose Data (Polymorphic Models)
The backend will need specific tables or JSONB columns to store configuration based on the `SavingsGroupType`:
* **`RotatingRoscaGroupData`**: Fields for payout frequencies, strikes, penalties, next payout date.
* **`TargetSavingsGroupData`**: Goal amount, target date, progress, overage policy.
* **`EmergencyWelfareGroupData`**: Pool balance, active requests, max payouts.
* **`LendingInvestmentGroupData`**: Total capital, active loans, ROI%, interest rates.
* **`SharedBillUtilityGroupData`**: Connected utilities, average spend, member split percentages.

---

## 3. The Thread & Messaging System
The app uses a unified messaging thread to handle chat, transactions, and system updates.

* **`ThreadEvent`** (The central message model)
  * **Base Fields**: `id`, `text`, `time`, `isCurrentUser`, `status`, `type` (`ThreadBubbleType`).
  * **Sender Info**: `senderName`, `senderPhone`, `senderColor`, `senderAvatarRes`.
  * **Media/Quotes**: `quotedText`, `imageUris`, `voiceUri`.

### Embedded Message Payloads (Rich Bubbles)
Depending on the `ThreadBubbleType`, a `ThreadEvent` carries optional nested objects. In a SQL database, these can be stored as JSONB columns or in associated payload tables:
* **Deposit / Transaction Data**: `amount`, `paymentMethod`, `referenceId`, `isVerified`, `receiptUrl`.
* **Statistics & Reports**: 
  * `WeeklyReportData` (Detailed breakdown of members saved, missed, balances).
  * Chart Datas: `StatGroupProgressData`, `StatHistogramData`, `GroupHealthData`.
* **Group Management**:
  * `SecurityRulesData` & `SecurityRuleUpdateData`.
  * `SecurityPollData` (Group voting).

---

## Backend Implementation Recommendations

1. **Database Design (SQLModel / PostgreSQL):**
   * Use **JSONB columns** in your `ThreadEvent` table for the rich embedded data (like `weeklyReport`, `statGroupProgress`, `pollData`). Setting up separate tables for every single chart type would overcomplicate the database.
   * Use a **Polymorphic relationship** or separate tables linked by a `group_id` for the `GroupPurposeData` since they have vastly different fields and business logic.
2. **API Design (FastAPI):**
   * Since `ThreadEvent` is massive, you can use **Pydantic Unions** and discriminated unions in FastAPI to accept/return the correct payload based on the `ThreadBubbleType`.
