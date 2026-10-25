import time
import uuid
from typing import List, Dict, Any, Optional
from collections import defaultdict
from sqlmodel import Session, select, func
from sqlalchemy import desc

from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.finance import MemberObligation, GroupPayout
from app.models.group.rotating import RotatingGroupDetails
from app.models.group.chat import GroupChatMessage, GroupChatReadReceipt
from app.schemas.group_dashboard_summary import (
    RingStatus,
    ActionMessage,
    GroupListSummaryResponse,
    LastMessageSummary,
)

def format_message_preview(msg: GroupChatMessage) -> str:
    """Formats a concise preview text for the dashboard group list."""
    if msg.message_text and msg.message_text.strip():
        return msg.message_text.strip()
    
    if msg.message_type == "MEDIA" or msg.media_type:
        media_map = {
            "IMAGE": "📷 Photo",
            "VIDEO": "🎥 Video",
            "AUDIO": "🎤 Audio",
            "VOICE_NOTE": "🎤 Voice message",
            "DOCUMENT": "📄 Document",
        }
        return media_map.get(msg.media_type, "📎 Attachment")
    
    if msg.message_type == "SYSTEM_EVENT":
        return msg.message_text or "System notice"
    
    if msg.message_type == "VOTE":
        return "📊 Poll"
        
    return "Message"

