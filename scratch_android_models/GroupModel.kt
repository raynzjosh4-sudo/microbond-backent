package com.microbond.app.models.groupmodel

import androidx.compose.ui.graphics.Color
import com.microbond.app.core.data_classes_and_enums.GroupAdminSettings
import com.microbond.app.core.data_classes_and_enums.GroupPrivateSettings
import com.microbond.app.core.data_classes_and_enums.GroupPurposeData
import com.microbond.app.core.data_classes_and_enums.GroupSavingsType
import com.microbond.app.core.data_classes_and_enums.MemberSaveStatus
import com.microbond.app.core.data_classes_and_enums.MessageStatus
import com.microbond.app.core.data_classes_and_enums.SavingsGroupType
import com.microbond.app.feature_settings.subgroupsettingsscreens.access.GroupMemberRole
import java.util.UUID

/**
 * Represents a savings / welfare / bill-split group on the Microbond platform.
 *
 * Holds only data that is shared by every member of the group. Anything that is
 * specific to one user (role, personal settings, unread count, favourite flag…)
 * lives in [GroupMembershipModel], mirroring how [com.microbond.app.models.usermodel.User]
 * keeps group-specific details out of the global user record.
 */
data class GroupModel(
    val groupId: String = UUID.randomUUID().toString(),
    val name: String,
    val description: String = "",
    val groupImageUrl: String,                      // Required: cloud URL / local URI for the group image
    val avatarColor: Color = Color.Gray,            // Placeholder tint while the image loads

    // Classification
    val type: SavingsGroupType,                     // Merry-Go-Round, Goal Savings, Bill Split…
    val paymentMode: GroupPaymentMode = GroupPaymentMode.defaultFor(type),
    val savingsTerm: GroupSavingsType = GroupSavingsType.LONG_TERM,
    val visibility: GroupVisibility = GroupVisibility.PRIVATE,
    val status: GroupStatus = GroupStatus.ACTIVE,

    // Financials
    val currency: String = "UGX",
    val totalBalance: Long = 0L,                    // Current pooled balance (minor units not applied)

    // Type-specific rules & state (e.g. TargetSavingsGroupData, RotatingRoscaGroupData)
    val purposeData: GroupPurposeData,

    // Group-wide permissions controlled by admins
    val adminSettings: GroupAdminSettings = GroupAdminSettings(),

    // Membership
    val memberCount: Int = 0,                       // Full roster size (members list may be partial)
    val maxMembers: Int? = null,
    val createdByUserId: String,
    val inviteCode: String? = null,                 // Shareable join code / deep-link token

    // Shared content stats
    val sharedMediaCount: Int = 0,
    val sharedLedgerEntryCount: Int = 0,

    // Chat-list preview
    val lastActivity: GroupLastActivity? = null,

    // Audit
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis()
) {
    val initials: String
        get() = name.trim().take(1).uppercase()

    val isPublic: Boolean
        get() = visibility == GroupVisibility.PUBLIC
}

/**
 * Join table between a [com.microbond.app.models.usermodel.User] and a [GroupModel].
 * Stores everything about a user that only makes sense inside one group.
 */
data class GroupMembershipModel(
    val membershipId: String = UUID.randomUUID().toString(),
    val groupId: String,
    val userId: String,

    // Role & standing
    val role: GroupMemberRole = GroupMemberRole.MEMBER,
    val title: String? = null,                      // Free-text office e.g. "Treasurer", "Secretary"
    val status: MembershipStatus = MembershipStatus.ACTIVE,
    val groupTrustScore: Int? = null,               // Trust score within this group only

    // Money in
    // OBLIGATION groups: the amount assigned to this member that they MUST pay.
    // VOLUNTARY groups: null — the member brings whatever they want, whenever they want.
    val obligation: MemberObligation? = null,
    val totalContributed: Long = 0L,                // Everything this member has paid in (required + extra)

    // Viewer-private settings (mute, auto-pay, linked payment method…)
    val privateSettings: GroupPrivateSettings = GroupPrivateSettings(),

    // Chat-list state for this user
    val isFavorite: Boolean = false,
    val unreadCount: Int = 0,

    // Lifecycle
    val invitedByUserId: String? = null,
    val joinedAt: Long = System.currentTimeMillis(),
    val leftAt: Long? = null
) {
    val isAdmin: Boolean
        get() = role.isAdmin

    /**
     * Status for the member status ring in the UI. Voluntary members can never "miss",
     * they are either SAVED (have brought something) or PENDING (nothing yet).
     */
    val ringStatus: MemberSaveStatus
        get() = when (obligation?.status) {
            null -> if (totalContributed > 0) MemberSaveStatus.SAVED else MemberSaveStatus.PENDING
            ObligationStatus.PAID, ObligationStatus.WAIVED -> MemberSaveStatus.SAVED
            ObligationStatus.OVERDUE -> MemberSaveStatus.MISSED
            ObligationStatus.DUE, ObligationStatus.PARTIALLY_PAID -> MemberSaveStatus.PENDING
        }
}

