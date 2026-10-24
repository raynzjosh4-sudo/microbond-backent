
from fastapi import APIRouter
from .rotating.rotating_endpoints import router as rotating_router
from .target_savings import router as target_savings_router
from .fundraiser import router as fundraiser_router
from .shared_wallet import router as shared_wallet_router
from .welfare_fund import router as welfare_fund_router
from .event_committee import router as event_committee_router
from .investment_club import router as investment_club_router
from .association_dues import router as association_dues_router
from .bill_split import router as bill_split_router
from .settings.update_general import router as settings_router
from .settings.update_group_profile import router as update_group_profile_router
from .settings.update_privacy import router as privacy_router
from .settings.update_permissions import router as permissions_router
from .settings.update_financial import router as financial_settings_router
from .settings.update_governance import router as governance_settings_router
from .join.join_request import router as join_router
from .join.generate_invite_link import router as guarantor_router
from .membership.update_membership import router as membership_router
from .membership.list_members import router as list_members_router
from .membership.payout_destination import router as payout_destination_router
from .membership.payment_method import router as group_payment_method_router
from .membership.proxy_contributor import router as proxy_contributor_router
from .membership.leave_group import router as leave_group_router
from .membership.export_data import router as export_data_router
from .membership.add_member import router as add_member_router
from .membership.administration import router as member_admin_router
from .report.submit_report import router as report_group_router
from .rotating.turn_swaps import router as turn_swaps_router
from .rotating.admin_payout_order import router as admin_payout_order_router
from .membership.health_rating import router as health_rating_router
from .membership.vouching import router as vouching_router
from .membership.sms_preferences import router as sms_preferences_router
from .settings.update_communication import router as communication_settings_router
from .settings.update_transaction_messages import router as transaction_messages_router
from .settings.update_reports import router as report_settings_router
from .settings.update_milestones import router as milestone_settings_router
from .settings.update_payout_visibility import router as payout_visibility_router
from .settings.update_governance_visibility import router as governance_visibility_router
from .settings.update_trust_visibility import router as trust_visibility_router
from .settings.update_liquidity_visibility import router as liquidity_visibility_router
from .settings.update_records_visibility import router as records_visibility_router
from .settings.update_transaction_visibility import router as transaction_visibility_router
from .settings.update_reminders_visibility import router as reminders_visibility_router
from .settings.update_liquidity import router as liquidity_settings_router
from .settings.update_milestones_visibility import router as milestones_visibility_router
from .settings.update_member_visibility import router as member_visibility_router
from .settings.manifest import router as settings_manifest_router
from .settings.get_settings import router as get_settings_router
from .settings.get_financial_settings import router as get_financial_settings_router
from .settings.goal_controls import router as goal_controls_router
from .settings.escrow_lock import router as escrow_lock_router
from .settings.multisig_roster import router as multisig_roster_router
from .membership.statement import router as statement_router
from .membership.savings_growth import router as savings_growth_router
from .report.weekly_report import router as weekly_report_router
from .report.dashboard_analytics import router as dashboard_analytics_router
from .report.universal_analytics import router as universal_analytics_router
from .report.analytics_series import router as analytics_series_router
from .chat.media import router as chat_media_router
from .chat.get_group_media import router as group_media_gallery_router
from .chat.messages import router as chat_messages_router
from .chat.websocket import router as chat_websocket_router
from .chat.polls import router as chat_polls_router
from .settings.audit_report_delivery import router as audit_report_delivery_router
from .settings.upload_group_image import router as upload_group_image_router
from .dashboard_summary import router as dashboard_summary_router
from .deposit_pipeline import router as deposit_pipeline_router
from .deposits.daily_deposit_widget import router as daily_deposit_widget_router

from .create_group import router as create_group_router

router = APIRouter()
router.include_router(create_group_router)
router.include_router(audit_report_delivery_router)
router.include_router(dashboard_summary_router)
router.include_router(deposit_pipeline_router)
router.include_router(daily_deposit_widget_router)

router.include_router(rotating_router)
router.include_router(target_savings_router)
router.include_router(fundraiser_router)
router.include_router(shared_wallet_router)
router.include_router(welfare_fund_router)
router.include_router(event_committee_router)
router.include_router(investment_club_router)
router.include_router(association_dues_router)
router.include_router(bill_split_router)
router.include_router(settings_router)
router.include_router(update_group_profile_router)
router.include_router(upload_group_image_router)
router.include_router(privacy_router)
router.include_router(permissions_router)
router.include_router(financial_settings_router)
router.include_router(governance_settings_router)
router.include_router(join_router)
router.include_router(guarantor_router)
router.include_router(membership_router)
router.include_router(savings_growth_router)
router.include_router(list_members_router)
router.include_router(payout_destination_router)
router.include_router(group_payment_method_router)
router.include_router(proxy_contributor_router)
router.include_router(export_data_router)
router.include_router(leave_group_router)
router.include_router(add_member_router)
router.include_router(member_admin_router)
router.include_router(report_group_router)
router.include_router(turn_swaps_router)
router.include_router(admin_payout_order_router)
router.include_router(health_rating_router)
router.include_router(vouching_router)
router.include_router(sms_preferences_router)
router.include_router(communication_settings_router)
router.include_router(transaction_messages_router)
router.include_router(report_settings_router)
router.include_router(milestone_settings_router)
router.include_router(payout_visibility_router)
router.include_router(governance_visibility_router)
router.include_router(trust_visibility_router)
router.include_router(liquidity_visibility_router)
router.include_router(records_visibility_router)
router.include_router(transaction_visibility_router)
router.include_router(reminders_visibility_router)
router.include_router(liquidity_settings_router)
router.include_router(milestones_visibility_router)
router.include_router(member_visibility_router)
router.include_router(settings_manifest_router)
router.include_router(get_settings_router)
router.include_router(get_financial_settings_router)
router.include_router(goal_controls_router)
router.include_router(escrow_lock_router)
router.include_router(multisig_roster_router)
router.include_router(statement_router)
router.include_router(weekly_report_router)
router.include_router(dashboard_analytics_router)
router.include_router(universal_analytics_router)
router.include_router(analytics_series_router)
router.include_router(chat_media_router)
router.include_router(group_media_gallery_router)
router.include_router(chat_messages_router)
router.include_router(chat_websocket_router)
router.include_router(chat_polls_router)
