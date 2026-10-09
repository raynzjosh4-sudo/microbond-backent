package com.microbond.app.core.data_classes_and_enums

import androidx.annotation.DrawableRes
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import com.microbond.app.core.ui.theme.MicrobondActiveGreen

data class TabItem(
    val title: String,
    val unselectedIcon: ImageVector,
    val selectedIcon: ImageVector,
    val isProfileTab: Boolean = false,
    @DrawableRes val profileRes: Int? = null,
    val badgeCount: Int? = null,
    val hasUnreadIndicator: Boolean = false
)

public data class ChartPreview(
    val name: String,
    val initials: String,
    val message: String,
    val time: String,
    val isOutgoingMessage: Boolean = true,
    val unreadCount: Int = 0,
    val isFavorite: Boolean = false,
    val isGroup: Boolean = false,
    val avatarColor: Color,
    val messageStatus: MessageStatus,
    val memberStatuses: List<MemberSaveStatus> = emptyList()
)

enum class ThreadBubbleType {
    TEXT, REPLY, VOICE, IMAGE, DEPOSIT, DEPOSIT_STATUS, WEEKLY_REPORT,
    SECURITY_RULES, SECURITY_POLL, SAVINGS_RECEIVED, SECURITY_RULE_UPDATE,
    LOCATION, STAT_GROUP_PROGRESS, STAT_GROUP_SNAPSHOT, GROUP_HEALTH, STAT_HISTOGRAM,
    PAYMENT_UPDATE, DOCUMENT, CONTACT, SYSTEM, POLL, VIDEO, ACTION_PROMPT,
    // New chart bubbles
    STAT_CANDLESTICK, STAT_AREA, STAT_WATERFALL, STAT_SCATTER, STAT_BOXPLOT, STAT_HEATMAP,
    STAT_CUSTOM_CHART
}

data class ThreadEvent(
    val id: Int,
    val text: String,
    val time: String,
    val isCurrentUser: Boolean,
    val status: MessageStatus? = null,
    val type: ThreadBubbleType = ThreadBubbleType.TEXT,
    val senderName: String? = null,
    val senderPhone: String? = null,
    val senderInitials: String = senderName?.take(1)?.uppercase() ?: "?",
    val senderColor: Color = MicrobondActiveGreen,
    @DrawableRes val senderAvatarRes: Int? = null,
    val quotedSender: String? = null,
    val quotedText: String? = null,
    @DrawableRes val imageRes: Int? = null,
    val imageResList: List<Int>? = null,
    val imageUri: String? = null,
    val imageUris: List<String>? = null,
    val imageAspectRatio: Float? = null,
    // Deposit Specific Fields
    val amount: String? = null,
    val paymentMethod: String? = null,
    val referenceId: String? = null,
    val cycleNote: String? = null,
    val isVerified: Boolean = false,
    val receiptUrl: String? = null,
    val fullDate: String? = null,
    val requiredAmount: Long = 0L,
    val depositedAmount: Long = 0L,
    // Deposit Status Fields
    val fullDepositCount: Int = 0,
    val halfDepositCount: Int = 0,
    val notDepositedCount: Int = 0,
    // Weekly Report Fields
    val weeklyReport: WeeklyReportData? = null,
    // Security Fields
    val securityRules: SecurityRulesData? = null,
    val securityPoll: SecurityPollData? = null,
    val savingsReceived: SavingsReceivedData? = null,
    val securityRuleUpdate: SecurityRuleUpdateData? = null,
    // Location
    val locationPlace: String? = null,
    val locationSubtitle: String? = null,
    // Statistics — existing
    val statGroupProgress: StatGroupProgressData? = null,
    val statGroupSnapshot: StatGroupSnapshotData? = null,
    val groupHealth: GroupHealthData? = null,
    val statHistogram: StatHistogramData? = null,
    // Statistics — new chart bubbles
    val statCustomChart: StatCustomChartData? = null,
    val statCandlestick: StatCandlestickData? = null,
    val statArea: StatAreaData? = null,
    val statWaterfall: StatWaterfallData? = null,
    val statScatter: StatScatterData? = null,
    val statBoxPlot: StatBoxPlotData? = null,
    val statHeatmap: StatHeatmapData? = null,
    // Other Bubble Data
    val paymentUpdate: PaymentUpdateData? = null,
    val documentData: DocumentData? = null,
    val contactData: List<ContactBubbleData> = emptyList(),
    val systemMessage: String? = null,
    val pollData: StandardPollData? = null,
    val videoData: VideoData? = null,
    val actionPromptData: ActionPromptData? = null,
    val voiceUri: String? = null,
    val quotedEventId: Int? = null,
    val quotedAccentColor: Color? = null
)

