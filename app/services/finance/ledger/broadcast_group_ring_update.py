from sqlmodel import Session


async def broadcast_group_ring_update(group_id: str, depositor_name: str, amount: int):
    """
    Pushes real-time RING_STATUS_UPDATED event over WebSockets to all connected group members.
    Advances the green arc and pushes the new action ticker message in 0ms.
    """
    from app.core.database import engine
    from app.services.websocket_manager import manager
    from app.services.group.dashboard_summary_service import GroupDashboardSummaryService

    with Session(engine) as session:
        ring = GroupDashboardSummaryService.calculate_group_ring(session, group_id)

        payload = {
            "event_type": "RING_STATUS_UPDATED",
            "group_id": group_id,
            "ring_status": ring.model_dump(),
            "new_action_message": {
                "text": f"{depositor_name} deposited {amount:,} UGX",
                "type": "RECENT_CONTRIBUTION",
                "has_blue_ticks": True,
                "is_alert": False
            }
        }
        await manager.broadcast_to_group(group_id=group_id, message=payload)
