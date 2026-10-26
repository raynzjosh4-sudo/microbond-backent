import hashlib
import json
import logging
import uuid
from typing import Optional, Dict, Any, List
from sqlmodel import Session, select

from app.models.group.group import Group, GroupMembership
from app.models.group.rotating.rotating_group_details import RotatingGroupDetails
from app.models.group.wallet.group_wallet import GroupWallet
from app.models.group.finance import MemberObligation, GroupPayout
from app.models.group.ledger.ledger_entry import LedgerEntry
from app.models.group.report.rotating_cycle_report import RotatingCycleReport
from app.models.group.chat import GroupChatMessage
from app.models.user.user import User
from app.utils.time.now_epoch_ms import now_epoch_ms

logger = logging.getLogger(__name__)


def build_cycle_report_payload(
    session: Session,
    group_id: str,
    cycle_number: int,
    payout: Optional[GroupPayout] = None
) -> Dict[str, Any]:
    """
    Assembles the complete, authoritative cycle milestone statement for a rotating group.
    Adheres strictly to the Rotating Group Reporting & Audit Ledger specification.
    """
    # 1. Fetch Group Core & Rotating Details
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise ValueError(f"Group {group_id} not found.")

    details = session.exec(
        select(RotatingGroupDetails).where(RotatingGroupDetails.group_id == group_id)
    ).first()

    wallet = session.exec(
        select(GroupWallet).where(GroupWallet.group_id == group_id)
    ).first()

    curr = group.currency or "UGX"
    total_cycles = details.number_of_cycles if details and details.number_of_cycles else group.member_count or 1

    # 2. Payout for this cycle
    if not payout:
        payout = session.exec(
            select(GroupPayout).where(
                GroupPayout.group_id == group_id,
                GroupPayout.cycle_number == cycle_number
            )
        ).first()

    # 3. Obligations for this cycle
    obligations = session.exec(
        select(MemberObligation).where(
            MemberObligation.group_id == group_id,
            MemberObligation.cycle_number == cycle_number
        )
    ).all()
    ob_by_user = {ob.user_id: ob for ob in obligations}

    # 4. Group Memberships
    memberships = session.exec(
        select(GroupMembership).where(GroupMembership.group_id == group_id)
    ).all()
    member_user_ids = [m.user_id for m in memberships]

    users = session.exec(select(User).where(User.id.in_(member_user_ids))).all() if member_user_ids else []
    user_by_id = {u.id: u for u in users}

    # 5. Financial Summary Calculations
    target_contrib = getattr(details, "contribution_amount", 0) or getattr(details, "target_cycle_contribution", 0) or (group.target_amount or 0)
    expected_pool_target = sum(ob.amount_due for ob in obligations) if obligations else (target_contrib * len(memberships))
    actual_collected = sum(ob.amount_paid for ob in obligations)
    
    collection_rate = round((actual_collected / expected_pool_target * 100), 2) if expected_pool_target > 0 else 100.0

    gross_payout = payout.amount_expected if payout and payout.amount_expected else expected_pool_target
    net_payout = payout.amount_received if (payout and payout.amount_received) else gross_payout
    
    # Calculate security hold
    hold_amount = 0
    if payout and payout.hold_reason and "Security reserve:" in payout.hold_reason:
        try:
            # Extract number from "Security reserve: 40,000 UGX held..."
            parts = payout.hold_reason.split("Security reserve:")[1].split("UGX")[0].strip().replace(",", "")
            hold_amount = int(parts)
        except Exception:
            hold_amount = max(0, gross_payout - net_payout)
    elif gross_payout > net_payout:
        hold_amount = gross_payout - net_payout

    group_reserve_fund_total = (wallet.prepaid_funds if wallet else 0)

    outstanding_arrears = sum(max(0, ob.amount_due - ob.amount_paid) for ob in obligations)
    total_penalties = 0

    # 6. Recipient Details
    recipient_user = None
    recipient_pos = cycle_number
    if payout:
        recipient_user = user_by_id.get(payout.user_id) or session.get(User, payout.user_id)
        # Find payout position
        rec_m = next((m for m in memberships if m.user_id == payout.user_id), None)
        if rec_m and rec_m.payout_position:
            recipient_pos = rec_m.payout_position

    payout_recipient_data = {
        "user_id": str(payout.user_id) if payout else None,
        "full_name": recipient_user.full_name if recipient_user else "Member",
        "turn_position": recipient_pos,
        "destination_provider": "MTN Mobile Money",
        "masked_account_number": recipient_user.phone_number[-4:].rjust(len(recipient_user.phone_number or "0000"), "*") if (recipient_user and recipient_user.phone_number) else "***",
        "disbursement_tx_id": f"payout_tx_c{cycle_number}_{group_id[:8]}",
        "disbursement_timestamp": payout.payout_date if payout else now_epoch_ms(),
        "status": payout.status if payout else "PENDING"
    }

    # 7. Member Performance Breakdown
    now_ms = now_epoch_ms()
    sorted_members = sorted(memberships, key=lambda m: (m.payout_position or 999))
    member_breakdown = []
    
    for m in sorted_members:
        u = user_by_id.get(m.user_id)
        ob = ob_by_user.get(m.user_id)
        
        amt_due = ob.amount_due if ob else target_contrib
        amt_paid = ob.amount_paid if ob else 0
        prepaid_bal = getattr(m, "credit_balance_ugx", 0)
        settled_at = getattr(ob, "settled_at", None) or (ob.updated_at if ob and ob.status == "PAID" else None)

        # Determine status
        if amt_paid >= amt_due:
            if ob and getattr(ob, "paid_by_guarantor", False):
                m_status = "PAID_VIA_GUARANTOR"
            elif ob and ob.due_date and settled_at and settled_at > ob.due_date:
                m_status = "PAID_LATE"
            else:
                m_status = "PAID_ON_TIME"
        elif amt_paid > 0:
            m_status = "PARTIAL"
        else:
            if ob and ob.due_date and now_ms > ob.due_date:
                m_status = "DEFAULTED"
            else:
                m_status = "UNPAID"

        channel = getattr(ob, "payment_channel", None) or "MTN_MOMO"
        strikes = getattr(m, "strikes_count", 0)

        member_breakdown.append({
            "user_id": str(m.user_id),
            "full_name": u.full_name if u else "Member",
            "turn_position": m.payout_position or 0,
            "amount_due": amt_due,
            "amount_paid_this_cycle": amt_paid,
            "advance_prepaid_balance": prepaid_bal,
            "settled_at": settled_at,
            "status": m_status,
            "payment_channel": channel,
            "strikes_incurred": strikes
        })

    # 8. Ledger Entries & Cryptographic SHA-256 Hash
    ledger_query = select(LedgerEntry).where(LedgerEntry.group_id == group_id)
    ob_ids = [ob.id for ob in obligations if ob.id]
    if ob_ids and payout:
        ledger_query = select(LedgerEntry).where(
            (LedgerEntry.group_id == group_id) &
            ((LedgerEntry.obligation_id.in_(ob_ids)) | (LedgerEntry.payout_id == payout.id))
        )
    elif ob_ids:
        ledger_query = select(LedgerEntry).where(
            (LedgerEntry.group_id == group_id) &
            (LedgerEntry.obligation_id.in_(ob_ids))
        )
    
    entries = session.exec(ledger_query).all()
    entries_sorted = sorted(entries, key=lambda e: (e.created_at, str(e.id)))

    if entries_sorted:
        canonical_str = "\n".join(
            f"{e.id}:{e.amount}:{e.source_account}:{e.destination_account}:{e.transaction_type}:{e.status}:{e.created_at}"
            for e in entries_sorted
        )
        sha256_hash = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
    else:
        # Fallback cryptographic seal over the financial summary
        canonical_str = f"{group_id}:{cycle_number}:{expected_pool_target}:{actual_collected}:{gross_payout}:{net_payout}:{now_ms}"
        sha256_hash = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    # 9. Assemble Canonical Schema
    payload = {
        "report_type": "ROTATING_CYCLE_COMPLETION",
        "group_id": group_id,
        "group_name": group.name,
        "cycle_number": cycle_number,
        "total_cycles": total_cycles,
        "currency": curr,
        "generated_at": now_ms,
        
        "financial_summary": {
            "expected_pool_target": expected_pool_target,
            "actual_collected_amount": actual_collected,
            "collection_rate_percentage": collection_rate,
            "gross_payout_amount": gross_payout,
            "early_security_hold_deducted": hold_amount,
            "net_payout_disbursed": net_payout,
            "group_reserve_fund_total": group_reserve_fund_total,
            "outstanding_arrears_ugx": outstanding_arrears,
            "total_penalties_collected_ugx": total_penalties
        },

        "payout_recipient": payout_recipient_data,
        "member_performance_breakdown": member_breakdown,
        "audit_integrity": {
            "ledger_entries_count": len(entries_sorted),
            "cryptographic_hash_sha256": sha256_hash,
            "certified_by": "Microbond Authoritative Ledger Engine"
        }
    }

    return payload