data class WeeklyReportData(
    val weekLabel: String = "WEEK 1 SAVING REPORT",
    val groupName: String = "UGANDAN BIBINA",
    val dateRange: String = "21 – 27 Sep 2026",
    val dailyTarget: String = "UGX 10,000",
    val memberCount: Int = 50,
    val asOf: String = "28 Sep 2026 · 8:00 PM",
    // Members
    val membersStart: Int = 48,
    val membersJoined: Int = 2,
    val membersLeft: Int = 0,
    val membersNow: Int = 50,
    val eligibleSaveDays: Int = 344,
    // Daily saving per day: Triple(full, partial, noSave)
    val dailySavings: List<Pair<String, Triple<Int, Int, Int>>> = emptyList(),
    // Week Totals
    val totalFullDays: Int = 315,
    val totalPartialDays: Int = 21,
    val totalNoSaveDays: Int = 8,
    val membersSavedAtLeastOnce: Int = 49,
    val successfulSaveDays: Int = 336,
    val fullEveryEligibleDay: Int = 40,
    val partialNoMissedDays: Int = 6,
    val missed1PlusDays: Int = 3,
    val noSavingAllWeek: Int = 1,
    // Balance
    val startedWithBalance: Int = 4,
    val clearedBalance: Int = 2,
    val newBalances: Int = 9,
    val endWithBalance: Int = 11,
    // Activity
    val busiestDays: String = "Thu–Sun",
    val saversPerDay: Int = 49,
    val quietestDay: String = "Mon",
    val quietestCount: Int = 46,
    // Payout Rotation
    val payoutThisWeek: String = "2/2 completed (28 Sep): Grace N. + John B.",
    val payoutNextWeek: String = "Mon 5 Oct: Mariam K. + Denis O.",
    val remainAfterPayout: Int = 46,
    // Baseline
    val baselineNote: String = "no prior-week comparison",
    val footerTime: String = "8:00 PM",
    val visibleSections: Set<String> = emptySet(),
    val filterSections: Boolean = false
)

/** Data for SECURITY_RULES bubble (MicroBondSecurityRulesBubble) */
data class SecurityRulesData(
    val title: String = "Group rules",
    val rules: List<String> = emptyList(),
    val pinnedLabel: String = "Pinned for everyone",
    val viewAllLabel: String = "View all rules"
)

data class PollOption(
    val id: String,
    val label: String,
    val percentage: Int,
    val isSelected: Boolean
)

data class PollReply(
    val id: String,
    val senderName: String,
    val senderInitials: String,
    val senderColor: Color,
    val time: String,
    val text: String
)

/** Data for SECURITY_POLL bubble (MicroBondSecurityPollBubble) */
data class SecurityPollData(
    val questionTitle: String = "Change the joining rule?",
    val questionSubtitle: String = "Open the group to new members?",
    val options: List<PollOption> = emptyList(),
    val totalVotes: Int = 12,
    val footerText: String = "Majority: 8 of 12",
    val replies: List<PollReply> = emptyList()
)

/** Data for SAVINGS_RECEIVED bubble */
data class SavingsReceivedData(
    val title: String = "Savings received",
    val subtitle: String = "Your savings have been delivered",
    val recipientName: String = "Joseph",
    val status: String = "Completed",
    val footerText: String = "Group payout · Confirmed"
)

/** Data for SECURITY_RULE_UPDATE bubble (MicroBondSecurityRuleUpdateBubble) */
data class SecurityRuleUpdateData(
    val ruleText: String = "Payouts are sent in member order. New members join after the current cycle.",
    val title: String = "Group rule updated",
    val statusLabel: String = "Active rule",
    val approvalNote: String = "Approved by the group",
    val approvalDate: String = "Today"
)

