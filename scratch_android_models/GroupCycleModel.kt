package com.microbond.app.models.groupmodel

import java.util.UUID

/**
 * One round / period of a group (a day, week or month of saving, a ROSCA turn,
 * a billing month, a dues period…).
 *
 * Cycles give reports their "WEEK 1", let deposit status be counted per period,
 * and record who was paid out in each turn.
 */
data class GroupCycleModel(
    val cycleId: String = UUID.randomUUID().toString(),
    val groupId: String,
    val cycleNumber: Int,                           // 1, 2, 3… shown as "WEEK 1" etc.
    val frequency: CycleFrequency,
    val startDate: Long,
    val endDate: Long,
    val dueDate: Long,                              // Deadline for required payments in this cycle

    // Expected money
    val expectedAmountPerMember: Long? = null,      // null for voluntary groups
    val expectedTotal: Long? = null,

    // Payout rotation (Merry-Go-Round / goal payout)
    val payoutRecipientUserIds: List<String> = emptyList(),
    val payoutDate: Long? = null,
    val payoutTransactionIds: List<String> = emptyList(),

    val status: CycleStatus = CycleStatus.UPCOMING,
    val closedAt: Long? = null
)

enum class CycleFrequency {
    DAILY,
    WEEKLY,
    BI_WEEKLY,
    MONTHLY,
    QUARTERLY,
    YEARLY,
    ONE_OFF                 // Single event / fundraiser campaign
}

enum class CycleStatus {
    UPCOMING,
    ACTIVE,
    CLOSED,                 // Deadline passed, totals final
    CANCELLED
}