class GroupDashboardSummaryService:
    """
    High-Performance, Batch-Aggregated Dashboard Summary Engine.
    Executes exactly bulk queries across ALL of a user's groups simultaneously,
    eliminating the O(N) query explosion completely.
    """

    @classmethod
    def get_user_dashboard_summaries(
        cls,
        session: Session,
        user_id: uuid.UUID
    ) -> List[GroupListSummaryResponse]:
        """
        Calculates all group summaries for the user in a strict constant number of bulk queries:
        Query 1: User's Active Memberships + Group Models (JOIN)
        Query 2: Batch Total Member Counts per Group
        Query 3: Batch Active Cycle Obligations
        Query 4: Batch Rotating Details & Upcoming Payouts
        Query 5: Batch Unread Message Counts
        """
        now_ms = int(time.time() * 1000)
        user_id_str = str(user_id)

        # -------------------------------------------------------------
        # QUERY 1: Fetch all Groups user belongs to via single JOIN
        # -------------------------------------------------------------
        results = session.exec(
            select(Group, GroupMembership)
            .join(GroupMembership, Group.group_id == GroupMembership.group_id)
            .where(
                GroupMembership.user_id == user_id,
                GroupMembership.status == "ACTIVE"
            )
        ).all()

        if not results:
            return []

        groups: List[Group] = [r[0] for r in results]
        group_ids: List[str] = [g.group_id for g in groups]

        # -------------------------------------------------------------
        # QUERY 2: Bulk Member Counts per Group (GROUP BY group_id)
        # -------------------------------------------------------------
        member_count_rows = session.exec(
            select(GroupMembership.group_id, func.count(GroupMembership.id))
            .where(
                GroupMembership.group_id.in_(group_ids),
                GroupMembership.status == "ACTIVE"
            )
            .group_by(GroupMembership.group_id)
        ).all()
        member_counts: Dict[str, int] = {row[0]: row[1] for row in member_count_rows}

        # -------------------------------------------------------------
        # QUERY 3: Bulk Rotating Group Details (Single WHERE IN query)
        # -------------------------------------------------------------
        rot_details_list = session.exec(
            select(RotatingGroupDetails).where(RotatingGroupDetails.group_id.in_(group_ids))
        ).all()
        current_cycles: Dict[str, int] = {rd.group_id: rd.current_cycle for rd in rot_details_list}

        # -------------------------------------------------------------
        # QUERY 4: Bulk Obligations Calculation (In-memory grouping)
        # -------------------------------------------------------------
        obligations = session.exec(
            select(MemberObligation).where(MemberObligation.group_id.in_(group_ids))
        ).all()

        # Group obligations by group_id
        obs_by_group: Dict[str, List[MemberObligation]] = defaultdict(list)
        for ob in obligations:
            # Match to current cycle (default 1 if not rotating)
            target_cycle = current_cycles.get(ob.group_id, 1)
            if ob.cycle_number == target_cycle:
                obs_by_group[ob.group_id].append(ob)

        # -------------------------------------------------------------
        # QUERY 5: Bulk Unread Chat Calculation
        # Total messages sent by others per group
        # -------------------------------------------------------------
        total_msgs_rows = session.exec(
            select(GroupChatMessage.group_id, func.count(GroupChatMessage.id))
            .where(
                GroupChatMessage.group_id.in_(group_ids),
                GroupChatMessage.sender_id != user_id_str,
                GroupChatMessage.is_deleted == False
            )
            .group_by(GroupChatMessage.group_id)
        ).all()
        total_msgs_map: Dict[str, int] = {r[0]: r[1] for r in total_msgs_rows}

        read_msgs_rows = session.exec(
            select(GroupChatMessage.group_id, func.count(GroupChatReadReceipt.message_id))
            .join(GroupChatMessage, GroupChatMessage.id == GroupChatReadReceipt.message_id)
            .where(
                GroupChatMessage.group_id.in_(group_ids),
                GroupChatReadReceipt.user_id == user_id_str
            )
            .group_by(GroupChatMessage.group_id)
        ).all()
        read_msgs_map: Dict[str, int] = {r[0]: r[1] for r in read_msgs_rows}

        # -------------------------------------------------------------
        # QUERY 6: Bulk Latest Chat Message per Group
        # -------------------------------------------------------------
        ranked_msgs_subq = (
            select(
                GroupChatMessage.id.label("msg_id"),
                func.row_number()
                .over(
                    partition_by=GroupChatMessage.group_id,
                    order_by=desc(GroupChatMessage.created_at),
                )
                .label("rn"),
            )
            .where(
                GroupChatMessage.group_id.in_(group_ids),
                GroupChatMessage.is_deleted == False,
            )
            .subquery()
        )

        latest_msgs_rows = session.exec(
            select(GroupChatMessage)
            .join(ranked_msgs_subq, GroupChatMessage.id == ranked_msgs_subq.c.msg_id)
            .where(ranked_msgs_subq.c.rn == 1)
        ).all()
        latest_msgs_by_group: Dict[str, GroupChatMessage] = {
            m.group_id: m for m in latest_msgs_rows
        }

        # Bulk resolve sender names for non-system messages
        sender_uuids = set()
        for m in latest_msgs_rows:
            if m.sender_id and m.sender_id != "SYSTEM":
                try:
                    sender_uuids.add(uuid.UUID(m.sender_id))
                except (ValueError, TypeError):
                    pass

        sender_names_map: Dict[str, str] = {}
        if sender_uuids:
            user_rows = session.exec(
                select(User.id, User.full_name).where(User.id.in_(sender_uuids))
            ).all()
            sender_names_map = {str(u[0]): (u[1] or "Member") for u in user_rows}

        # -------------------------------------------------------------
        # QUERY 7: Bulk Upcoming Payouts (for MERRY_GO_ROUND groups)
        # -------------------------------------------------------------
        upcoming_payouts = session.exec(
            select(GroupPayout)
            .where(
                GroupPayout.group_id.in_(group_ids),
                GroupPayout.status == "PENDING"
            )
            .order_by(GroupPayout.payout_date.asc())
        ).all()
        payouts_by_group: Dict[str, GroupPayout] = {}
        for p in upcoming_payouts:
            if p.group_id not in payouts_by_group:
                payouts_by_group[p.group_id] = p

        # -------------------------------------------------------------
        # Assemble In-Memory Responses in O(N) CPU time
        # -------------------------------------------------------------
        summaries: List[GroupListSummaryResponse] = []

        for group in groups:
            gid = group.group_id
            tot_members = member_counts.get(gid, 0)

            # Compute Rings in Memory
            group_obs = obs_by_group.get(gid, [])
            paid_count = 0
            missed_count = 0
            for ob in group_obs:
                if ob.status == "PAID" or (ob.amount_paid >= ob.amount_due and ob.amount_due > 0):
                    paid_count += 1
                elif ob.due_date and now_ms > ob.due_date:
                    missed_count += 1

            ring_status = RingStatus(
                total_expected_members=tot_members,
                paid_on_time_count=paid_count,
                missed_deadline_count=missed_count
            )

            # Compute Ticker Messages in Memory
            ticker_messages: List[ActionMessage] = []
            if group.type == "MERRY_GO_ROUND":
                next_p = payouts_by_group.get(gid)
                if next_p:
                    if next_p.user_id == user_id:
                        ticker_messages.append(ActionMessage(
                            text="Your payout turn is scheduled for this round",
                            type="USER_TURN_REMINDER",
                            has_blue_ticks=True,
                            is_alert=False
                        ))
                    else:
                        ticker_messages.append(ActionMessage(
                            text="A rotation turn is scheduled for this round",
                            type="PAYOUT_TURN",
                            has_blue_ticks=True,
                            is_alert=False
                        ))
                else:
                    ticker_messages.append(ActionMessage(
                        text="Active rotation cycle underway",
                        type="SYSTEM_STATUS",
                        has_blue_ticks=True,
                        is_alert=False
                    ))
            elif group.type in ["EVENT_COMMITTEE", "FUNDRAISER", "GOAL_SAVINGS"]:
                ticker_messages.append(ActionMessage(
                    text=f"Total collected: {group.total_balance:,} {group.currency}",
                    type="GOAL_PROGRESS",
                    has_blue_ticks=False,
                    is_alert=False
                ))
            elif group.type == "BILL_SPLIT":
                ticker_messages.append(ActionMessage(
                    text="Split obligation cycle due soon",
                    type="BILL_DUE",
                    has_blue_ticks=True,
                    is_alert=False
                ))

            if not ticker_messages:
                ticker_messages.append(ActionMessage(
                    text="No new updates in this group",
                    type="IDLE",
                    has_blue_ticks=True,
                    is_alert=False
                ))

            # Unread Count in Memory
            tot_msgs = total_msgs_map.get(gid, 0)
            read_msgs = read_msgs_map.get(gid, 0)
            unread_count = max(0, tot_msgs - read_msgs)

            # Latest Message Preview in Memory
            latest_msg = latest_msgs_by_group.get(gid)
            last_msg_summary: Optional[LastMessageSummary] = None
            last_activity_ts = group.updated_at

            if latest_msg:
                is_outgoing = (latest_msg.sender_id == user_id_str)
                if is_outgoing:
                    sender_name = "You"
                elif latest_msg.sender_id == "SYSTEM":
                    sender_name = "System"
                else:
                    sender_name = sender_names_map.get(latest_msg.sender_id, "Member")

                last_msg_summary = LastMessageSummary(
                    message_id=str(latest_msg.id) if latest_msg.id else None,
                    sender_id=latest_msg.sender_id,
                    sender_name=sender_name,
                    text=format_message_preview(latest_msg),
                    raw_text=latest_msg.message_text,
                    message_type=latest_msg.message_type,
                    media_type=latest_msg.media_type,
                    timestamp=latest_msg.created_at,
                    is_outgoing=is_outgoing,
                    status=latest_msg.status
                )
                if latest_msg.created_at > last_activity_ts:
                    last_activity_ts = latest_msg.created_at

            summaries.append(GroupListSummaryResponse(
                group_id=gid,
                group_name=group.name,
                group_type=group.type,
                avatar_url=group.group_image_url,
                ring_status=ring_status,
                action_messages=ticker_messages,
                unread_count=unread_count,
                last_activity_timestamp=last_activity_ts,
                last_message=last_msg_summary
            ))

        return summaries

    @classmethod
    def get_user_total_unread_count(
        cls,
        session: Session,
        user_id: uuid.UUID
    ) -> int:
        """
        Calculates total unread chat messages across all groups the user belongs to.
        Used for the bottom navigation badge.
        """
        user_id_str = str(user_id)
        group_ids = session.exec(
            select(GroupMembership.group_id).where(
                GroupMembership.user_id == user_id,
                GroupMembership.status == "ACTIVE"
            )
        ).all()

        if not group_ids:
            return 0

        total_msgs = session.exec(
            select(func.count(GroupChatMessage.id)).where(
                GroupChatMessage.group_id.in_(group_ids),
                GroupChatMessage.sender_id != user_id_str,
                GroupChatMessage.is_deleted == False
            )
        ).one() or 0

        read_msgs = session.exec(
            select(func.count(GroupChatReadReceipt.message_id))
            .join(GroupChatMessage, GroupChatMessage.id == GroupChatReadReceipt.message_id)
            .where(
                GroupChatMessage.group_id.in_(group_ids),
                GroupChatReadReceipt.user_id == user_id_str
            )
        ).one() or 0

        return max(0, total_msgs - read_msgs)

    @classmethod
    def calculate_group_ring(
        cls,
        session: Session,
        group_id: str
    ) -> RingStatus:
        """
        Calculates the real-time RingStatus for a single group.
        Used by the direct deposit pipeline and real-time WebSocket broadcast.
        """
        now_ms = int(time.time() * 1000)

        # 1. Total active members
        total_members = session.exec(
            select(func.count(GroupMembership.id)).where(
                GroupMembership.group_id == group_id,
                GroupMembership.status == "ACTIVE"
            )
        ).one() or 0

        # 2. Get current cycle (default 1 if not rotating or not set)
        rot_detail = session.exec(
            select(RotatingGroupDetails).where(RotatingGroupDetails.group_id == group_id)
        ).first()
        target_cycle = rot_detail.current_cycle if (rot_detail and rot_detail.current_cycle) else 1

        # 3. Obligations for this cycle
        obligations = session.exec(
            select(MemberObligation).where(
                MemberObligation.group_id == group_id,
                MemberObligation.cycle_number == target_cycle
            )
        ).all()

        paid_count = 0
        missed_count = 0
        for ob in obligations:
            if ob.status == "PAID" or (ob.amount_paid >= ob.amount_due and ob.amount_due > 0):
                paid_count += 1
            elif ob.due_date and now_ms > ob.due_date:
                missed_count += 1

        return RingStatus(
            total_expected_members=total_members,
            paid_on_time_count=paid_count,
            missed_deadline_count=missed_count
        )