/** A single data point on the statistics line chart */
data class StatChartPoint(
    val label: String,   // e.g. "May"
    val value: Float     // 0f–100f
)

data class StatCustomChartData(
    val chartId: String,
    val title: String,
    val subtitle: String,
    val xLabel: String,
    val yLabel: String,
    val xValues: List<Float>,
    val yValues: List<Float>,
    val primaryColorValue: Long,
    val secondaryColorValue: Long
)

/** Data for STAT_GROUP_PROGRESS bubble (MicroBondStatGroupProgressBubble) */
data class StatGroupProgressData(
    val title: String = "Group statistics",
    val subtitle: String = "Payout progress \u00b7 last 6 months",
    val chartPoints: List<StatChartPoint> = emptyList(),
    val chartColorValue: Long? = null,
    // Summary stats
    val onTimePayoutsLabel: String = "On-time payouts",
    val onTimePayoutsValue: String = "91%",
    val activeMembersLabel: String = "Active members",
    val activeMembersValue: String = "15",
    val avgWaitLabel: String = "Avg. wait",
    val avgWaitValue: String = "3 days",
    val updatedNote: String = "Updated today"
)

/** A slice of the donut chart */
data class StatDonutSlice(
    val label: String,       // e.g. "Payouts"
    val percentage: Int,     // e.g. 54
    val colorValue: Long     // e.g. 0xFF54B478
)

/** Data for STAT_GROUP_SNAPSHOT bubble (MicroBondStatGroupSnapshotBubble) */
data class StatGroupSnapshotData(
    val title: String = "Savings group snapshot",
    val subtitle: String = "Where this month's money went",
    val slices: List<StatDonutSlice> = emptyList(),
    // Summary stats
    val membersLabel: String = "Members",
    val membersValue: String = "15",
    val collectedLabel: String = "Collected",
    val collectedValue: String = "$1,240",
    val nextPayoutLabel: String = "Next payout",
    val nextPayoutValue: String = "Friday"
)

/** A data point on the radar chart for group health */
data class RadarChartPoint(
    val label: String,
    val value: Float // 0f to 1f
)

/** Data for GROUP_HEALTH bubble (MicroBondGroupHealthBubble) */
data class GroupHealthData(
    val title: String = "Group health",
    val subtitle: String = "Current member experience",
    val radarPoints: List<RadarChartPoint> = emptyList(),
    val chartColorValue: Long? = null,
    val strongestText: String = "trust + support",
    val focusNextText: String = "payout speed",
    val footerText: String = "15 members \u00b7 12 responses"
)

/** A single bar in the histogram */
data class HistogramBar(
    val label: String,      // e.g., "Jan"
    val value: Float,       // e.g., 50000f
    val highlight: Boolean = false, // If true, make this bar a different color (e.g. current month)
    val colorValue: Long? = null
)

/** Data for STAT_HISTOGRAM bubble (MicroBondStatHistogramBubble) */
data class StatHistogramData(
    val title: String = "Deposit history",
    val subtitle: String = "Total group savings by month",
    val bars: List<HistogramBar> = emptyList(),
    val highlightColorValue: Long = 0xFF3B82F6,
    val totalLabel: String = "Total saved",
    val totalValue: String = "UGX 1.2M",
    val highestLabel: String = "Highest month",
    val highestValue: String = "August",
    val avgLabel: String = "Avg. monthly",
    val avgValue: String = "UGX 200K",
    val footerText: String = "Last 6 months"
)

// ── NEW CHART DATA CLASSES ──────────────────────────────────────────────────

/** A single OHLC candle for the candlestick chart */
data class CandlestickBar(
    val label: String,      // e.g. "Mon", "Jan"
    val open: Float,
    val high: Float,
    val low: Float,
    val close: Float
)

/** Data for STAT_CANDLESTICK bubble (MicroBondStatCandlestickBubble) */
data class StatCandlestickData(
    val title: String = "Price movement",
    val subtitle: String = "Open · High · Low · Close",
    val candles: List<CandlestickBar> = emptyList(),
    val bullishColorValue: Long? = null,
    val bearishColorValue: Long? = null,
    val currencySymbol: String = "UGX",
    val highLabel: String = "Period High",
    val highValue: String = "UGX 120,000",
    val lowLabel: String = "Period Low",
    val lowValue: String = "UGX 80,000",
    val footerText: String = "Last 8 periods"
)

