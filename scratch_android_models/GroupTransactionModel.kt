package com.microbond.app.models.groupmodel

import com.microbond.app.core.payment.PaymentMethod
import java.util.UUID

/**
 * A single money movement inside a group — the group's ledger.
 *
 * This is the SOURCE OF TRUTH for everything money-related:
 * deposit bubbles, deposit status counts, reports and most charts are
 * calculated from these records instead of being stored as display text.
 *
 * Amounts are stored as whole currency units (UGX has no minor unit).
 */
data class GroupTransactionModel(
    val transactionId: String = UUID.randomUUID().toString(),
    val groupId: String,
    val userId: String,                             // Member who paid / received
    val type: TransactionType,
    val amount: Long,
    val currency: String = "UGX",

    // What this money relates to
    val cycleId: String? = null,                    // Round / period it belongs to (GroupCycleModel)
    val obligationId: String? = null,               // Required amount it pays towards (MemberObligation)
    val expectedAmount: Long? = null,               // Snapshot of the required amount at payment time
    val counterpartyUserId: String? = null,         // e.g. payout recipient, loan borrower
    val counterpartyName: String? = null,           // e.g. vendor / utility provider for outside payments
    val note: String? = null,                       // e.g. "Weekly Saving Deposit"

    // Payment channel
    val paymentMethod: PaymentMethod? = null,
    val providerName: String? = null,               // e.g. "MTN Mobile Money", "Airtel Money"
    val payerAccount: String? = null,               // Phone / account the money came from
    val internalReference: String,                  // Microbond ref e.g. "DEP-94821"
    val externalReference: String? = null,          // Telecom / bank transaction id
    val receiptUrl: String? = null,

    // Status & verification
    val status: TransactionStatus = TransactionStatus.INITIATED,
    val failureReason: String? = null,
    val isVerified: Boolean = false,
    val verifiedByUserId: String? = null,           // null + isVerified = auto-verified by provider callback
    val verifiedAt: Long? = null,

    // Audit
    val createdByUserId: String,                    // Who recorded it (member, admin or "system")
    val createdAt: Long = System.currentTimeMillis(),
    val completedAt: Long? = null
) {
    val isInflow: Boolean
        get() = type.isInflow

    /** Signed amount for balance calculations (+ in, − out). */
    val signedAmount: Long
        get() = if (isInflow) amount else -amount

    /** FULL / PARTIAL / OVERPAID against the required amount, or null for voluntary money. */
    val coverage: DepositCoverage?
        get() {
            val expected = expectedAmount ?: return null
            return when {
                amount < expected -> DepositCoverage.PARTIAL
                amount == expected -> DepositCoverage.FULL
                else -> DepositCoverage.OVERPAID
            }
        }
}

enum class TransactionType(val isInflow: Boolean) {
    // Money into the group
    DEPOSIT(true),                  // Savings / ROSCA contribution / dues
    PLEDGE_PAYMENT(true),           // Paying towards an event pledge
    DONATION(true),                 // Voluntary fundraiser / wallet top-up
    LOAN_REPAYMENT(true),
    LATE_FEE(true),
    PENALTY(true),
    INTEREST_EARNED(true),

    // Money out of the group
    PAYOUT(false),                  // ROSCA rotation payout / goal payout
    LOAN_DISBURSEMENT(false),
    WELFARE_PAYOUT(false),          // Approved help request
    BILL_PAYMENT(false),            // Utility bill paid from pool
    VENDOR_PAYMENT(false),          // Event / wallet spending
    DIVIDEND(false),
    REFUND(false),
    WITHDRAWAL(false)               // Member exit / early withdrawal
}

enum class TransactionStatus {
    INITIATED,              // Created in app, nothing sent yet
    PENDING_CONFIRMATION,   // STK push sent / awaiting provider callback
    PENDING_APPROVAL,       // Outflow waiting for admin / quorum approval
    COMPLETED,
    FAILED,
    REVERSED,
    CANCELLED
}

enum class DepositCoverage {
    FULL,
    PARTIAL,
    OVERPAID
}