/**
 * A fixed amount dedicated to one member that they are required to pay for one
 * cycle (ROSCA slot, dues, bill share, pledge they committed to…).
 *
 * Stored as its own record (one per member per cycle) so arrears history is kept;
 * [GroupMembershipModel.obligation] holds the current one. Deposits link to it via
 * [GroupTransactionModel.obligationId].
 */
data class MemberObligation(
    val obligationId: String = UUID.randomUUID().toString(),
    val groupId: String,
    val userId: String,
    val cycleId: String? = null,                    // GroupCycleModel this belongs to (null for one-off pledges)
    val requiredAmount: Long,                       // What this member must bring this cycle
    val paidAmount: Long = 0L,                      // Sum of linked completed transactions
    val dueDate: Long,
    val source: ObligationSource,
    val status: ObligationStatus = ObligationStatus.DUE,
    val waivedByUserId: String? = null,
    val createdAt: Long = System.currentTimeMillis()
) {
    val outstandingAmount: Long
        get() = (requiredAmount - paidAmount).coerceAtLeast(0L)
}

/** How money comes into a group. */
enum class GroupPaymentMode {
    OBLIGATION,     // Every member has a set amount they must pay (late fees / arrears apply)
    VOLUNTARY,      // Members bring what they want, when they want; nothing is ever "missed"
    MIXED;          // A required minimum, plus optional extra contributions on top

    companion object {
        fun defaultFor(type: SavingsGroupType): GroupPaymentMode = when (type) {
            SavingsGroupType.MERRY_GO_ROUND,
            SavingsGroupType.BILL_SPLIT,
            SavingsGroupType.WELFARE_FUND,
            SavingsGroupType.ASSOCIATION_DUES,
            SavingsGroupType.EVENT_COMMITTEE -> OBLIGATION

            SavingsGroupType.FUNDRAISER,
            SavingsGroupType.SHARED_WALLET -> VOLUNTARY

            SavingsGroupType.GOAL_SAVINGS,
            SavingsGroupType.INVESTMENT_CLUB -> MIXED
        }
    }
}

/** Where a member's required amount comes from. */
enum class ObligationSource {
    FIXED_CYCLE_AMOUNT,     // Same amount for everyone each round (Merry-Go-Round)
    MEMBERSHIP_DUES,        // Periodic dues (Association / Welfare)
    ASSIGNED_SHARE,         // Member's split of a bill
    PLEDGE,                 // Member committed to an amount, now must pay it (Event)
    MINIMUM_SHARES          // Minimum share purchase (Investment club / Goal savings)
}

enum class ObligationStatus {
    DUE,                // Not yet paid, still within the deadline
    PARTIALLY_PAID,
    PAID,
    OVERDUE,            // Deadline passed — arrears / late-fee policy applies
    WAIVED              // Exempted by admins (fee exemption / hardship)
}

/** Latest message / event shown in the chats list for a group. */
data class GroupLastActivity(
    val preview: String,                            // e.g. "Monthly contribution approved"
    val senderUserId: String? = null,
    val timestamp: Long = System.currentTimeMillis(),
    val isOutgoing: Boolean = false,
    val messageStatus: MessageStatus = MessageStatus.DELIVERED
)

enum class GroupVisibility {
    PRIVATE,        // Invite / approval only
    PUBLIC          // Discoverable, anyone can request to join
}

enum class GroupStatus {
    ACTIVE,         // Running normally
    PAUSED,         // Contributions temporarily frozen by admins
    CLOSED,         // Cycle/goal completed, read-only
    ARCHIVED,       // Hidden from main list, history retained
    SUSPENDED       // Locked by platform (fraud / compliance review)
}

enum class MembershipStatus {
    INVITED,            // Invite sent, not yet accepted
    PENDING_APPROVAL,   // Requested to join, awaiting admin approval
    ACTIVE,
    SUSPENDED,          // Temporarily restricted (e.g. arrears policy)
    LEFT,               // User exited voluntarily
    REMOVED             // Removed by an admin
}