/** A single layer in a stacked area chart */
data class AreaChartLayer(
    val label: String,          // e.g. "Savings", "Loans"
    val colorValue: Long,       // e.g. 0xFF4ADE80
    val values: List<Float>     // one per x-axis period
)

/** Data for STAT_AREA bubble (MicroBondStatAreaBubble) */
data class StatAreaData(
    val title: String = "Contribution breakdown",
    val subtitle: String = "How savings grew over time",
    val xLabels: List<String> = emptyList(),   // e.g. ["Jan","Feb","Mar"]
    val layers: List<AreaChartLayer> = emptyList(),
    val totalLabel: String = "Total accumulated",
    val totalValue: String = "UGX 3.6M",
    val footerText: String = "Last 6 months"
)

/** A single bar segment in a waterfall chart (positive = inflow, negative = outflow) */
data class WaterfallBar(
    val label: String,       // e.g. "Deposits", "Payouts"
    val value: Float,        // Positive = gain, negative = loss
    val isTotal: Boolean = false  // If true, render as the running total bar
)

/** Data for STAT_WATERFALL bubble (MicroBondStatWaterfallBubble) */
data class StatWaterfallData(
    val title: String = "Cash flow",
    val subtitle: String = "Inflows & outflows this cycle",
    val bars: List<WaterfallBar> = emptyList(),
    val gainColorValue: Long? = null,
    val lossColorValue: Long? = null,
    val currencySymbol: String = "UGX",
    val netLabel: String = "Net change",
    val netValue: String = "+UGX 240,000",
    val footerText: String = "Current savings cycle"
)

/** A single point in a scatter plot */
data class ScatterPoint(
    val x: Float,           // e.g. member deposit rate (0–100%)
    val y: Float,           // e.g. on-time rate (0–100%)
    val label: String = ""  // optional member name label
)

/** Data for STAT_SCATTER bubble (MicroBondStatScatterBubble) */
data class StatScatterData(
    val title: String = "Member correlation",
    val subtitle: String = "Deposit rate vs. on-time rate",
    val points: List<ScatterPoint> = emptyList(),
    val primaryColorValue: Long? = null,
    val secondaryColorValue: Long? = null,
    val xAxisLabel: String = "Deposit rate",
    val yAxisLabel: String = "On-time %",
    val correlationLabel: String = "Correlation",
    val correlationValue: String = "0.82 (strong)"
)

/** A single box (5-number summary) in a box plot */
data class BoxPlotEntry(
    val label: String,   // e.g. member name or month
    val min: Float,
    val q1: Float,
    val median: Float,
    val q3: Float,
    val max: Float,
    val colorValue: Long = 0xFF4ADE80
)

/** Data for STAT_BOXPLOT bubble (MicroBondStatBoxPlotBubble) */
data class StatBoxPlotData(
    val title: String = "Deposit distribution",
    val subtitle: String = "Min · Q1 · Median · Q3 · Max",
    val entries: List<BoxPlotEntry> = emptyList(),
    val currencySymbol: String = "UGX",
    val footerText: String = "Last 6 months per member"
)

/** A single cell in the heatmap grid */
data class HeatmapCell(
    val rowLabel: String,     // e.g. member name
    val colLabel: String,     // e.g. month
    val value: Float,         // 0f = none, 1f = full
    val displayText: String = ""
)

/** Data for STAT_HEATMAP bubble (MicroBondStatHeatmapBubble) */
data class StatHeatmapData(
    val title: String = "Member payment heatmap",
    val subtitle: String = "Deposit activity per member per month",
    val rowLabels: List<String> = emptyList(),  // members
    val colLabels: List<String> = emptyList(),  // months
    val cells: List<HeatmapCell> = emptyList(),
    val lowColorValue: Long? = null,
    val highColorValue: Long? = null,
    val footerText: String = "Green = paid · Red = missed"
)

data class PaymentUpdateData(
    val depositedAmountText: String = "UGX 80,000",
    val requiredAmountText: String? = "UGX 100,000",
    val reminderText: String = "Reminder: UGX 20,000",
    val dateText: String = "Deposited on 30 Sep 2026",
    val title: String = "Payment update",
    val paymentPhoneText: String? = null,
    val paymentMethodText: String? = null
)