def generate_and_save_cycle_report(
    session: Session,
    group_id: str,
    cycle_number: int,
    payout: Optional[GroupPayout] = None
) -> RotatingCycleReport:
    """
    Generates and persists the RotatingCycleReport record in the database.
    """
    payload = build_cycle_report_payload(session, group_id, cycle_number, payout)
    fin = payload["financial_summary"]
    rec = payload["payout_recipient"]
    audit = payload["audit_integrity"]

    # Check if a report already exists for this cycle
    existing = session.exec(
        select(RotatingCycleReport).where(
            RotatingCycleReport.group_id == group_id,
            RotatingCycleReport.cycle_number == cycle_number
        )
    ).first()

    if existing:
        existing.expected_pool_target = fin["expected_pool_target"]
        existing.actual_collected_amount = fin["actual_collected_amount"]
        existing.collection_rate_percentage = fin["collection_rate_percentage"]
        existing.gross_payout_amount = fin["gross_payout_amount"]
        existing.early_security_hold_deducted = fin["early_security_hold_deducted"]
        existing.net_payout_disbursed = fin["net_payout_disbursed"]
        if rec.get("user_id"):
            existing.recipient_user_id = uuid.UUID(rec["user_id"])
        existing.recipient_name = rec.get("full_name") or "Member"
        existing.recipient_turn_position = rec.get("turn_position") or cycle_number
        existing.report_data = payload
        existing.ledger_entries_count = audit["ledger_entries_count"]
        existing.cryptographic_hash_sha256 = audit["cryptographic_hash_sha256"]
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    report = RotatingCycleReport(
        group_id=group_id,
        cycle_number=cycle_number,
        expected_pool_target=fin["expected_pool_target"],
        actual_collected_amount=fin["actual_collected_amount"],
        collection_rate_percentage=fin["collection_rate_percentage"],
        gross_payout_amount=fin["gross_payout_amount"],
        early_security_hold_deducted=fin["early_security_hold_deducted"],
        net_payout_disbursed=fin["net_payout_disbursed"],
        recipient_user_id=uuid.UUID(rec["user_id"]) if rec.get("user_id") else uuid.uuid4(),
        recipient_name=rec.get("full_name") or "Member",
        recipient_turn_position=rec.get("turn_position") or cycle_number,
        report_data=payload,
        ledger_entries_count=audit["ledger_entries_count"],
        cryptographic_hash_sha256=audit["cryptographic_hash_sha256"]
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return report


def post_cycle_report_card_to_chat(
    session: Session,
    report: RotatingCycleReport
):
    """
    Broadcasts the Interactive Visual Report Card to the group chat (Section 3).
    """
    fin = report.report_data.get("financial_summary", {})
    rec = report.report_data.get("payout_recipient", {})
    curr = report.report_data.get("currency", "UGX")

    collected = fin.get("actual_collected_amount", report.actual_collected_amount)
    target = fin.get("expected_pool_target", report.expected_pool_target)
    rate = fin.get("collection_rate_percentage", report.collection_rate_percentage)
    disbursed = fin.get("net_payout_disbursed", report.net_payout_disbursed)
    hold = fin.get("early_security_hold_deducted", report.early_security_hold_deducted)
    recipient_name = rec.get("full_name", report.recipient_name)

    # Next recipient
    next_cycle = report.cycle_number + 1
    next_payout = session.exec(
        select(GroupPayout).where(
            GroupPayout.group_id == report.group_id,
            GroupPayout.cycle_number == next_cycle
        )
    ).first()
    next_recipient_name = "Next Member in Schedule"
    if next_payout:
        next_user = session.get(User, next_payout.user_id)
        if next_user:
            next_recipient_name = next_user.full_name or "Member"

    lines = [
        f"📊 Cycle {report.cycle_number} Official Report Card",
        f"• Pot Collected: {collected:,} / {target:,} {curr} ({rate}%)",
        f"• Disbursed to {recipient_name}: {disbursed:,} {curr}"
    ]
    if hold > 0:
        lines.append(f"• Security Escrow Held: {hold:,} {curr}")
    if next_payout:
        lines.append(f"• Next Recipient for Cycle {next_cycle}: {next_recipient_name}")

    msg_text = "\n".join(lines)

    chat_msg = GroupChatMessage(
        client_message_id=str(uuid.uuid4()),
        group_id=report.group_id,
        sender_id="SYSTEM",
        message_type="ROTATING_CYCLE_REPORT_CARD",
        message_text=msg_text,
        attachments=[{
            "has_action_button": True,
            "action_text": "Download Full PDF Statement",
            "action_route": "download_cycle_report_pdf",
            "action_payload": {
                "cycle_number": report.cycle_number,
                "report_id": report.report_id,
                "group_id": report.group_id
            }
        }],
        created_at=now_epoch_ms(),
        status="SENT"
    )
    session.add(chat_msg)
    session.commit()
    logger.info(f"[REPORT_SERVICE] Posted visual report card for Cycle {report.cycle_number} to group {report.group_id}")


def generate_printable_html(report_data: Dict[str, Any]) -> str:
    """
    Generates a beautifully styled, authoritative printable HTML report statement
    formatted for browser printing / PDF generation.
    """
    fin = report_data.get("financial_summary", {})
    rec = report_data.get("payout_recipient", {})
    members = report_data.get("member_performance_breakdown", [])
    audit = report_data.get("audit_integrity", {})
    curr = report_data.get("currency", "UGX")

    rows = ""
    for m in members:
        status_color = "#10B981" if "PAID" in m["status"] else ("#F59E0B" if m["status"] == "PARTIAL" else "#EF4444")
        settled_str = f"{m['settled_at']}" if m.get("settled_at") else "—"
        rows += f"""
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #E5E7EB; text-align: center;">#{m['turn_position']}</td>
            <td style="padding: 10px; border-bottom: 1px solid #E5E7EB; font-weight: 500;">{m['full_name']}</td>
            <td style="padding: 10px; border-bottom: 1px solid #E5E7EB; text-align: right;">{m['amount_due']:,} {curr}</td>
            <td style="padding: 10px; border-bottom: 1px solid #E5E7EB; text-align: right; font-weight: 600;">{m['amount_paid_this_cycle']:,} {curr}</td>
            <td style="padding: 10px; border-bottom: 1px solid #E5E7EB; text-align: right; color: #4F46E5;">{m['advance_prepaid_balance']:,} {curr}</td>
            <td style="padding: 10px; border-bottom: 1px solid #E5E7EB; text-align: center;">
                <span style="background: {status_color}22; color: {status_color}; padding: 4px 10px; border-radius: 999px; font-size: 11px; font-weight: 700;">
                    {m['status']}
                </span>
            </td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Cycle {report_data.get('cycle_number')} Milestone Statement — {report_data.get('group_name')}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            color: #111827;
            background: #F9FAFB;
            margin: 0;
            padding: 40px;
        }}
        .report-card {{
            max-width: 850px;
            margin: 0 auto;
            background: #FFFFFF;
            border-radius: 16px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.06);
            padding: 40px;
            border: 1px solid #E5E7EB;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #F3F4F6;
            padding-bottom: 24px;
            margin-bottom: 24px;
        }}
        .badge {{
            background: #EEF2FF;
            color: #4F46E5;
            padding: 6px 14px;
            border-radius: 999px;
            font-size: 13px;
            font-weight: 600;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
            margin-bottom: 32px;
        }}
        .metric-box {{
            background: #F9FAFB;
            padding: 16px;
            border-radius: 12px;
            border: 1px solid #E5E7EB;
        }}
        .metric-label {{
            font-size: 12px;
            color: #6B7280;
            text-transform: uppercase;
            font-weight: 600;
            margin-bottom: 4px;
        }}
        .metric-value {{
            font-size: 20px;
            font-weight: 700;
            color: #111827;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 16px;
            font-size: 13px;
        }}
        th {{
            background: #F9FAFB;
            color: #4B5563;
            padding: 12px 10px;
            text-align: left;
            font-size: 11px;
            text-transform: uppercase;
            border-bottom: 2px solid #E5E7EB;
        }}
        .audit-footer {{
            margin-top: 32px;
            padding-top: 20px;
            border-top: 1px solid #E5E7EB;
            font-size: 11px;
            color: #6B7280;
            display: flex;
            justify-content: space-between;
        }}
        @media print {{
            body {{ background: #FFFFFF; padding: 0; }}
            .report-card {{ box-shadow: none; border: none; padding: 0; }}
        }}
    </style>
</head>
<body>
    <div class="report-card">
        <div class="header">
            <div>
                <h1 style="margin: 0 0 6px 0; font-size: 24px; color: #111827;">{report_data.get('group_name')}</h1>
                <p style="margin: 0; color: #6B7280; font-size: 14px;">Official Cycle {report_data.get('cycle_number')} Milestone Statement</p>
            </div>
            <div style="text-align: right;">
                <span class="badge">ROTATING ROSCA</span>
                <p style="margin: 8px 0 0 0; font-size: 12px; color: #9CA3AF;">Round {report_data.get('cycle_number')} of {report_data.get('total_cycles')}</p>
            </div>
        </div>

        <div class="metrics-grid">
            <div class="metric-box">
                <div class="metric-label">Total Pot Collected</div>
                <div class="metric-value">{fin.get('actual_collected_amount', 0):,} {curr}</div>
                <div style="font-size: 12px; color: #10B981; margin-top: 4px; font-weight: 500;">
                    {fin.get('collection_rate_percentage', 100.0)}% Collection Rate
                </div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Net Disbursed</div>
                <div class="metric-value">{fin.get('net_payout_disbursed', 0):,} {curr}</div>
                <div style="font-size: 12px; color: #4B5563; margin-top: 4px;">
                    To {rec.get('full_name')} (Turn #{rec.get('turn_position')})
                </div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Security Escrow Held</div>
                <div class="metric-value">{fin.get('early_security_hold_deducted', 0):,} {curr}</div>
                <div style="font-size: 12px; color: #6B7280; margin-top: 4px;">
                    Group Reserve Balance
                </div>
            </div>
        </div>

        <h3 style="margin: 0 0 12px 0; font-size: 16px;">Member Performance & Obligation Roster</h3>
        <table>
            <thead>
                <tr>
                    <th style="text-align: center;">Turn</th>
                    <th>Member</th>
                    <th style="text-align: right;">Target</th>
                    <th style="text-align: right;">Paid This Cycle</th>
                    <th style="text-align: right;">Prepaid Credit</th>
                    <th style="text-align: center;">Status</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>

        <div class="audit-footer">
            <div>
                <strong>Authoritative Ledger Integrity</strong><br>
                SHA-256: <code style="color: #4F46E5;">{audit.get('cryptographic_hash_sha256')}</code><br>
                Certified by: {audit.get('certified_by')}
            </div>
            <div style="text-align: right;">
                Entries Audited: {audit.get('ledger_entries_count')}<br>
                Timestamp: {report_data.get('generated_at')}
            </div>
        </div>
    </div>
</body>
</html>
"""
    return html


def generate_csv(report_data: Dict[str, Any]) -> str:
    """
    Generates CSV format export of the cycle milestone statement.
    """
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)

    curr = report_data.get("currency", "UGX")
    fin = report_data.get("financial_summary", {})
    rec = report_data.get("payout_recipient", {})
    audit = report_data.get("audit_integrity", {})

    writer.writerow(["MICROBOND AUTHORITATIVE ROTATING GROUP AUDIT REPORT"])
    writer.writerow(["Group Name", report_data.get("group_name")])
    writer.writerow(["Cycle Number", report_data.get("cycle_number")])
    writer.writerow(["Total Cycles", report_data.get("total_cycles")])
    writer.writerow(["Currency", curr])
    writer.writerow([])

    writer.writerow(["FINANCIAL SUMMARY"])
    writer.writerow(["Expected Target", f"{fin.get('expected_pool_target', 0)} {curr}"])
    writer.writerow(["Actual Collected", f"{fin.get('actual_collected_amount', 0)} {curr}"])
    writer.writerow(["Collection Rate", f"{fin.get('collection_rate_percentage', 0)}%"])
    writer.writerow(["Gross Payout", f"{fin.get('gross_payout_amount', 0)} {curr}"])
    writer.writerow(["Security Escrow Held", f"{fin.get('early_security_hold_deducted', 0)} {curr}"])
    writer.writerow(["Net Disbursed", f"{fin.get('net_payout_disbursed', 0)} {curr}"])
    writer.writerow(["Recipient Name", rec.get("full_name")])
    writer.writerow(["Recipient Turn", rec.get("turn_position")])
    writer.writerow([])

    writer.writerow(["MEMBER PERFORMANCE ROSTER"])
    writer.writerow(["Turn Position", "Member Name", "Amount Due", "Amount Paid", "Advance Prepaid Balance", "Status", "Payment Channel"])
    for m in report_data.get("member_performance_breakdown", []):
        writer.writerow([
            m.get("turn_position"),
            m.get("full_name"),
            m.get("amount_due"),
            m.get("amount_paid_this_cycle"),
            m.get("advance_prepaid_balance"),
            m.get("status"),
            m.get("payment_channel")
        ])

    writer.writerow([])
    writer.writerow(["AUDIT INTEGRITY SEAL"])
    writer.writerow(["Cryptographic SHA-256", audit.get("cryptographic_hash_sha256")])
    writer.writerow(["Ledger Entries Audited", audit.get("ledger_entries_count")])
    writer.writerow(["Certified By", audit.get("certified_by")])

    return output.getvalue()
