from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlmodel import Session, select
import jwt
import json
import logging

from app.core.config import settings
from app.core.database import get_session
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.chat import GroupChatReadReceipt, GroupChatMessage
from app.services.websocket_manager import ws_manager
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/groups", tags=["Group Chat WebSockets"])

def get_ws_user(token: str, session: Session) -> User:
    """
    Authenticates a WebSocket connection using the JWT token passed in query parameters.
    Standard HTTP Bearer headers can't be used easily in native WebSockets.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            return None
        return session.get(User, user_id)
    except Exception:
        return None

@router.websocket("/{group_id}/chat/ws")
async def chat_websocket(
    websocket: WebSocket,
    group_id: str,
    token: str = Query(...),
    session: Session = Depends(get_session)
):
    # 1. Authenticate
    user = get_ws_user(token, session)
    if not user:
        await websocket.close(code=1008, reason="Invalid authentication token")
        return

    # 2. Verify Membership
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    
    if not membership:
        await websocket.close(code=1008, reason="You must be an active member to join this chat.")
        return

    # 3. Connect to Manager
    user_id_str = str(user.id)
    await ws_manager.connect(websocket, group_id, user_id_str)

    try:
        # 4. Listen for incoming real-time events (Typing, read receipts, etc.)
        while True:
            data = await websocket.receive_text()
            try:
                event = json.loads(data)
                event_type = event.get("event_type")
                
                # Handling Typing Indicators (Bypasses the Database for speed!)
                if event_type == "TYPING":
                    await ws_manager.broadcast_to_group(
                        group_id, 
                        {"event_type": "USER_TYPING", "user_id": user_id_str},
                        exclude_user_id=user_id_str
                    )
                elif event_type == "STOP_TYPING":
                    await ws_manager.broadcast_to_group(
                        group_id, 
                        {"event_type": "USER_STOP_TYPING", "user_id": user_id_str},
                        exclude_user_id=user_id_str
                    )
                elif event_type == "MESSAGE_READ":
                    message_id = event.get("message_id")
                    if message_id:
                        def _save_receipt():
                            from app.core.database import engine
                            # Instantiate a brand new session bound safely to this background thread
                            with Session(engine) as local_session:
                                try:
                                    # Ensure we don't duplicate receipts
                                    existing = local_session.exec(
                                        select(GroupChatReadReceipt).where(
                                            GroupChatReadReceipt.message_id == message_id,
                                            GroupChatReadReceipt.user_id == user.id
                                        )
                                    ).first()
                                    
                                    if not existing:
                                        receipt = GroupChatReadReceipt(
                                            message_id=message_id,
                                            user_id=user.id,
                                            group_id=group_id
                                        )
                                        local_session.add(receipt)
                                        local_session.commit()
                                except Exception as e:
                                    logger.error(f"Failed to save read receipt: {e}")
                                    local_session.rollback()

                        # Run the DB write safely in a thread-isolated context
                        loop = asyncio.get_running_loop()
                        await loop.run_in_executor(None, _save_receipt)
                        
                        # Broadcast the blue tick to everyone else in the chat instantly
                        await ws_manager.broadcast_to_group(
                            group_id,
                            {"event_type": "MESSAGE_READ", "message_id": message_id, "user_id": user_id_str},
                            exclude_user_id=user_id_str
                        )
                    
            except json.JSONDecodeError:
                logger.warning("Received invalid JSON over WebSocket")
                
    except WebSocketDisconnect:
        # Client dropped connection (app closed, internet died)
        await ws_manager.disconnect(websocket, group_id, user_id_str)