data class StandardPollData(
    val question: String,
    val options: List<PollOption> = emptyList(),
    val isMultipleChoice: Boolean = false,
    val questionSubtitle: String = "",
    val footerText: String = "No votes yet"
)

data class VideoData(
    val duration: String,
    val caption: String? = null
)

data class ActionPromptData(
    val message: String,
    val actionText: String? = null
)

/** Options available in the attachment picker sheet. */
enum class AttachmentOption {
    GALLERY, DEPOSIT_STATUS, CAMERA, SAVE_REPORT, LOCATION, CONTACT, DOCUMENT, POLL, EVENT, RULES, AI_IMAGES, STATISTICS
}

/** Represents a single cell in the attachment picker grid. */
data class AttachmentItem(
    val option: AttachmentOption,
    val icon: ImageVector,
    val label: String,
    val tint: Color,
    val background: Color
)


data class MicrobondMenuAction(
    val title: String,
    val onClick: () -> Unit,
    val icon: ImageVector? = null,
    val enabled: Boolean = true
)


data class GroupMemberSummary(
    val name: String,
    val phoneNumber: String = "",
    val role: String = "Member",
    val trustScore: Int? = 7,
    val contributionStatus: MemberSaveStatus = MemberSaveStatus.PENDING
)

data class GroupPrivateSettings(
    val muted: Boolean = false,
    val customNotification: String? = null,
    val linkedPaymentMethod: String? = null,
    val maskedPaymentDestination: String? = null,
    val personalSavedAmount: Long? = null,
    val personalShareCount: Int? = null,
    val personalPledges: List<String> = emptyList(),
    val autoPayEnabled: Boolean = false,
    val autoRoundupEnabled: Boolean = false,
    val personalSplitPercent: Double? = null,
    val allowConfidentialClaims: Boolean = false
)

data class GroupAdminSettings(
    val membersCanEditInfo: Boolean = false,
    val membersCanSendMessages: Boolean = true,
    val membersCanAddMembers: Boolean = false,
    val requireMemberApproval: Boolean = true,
    val assignedAdmins: List<String> = emptyList(),
    val requireMultiSignature: Boolean = false,
    val minimumTrustScore: Int? = null,
    val membersCanVerifyContributions: Boolean = false,
    val membersCanManagePayoutRoster: Boolean = false,
    val membersCanTriggerPayments: Boolean = false,
    val membersCanManageUtilities: Boolean = false
)

sealed interface GroupPurposeData

data class TargetSavingsGroupData(
    val goalAmount: Long,
    val targetDate: String,
    val progressPercent: Double,
    val savingsPace: String,
    val milestonesPercent: List<Int> = listOf(25, 50, 75, 100),
    val lockFunds: Boolean = true,
    val hideLeaderboard: Boolean = false,
    val topUpMatchingAmount: Long = 0L,
    val overagePolicy: String = "Keep in group wallet",
    val allowEarlyExits: Boolean = false
) : GroupPurposeData

data class RotatingRoscaGroupData(
    val contributionAmount: Long,
    val paymentFrequency: String,
    val payoutsPerCycle: Int = 1,
    val totalCycles: Int = 1,
    val payoutOrderStrategy: String = "Randomized",
    val payoutOrder: List<List<String>> = emptyList(), // Multi-Payout Matrix
    val nextPayoutDate: String,
    val startDate: Long = 0L,
    val contributionStreaks: Map<String, Int> = emptyMap(),
    val strikeCounts: Map<String, Int> = emptyMap(),
    val latePaymentPenaltyFee: Long = 0L,
    val requirePaymentProof: Boolean = true,
    val gracePeriodHours: Int = 24,
    val defaultActionThresholdHours: Int = 48,
    val enforcePayoutHold: Boolean = true,
    // Trust & Admission Criteria
    val minimumKycTier: String = "UNVERIFIED",
    val minimumTrustScore: Int? = null,
    val requiresGuarantor: Boolean = false
) : GroupPurposeData

data class UtilityAccountData(
    val provider: String,
    val accountReference: String,
    val serviceType: String
)

data class UtilityBillData(
    val provider: String,
    val amountDue: Long,
    val dueDate: String,
    val status: String
)

