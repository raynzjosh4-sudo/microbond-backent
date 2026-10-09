package com.microbond.app.models.groupmodel

import java.util.UUID

/**
 * A generated report for a period (stored so everyone sees the same numbers
 * that were posted to the thread, even if the ledger changes later).
 *
 * Holds raw numbers only. Formatting ("UGX 10,000", "Thu–Sun") happens in the UI
 * when this is mapped to WeeklyReportData for the report bubble.
 */
data class GroupReportModel(
    val reportId: String = UUID.randomUUID().toString(),
    val groupId: String,
    val period: ReportPeriod,
    val periodStart: Long,
    val periodEnd: Long,
    val cycleId: String? = null,
    val sections: Set<ReportSection> = ReportSection.entries.toSet(),
    val summary: GroupPeriodSummary,
    val generatedByUserId: String? = null,          // null = automatic system report
    val generatedAt: Long = System.currentTimeMillis()
)

/** All the numbers behind a report, calculated from transactions + memberships. */
data class GroupPeriodSummary(
    val currency: String = "UGX",
    val expectedAmountPerMember: Long? = null,      // "Daily target"

    // Members
    val membersAtStart: Int,
    val membersJoined: Int,
    val membersLeft: Int,
    val membersAtEnd: Int,
    val eligibleSaveDays: Int = 0,                  // Member-days where a payment was required

    // Per-day breakdown (DAILY SAVING section)
    val dailyBreakdown: List<DailyDepositSummary> = emptyList(),

    // Totals (WEEK TOTALS section)
    val totalCollected: Long,
    val totalExpected: Long? = null,
    val totalPaidOut: Long = 0L,
    val fullDepositCount: Int = 0,
    val partialDepositCount: Int = 0,
    val missedDepositCount: Int = 0,

    // Member behaviour
    val membersSavedAtLeastOnce: Int = 0,
    val membersFullEveryEligibleDay: Int = 0,
    val membersPartialNoMissed: Int = 0,
    val membersMissedOneOrMore: Int = 0,
    val membersNoSavingAtAll: Int = 0,

    // Outstanding balances (BALANCE COUNTS section)
    val membersStartedWithBalance: Int = 0,
    val membersClearedBalance: Int = 0,
    val membersNewBalance: Int = 0,
    val membersEndedWithBalance: Int = 0,
    val totalOutstanding: Long = 0L,

    // Payout rotation
    val payoutsCompletedUserIds: List<String> = emptyList(),
    val nextPayoutUserIds: List<String> = emptyList(),
    val nextPayoutDate: Long? = null,
    val membersRemainingInRotation: Int? = null,

    // Comparison with previous period (null = no baseline yet)
    val previousPeriodCollected: Long? = null
) {
    val busiestDay: DailyDepositSummary?
        get() = dailyBreakdown.maxByOrNull { it.payingMembers }

    val quietestDay: DailyDepositSummary?
        get() = dailyBreakdown.minByOrNull { it.payingMembers }
}

/**
 * Deposit status for one day / one cycle — also what the DEPOSIT_STATUS bubble shows
 * (full · partial · not deposited).
 */
data class DailyDepositSummary(
    val date: Long,
    val fullCount: Int,
    val partialCount: Int,
    val notDepositedCount: Int,
    val amountCollected: Long,
    val amountExpected: Long? = null
) {
    val payingMembers: Int
        get() = fullCount + partialCount
}

enum class ReportPeriod {
    DAY,
    WEEK,
    MONTH,
    YEAR,
    FIVE_YEARS,
    CUSTOM
}

/** Sections a user can choose to include when sharing a report. */
enum class ReportSection {
    MEMBERS,
    DAILY_SAVING,
    WEEK_TOTALS,
    BALANCE_COUNTS,
    ACTIVITY,
    PAYOUT_ROTATION
}
