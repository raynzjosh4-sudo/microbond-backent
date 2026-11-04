from typing import Optional, List, Dict, Any
from sqlmodel import Session, select, func, col
from sqlalchemy import desc, asc

from app.models.user.user import User
from app.models.group.core.group import Group
from app.models.group.core.group_membership import GroupMembership
from app.models.group.settings.group_visibility_settings import GroupVisibilitySettings
from app.models.group.settings.group_governance_settings import GroupGovernanceSettings
from app.models.group.settings.group_common_settings import GroupCommonSettings
from app.models.group.health.group_health import GroupHealth
from app.models.group.rotating.rotating_group_details import RotatingGroupDetails
from app.models.group.target_savings.target_savings_group_details import TargetSavingsGroupDetails
from app.schemas.explore_discovery import (
    ExploreGroupCard,
    ExploreFinancialTermsSummary,
    ExploreHealthSummary,
    ExploreGovernanceSummary,
    ExploreCallerStatus,
    ExploreDiscoveryResponse,
    ExploreCategoryCollection,
    ExploreCategoriesResponse,
    ExplorePreviewResponse,
)


class ExploreGroupService:
    @staticmethod
    def search_and_discover_groups(
        session: Session,
        current_user: Optional[User] = None,
        q: Optional[str] = None,
        type: Optional[str] = None,
        currency: Optional[str] = None,
        frequency: Optional[int] = None,
        min_contribution: Optional[float] = None,
        max_contribution: Optional[float] = None,
        hide_full: bool = True,
        eligible_only: bool = False,
        sort_by: str = "POPULAR",
        page: int = 1,
        page_size: int = 20,
    ) -> ExploreDiscoveryResponse:
        """
        Executes an authoritative search & discovery query across public, active groups.
        Filters out private, invite-only, critical-risk, and already-enrolled groups.
        """
        page = max(1, page)
        page_size = min(max(1, page_size), 50)

        # 1. Base Query with visibility & active gates
        query = (
            select(Group)
            .outerjoin(GroupVisibilitySettings, Group.group_id == GroupVisibilitySettings.group_id)
            .outerjoin(GroupHealth, Group.group_id == GroupHealth.group_id)
            .where(Group.status == "ACTIVE")
            .where(func.upper(Group.visibility) == "PUBLIC")
            .where(
                (GroupVisibilitySettings.invite_only_discoverability == False)
                | (GroupVisibilitySettings.invite_only_discoverability == None)
            )
            .where(
                (GroupHealth.risk_level != "CRITICAL")
                | (GroupHealth.risk_level == None)
            )
        )

        # 2. Exclude groups the caller is already a member of
        if current_user:
            already_member_gids = session.exec(
                select(GroupMembership.group_id).where(
                    GroupMembership.user_id == current_user.id,
                    GroupMembership.status.in_(["ACTIVE", "ADMIN"]),
                )
            ).all()
            if already_member_gids:
                query = query.where(col(Group.group_id).not_in(already_member_gids))

        # 3. Text search
        if q and q.strip():
            term = f"%{q.strip().lower()}%"
            query = query.where(
                func.lower(Group.name).like(term) | func.lower(Group.description).like(term)
            )

        # 4. Group type filter
        if type and type.strip():
            query = query.where(func.upper(Group.type) == type.strip().upper())

        # 5. Currency filter
        if currency and currency.strip():
            query = query.where(func.upper(Group.currency) == currency.strip().upper())

        # 6. Capacity filter
        if hide_full:
            query = query.where(
                (Group.max_members == None) | (Group.member_count < Group.max_members)
            )

        # 7. Sorting
        sort_by_upper = (sort_by or "POPULAR").upper()
        if sort_by_upper == "NEWEST":
            query = query.order_by(desc(Group.created_at))
        elif sort_by_upper == "OLDEST":
            query = query.order_by(asc(Group.created_at))
        else:  # Default POPULAR
            query = query.order_by(desc(Group.member_count), desc(Group.created_at))

        # 8. Fetch candidate groups
        all_candidate_groups = session.exec(query).all()
        
        # 9. Batch-load metadata for candidate groups
        candidate_gids = [g.group_id for g in all_candidate_groups]
        if not candidate_gids:
            return ExploreDiscoveryResponse(
                total=0,
                page=page,
                page_size=page_size,
                has_more=False,
                items=[],
            )

        gov_map = {
            gov.group_id: gov
            for gov in session.exec(
                select(GroupGovernanceSettings).where(col(GroupGovernanceSettings.group_id).in_(candidate_gids))
            ).all()
        }
        health_map = {
            h.group_id: h
            for h in session.exec(
                select(GroupHealth).where(col(GroupHealth.group_id).in_(candidate_gids))
            ).all()
        }
        rotating_map = {
            r.group_id: r
            for r in session.exec(
                select(RotatingGroupDetails).where(col(RotatingGroupDetails.group_id).in_(candidate_gids))
            ).all()
        }
        target_map = {
            t.group_id: t
            for t in session.exec(
                select(TargetSavingsGroupDetails).where(col(TargetSavingsGroupDetails.group_id).in_(candidate_gids))
            ).all()
        }
        common_map = {
            c.group_id: c
            for c in session.exec(
                select(GroupCommonSettings).where(col(GroupCommonSettings.group_id).in_(candidate_gids))
            ).all()
        }

        # Also check pending join requests for caller
        pending_gids_set = set()
        if current_user:
            pending_memberships = session.exec(
                select(GroupMembership.group_id).where(
                    GroupMembership.user_id == current_user.id,
                    GroupMembership.status == "PENDING_APPROVAL",
                )
            ).all()
            pending_gids_set = set(pending_memberships)

        cards: List[ExploreGroupCard] = []
        for g in all_candidate_groups:
            gid = g.group_id
            gov = gov_map.get(gid)
            health = health_map.get(gid)
            rot = rotating_map.get(gid)
            tgt = target_map.get(gid)
            common = common_map.get(gid)

            # Determine financial terms
            terms = ExploreFinancialTermsSummary()
            if g.type == "MERRY_GO_ROUND" and rot:
                terms.contribution_amount = rot.contribution_amount
                terms.collection_frequency_days = rot.collection_frequency_days
                terms.saving_days_per_cycle = rot.saving_days_per_cycle
                terms.expected_pool_per_cycle = rot.total_expected_pool_per_cycle
            elif g.type == "TARGET_SAVINGS" and tgt:
                terms.contribution_amount = float(tgt.contribution_amount) if tgt.contribution_amount else None
                terms.collection_frequency_days = tgt.collection_frequency_days
                terms.target_amount = float(tgt.target_amount) if tgt.target_amount else None
            elif common:
                terms.collection_frequency_days = common.collection_frequency_days

            # Filter by frequency if specified
            if frequency is not None and terms.collection_frequency_days != frequency:
                continue

            # Filter by contribution amount range if specified
            if min_contribution is not None and terms.contribution_amount is not None:
                if terms.contribution_amount < min_contribution:
                    continue
            if max_contribution is not None and terms.contribution_amount is not None:
                if terms.contribution_amount > max_contribution:
                    continue

            # Governance summary
            req_approval = bool(gov.requires_admin_approval if gov else False)
            min_kyc = gov.minimum_kyc_tier if gov else 1
            min_trust = gov.minimum_trust_score if gov else None
            req_guarantor = bool(gov.require_guarantors if gov else False)

            # Caller eligibility checks
            is_full = bool(g.max_members and g.member_count >= g.max_members)
            is_eligible = True
            ineligibility_reasons: List[str] = []

            if current_user:
                caller_kyc = getattr(current_user, "kyc_tier", 0) or 0
                caller_trust = getattr(current_user, "trust_score", None)
                if caller_trust is None:
                    caller_trust = 50

                if min_kyc > 0 and caller_kyc < min_kyc:
                    is_eligible = False
                    ineligibility_reasons.append(f"Requires Tier {min_kyc} KYC verification (you are Tier {caller_kyc})")

                if min_trust is not None and caller_trust < min_trust:
                    is_eligible = False
                    ineligibility_reasons.append(f"Requires minimum {min_trust} Trust Score (your score: {caller_trust})")

            if is_full:
                is_eligible = False
                ineligibility_reasons.append("Group has reached maximum capacity")

            if eligible_only and not is_eligible:
                continue

            health_summary = ExploreHealthSummary(
                health_grade=health.health_grade if health else "A+",
                risk_level=health.risk_level if health else "LOW",
                on_time_repayment_rate_pct=health.on_time_repayment_rate_pct if health else 100.0,
            )

            gov_summary = ExploreGovernanceSummary(
                requires_admin_approval=req_approval,
                minimum_kyc_tier=min_kyc,
                minimum_trust_score=min_trust,
                require_guarantor=req_guarantor,
            )

            has_pending = gid in pending_gids_set
            caller_status = ExploreCallerStatus(
                is_eligible=is_eligible,
                ineligibility_reasons=ineligibility_reasons,
                can_join_instantly=bool(is_eligible and not req_approval and not is_full),
                requires_approval=req_approval,
                has_pending_join_request=has_pending,
                is_member=False,
                mutual_contacts_count=0,
            )

            cards.append(
                ExploreGroupCard(
                    group_id=g.group_id,
                    name=g.name,
                    description=g.description or "",
                    group_image_url=g.group_image_url or "",
                    avatar_color=g.avatar_color or "Blue",
                    type=g.type,
                    currency=g.currency or "UGX",
                    member_count=g.member_count or 0,
                    max_members=g.max_members,
                    is_full=is_full,
                    created_at=g.created_at or 0,
                    financial_terms=terms,
                    health=health_summary,
                    governance=gov_summary,
                    caller_status=caller_status,
                )
            )

        total_items = len(cards)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_items = cards[start_idx:end_idx]
        has_more = end_idx < total_items

        return ExploreDiscoveryResponse(
            total=total_items,
            page=page,
            page_size=page_size,
            has_more=has_more,
            items=paginated_items,
        )

    @staticmethod
    def get_explore_categories(
        session: Session,
        current_user: Optional[User] = None,
    ) -> ExploreCategoriesResponse:
        """
        Returns curated collections of public groups across standard savings themes.
        """
        # 1. Trending Rotating Circles
        rotating_resp = ExploreGroupService.search_and_discover_groups(
            session=session,
            current_user=current_user,
            type="MERRY_GO_ROUND",
            sort_by="POPULAR",
            page_size=6,
        )

        # 2. Goal & Target Savings
        target_resp = ExploreGroupService.search_and_discover_groups(
            session=session,
            current_user=current_user,
            type="TARGET_SAVINGS",
            sort_by="POPULAR",
            page_size=6,
        )

        # 3. High Trust / Grade A+ Circles
        all_resp = ExploreGroupService.search_and_discover_groups(
            session=session,
            current_user=current_user,
            sort_by="POPULAR",
            page_size=15,
        )
        grade_a_items = [item for item in all_resp.items if item.health.health_grade in ["A+", "A"]][:6]

        # 4. Open Starter Circles (Tier 1 Friendly)
        starter_items = [
            item for item in all_resp.items
            if item.governance.minimum_kyc_tier <= 1
            and not item.governance.require_guarantor
            and item.caller_status.is_eligible
        ][:6]

        categories = [
            ExploreCategoryCollection(
                id="trending_rotating",
                title="Trending Rotating Circles",
                description="Fast-moving Merry-Go-Round chamas with verified payout rotations.",
                badge_label="Popular",
                count=rotating_resp.total,
                groups=rotating_resp.items,
            ),
            ExploreCategoryCollection(
                id="goal_savings",
                title="Goal & Target Savings",
                description="Save collectively towards fixed milestones and projects.",
                badge_label="Goals",
                count=target_resp.total,
                groups=target_resp.items,
            ),
            ExploreCategoryCollection(
                id="high_trust_circles",
                title="Top Rated & Grade A+ Circles",
                description="Groups maintaining over 95% on-time repayment history.",
                badge_label="Verified",
                count=len(grade_a_items),
                groups=grade_a_items,
            ),
            ExploreCategoryCollection(
                id="starter_friendly",
                title="Open Starter Circles",
                description="Accessible groups requiring basic phone KYC and no guarantors.",
                badge_label="Easy Join",
                count=len(starter_items),
                groups=starter_items,
            ),
        ]

        return ExploreCategoriesResponse(categories=categories)

    @staticmethod
    def get_explore_group_preview(
        group_id: str,
        session: Session,
        current_user: Optional[User] = None,
    ) -> Optional[ExplorePreviewResponse]:
        """
        Returns an enriched preview of a discoverable public group.
        """
        group = session.exec(
            select(Group).where(Group.group_id == group_id, Group.status == "ACTIVE")
        ).first()
        if not group or (group.visibility or "").upper() != "PUBLIC":
            return None

        vis = session.exec(
            select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group.group_id)
        ).first()
        if vis and vis.invite_only_discoverability:
            return None

        # Discover single item using the primary search
        resp = ExploreGroupService.search_and_discover_groups(
            session=session,
            current_user=current_user,
            q=group.name,
            hide_full=False,
            page_size=10,
        )
        matched_card = next((c for c in resp.items if c.group_id == group.group_id), None)
        if not matched_card:
            return None

        # Fetch creator name
        creator = session.get(User, group.created_by_user_id)
        creator_name = creator.full_name if creator else "Admin"

        # Check strategy if rotating
        payout_strat = None
        cycle_summary = None
        if group.type == "MERRY_GO_ROUND":
            rot = session.exec(
                select(RotatingGroupDetails).where(RotatingGroupDetails.group_id == group.group_id)
            ).first()
            if rot:
                payout_strat = rot.payout_order_strategy
                cycle_summary = f"Cycle {rot.current_cycle} (Day {rot.current_saving_day} of {rot.saving_days_per_cycle or '?'})"

        # Checklist for user requirements
        checklist = []
        user_kyc = getattr(current_user, "kyc_tier", 0) if current_user else 0
        user_trust = getattr(current_user, "trust_score", 50) if current_user else 50
        min_kyc = matched_card.governance.minimum_kyc_tier
        min_trust = matched_card.governance.minimum_trust_score

        checklist.append({
            "requirement": f"Tier {min_kyc} KYC Verification",
            "satisfied": bool(user_kyc >= min_kyc),
            "current_value": f"Tier {user_kyc}",
            "required_value": f"Tier {min_kyc}",
        })

        if min_trust is not None:
            checklist.append({
                "requirement": f"Minimum {min_trust} Trust Score",
                "satisfied": bool(user_trust >= min_trust),
                "current_value": str(user_trust),
                "required_value": str(min_trust),
            })

        checklist.append({
            "requirement": "Group Membership Capacity",
            "satisfied": not matched_card.is_full,
            "current_value": f"{matched_card.member_count} members",
            "required_value": f"Max {matched_card.max_members or 'Unlimited'}",
        })

        return ExplorePreviewResponse(
            group=matched_card,
            creator_name=creator_name,
            payout_order_strategy=payout_strat,
            cycle_summary=cycle_summary,
            join_requirements_checklist=checklist,
        )