data class UtilityPaymentRecord(
    val provider: String,
    val amountPaid: Long,
    val paidDate: String,
    val reference: String
)

data class SharedBillUtilityGroupData(
    val connectedUtilities: List<UtilityAccountData>,
    val upcomingBills: List<UtilityBillData>,
    val averageMonthlySpend: Long,
    val paymentHistory: List<UtilityPaymentRecord>,
    val memberSplitPercentages: Map<String, Double>,
    val autoPayEnabled: Boolean = false,
    val approvedVendors: List<String> = emptyList(),
    val disputeResolutionAuthority: String = "Group admins"
) : GroupPurposeData

data class WelfareRequestSummary(
    val requestId: String,
    val amount: Long,
    val status: String,
    val submittedDate: String,
    val confidential: Boolean = true
)

data class WelfareAssistanceRecord(
    val recipient: String,
    val amount: Long,
    val reason: String,
    val paidDate: String
)

data class EmergencyWelfareGroupData(
    val poolBalance: Long,
    val activeHelpRequests: List<WelfareRequestSummary>,
    val assistanceHistory: List<WelfareAssistanceRecord>,
    val replenishmentTarget: Long,
    val trustedVendorLinks: List<String> = emptyList(),
    val memberStanding: Map<String, String> = emptyMap(),
    val approvalProcess: String = "Group vote",
    val maximumPayout: Long = 500_000L,
    val directToVendorPayouts: Boolean = false,
    val hardshipWaiversAllowed: Boolean = false,
    val contributionsPaused: Boolean = false
) : GroupPurposeData

data class GroupPledgeSummary(
    val memberName: String,
    val description: String,
    val pledgedAmount: Long,
    val paidAmount: Long,
    val anonymous: Boolean = false
)

data class EventPledgeGroupData(
    val eventDate: String,
    val totalBudget: Long,
    val totalRaised: Long,
    val pledges: List<GroupPledgeSummary>,
    val remainingShortfall: Long,
    val sponsorBadges: List<String> = emptyList(),
    val allowAnonymousContributions: Boolean = false,
    val vendorPaymentsEnabled: Boolean = true,
    val pledgesLocked: Boolean = false,
    val pledgeCap: Long? = null,
    val milestoneAmounts: List<Long> = emptyList()
) : GroupPurposeData

data class ActiveGroupLoan(
    val borrower: String,
    val principal: Long,
    val dueDate: String,
    val status: String
)

data class LendingInvestmentGroupData(
    val shareValue: Long,
    val totalGroupCapital: Long,
    val activeLoans: List<ActiveGroupLoan>,
    val groupRoiPercent: Double,
    val defaultRatePercent: Double,
    val interestRatePercent: Double,
    val guarantorsRequired: Int = 0,
    val maximumBorrowingMultiplier: Double = 3.0,
    val earlyRepaymentDiscountPercent: Double = 0.0,
    val defaultAssetSeizureEnabled: Boolean = false,
    val dividendReinvestmentEnabled: Boolean = false
) : GroupPurposeData

data class ContributionFundraiserGroupData(
    val targetAmount: Long,
    val raisedAmount: Long,
    val targetDate: String,
    val activeDonorCount: Int,
    val pledgeFulfillmentPercent: Double,
    val paymentChannelSplitPercent: Map<String, Double>,
    val allowAnonymousContributions: Boolean = true,
    val vendorPaymentsEnabled: Boolean = false
) : GroupPurposeData


data class SharedWalletGroupData(
    val walletPurpose: String,
    val walletBalance: Long,
    val recentInflows: List<Long>,
    val recentOutflows: List<Long>,
    val spendingCategories: Map<String, Long>,
    val requiresApprovalAbove: Long,
    val approverNames: List<String>,
    val memberBalanceVisibility: Boolean = true
) : GroupPurposeData

data class AssociationDuesGroupData(
    val duesAmount: Long,
    val paymentFrequency: String,
    val nextDueDate: String,
    val membersCurrent: Int,
    val membersInArrears: Int,
    val arrearsAmount: Long,
    val lateFeeAmount: Long = 0L,
    val gracePeriodDays: Int = 7,
    val allowInstallments: Boolean = false
) : GroupPurposeData
