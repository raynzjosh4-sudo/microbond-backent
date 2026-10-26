import json
import logging
import asyncio
from typing import Dict, List, Optional
from fastapi import WebSocket

# Try to import Redis for cross-worker scaling
try:
    import redis.asyncio as redis
except ImportError:
    redis = None

from app.core.config import settings

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Maps group_id -> user_id -> List of WebSockets (local to this worker process)
        self.active_connections: Dict[str, Dict[str, List[WebSocket]]] = {}
        
        # Redis PubSub resources for horizontal scaling across multiple Gunicorn workers
        self.redis_client: Optional['redis.Redis'] = None
        self.pubsub = None
        self.is_redis_connected = False
        self._listener_task = None
        self._redis_last_failure_time: float = 0.0
        self._redis_retry_cooldown: float = 30.0

    async def connect_redis(self):
        """Initialize Redis connection for cross-worker broadcasting"""
        if self.is_redis_connected or redis is None:
            return
            
        import time
        now = time.time()
        if now - self._redis_last_failure_time < self._redis_retry_cooldown:
            return
            
        try:
            redis_url = getattr(settings, "REDIS_URL", None)
            if not redis_url:
                return
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=1.5,
                socket_timeout=1.5
            )
            # Ping to test connection
            await self.redis_client.ping()
            self.pubsub = self.redis_client.pubsub()
            self.is_redis_connected = True
            logger.info("Successfully connected to Redis for WebSocket Pub/Sub")
            
            # Start background task to listen to incoming messages from other workers
            if self._listener_task is None:
                self._listener_task = asyncio.create_task(self._listen_to_redis())
            
        except Exception as e:
            self._redis_last_failure_time = now
            logger.warning(f"Could not connect to Redis for WebSockets. Falling back to in-memory mode. Error: {e}")
            self.is_redis_connected = False
            if self.redis_client:
                try:
                    await self.redis_client.close()
                except Exception:
                    pass
            self.redis_client = None

    async def _listen_to_redis(self):
        """Background worker that listens for messages published by other Gunicorn workers"""
        try:
            await self.pubsub.psubscribe("chat:*")
            async for message in self.pubsub.listen():
                if message["type"] == "pmessage":
                    channel = message["channel"]
                    # channel format: chat:{group_id}
                    group_id = channel.split(":")[1]
                    data = message["data"]
                    
                    # We received a message from Redis! Broadcast it to all local websockets on this worker
                    await self._local_broadcast(group_id, data)
        except Exception as e:
            logger.error(f"Redis pubsub listener crashed: {e}")
            self.is_redis_connected = False

    async def connect(self, websocket: WebSocket, group_id: str, user_id: str):
        # Always try to ensure Redis is connected when a new user joins
        await self.connect_redis()
        
        await websocket.accept()
        if group_id not in self.active_connections:
            self.active_connections[group_id] = {}
        if user_id not in self.active_connections[group_id]:
            self.active_connections[group_id][user_id] = []
        
        self.active_connections[group_id][user_id].append(websocket)
        logger.info(f"User {user_id} connected to group {group_id} via WebSocket")
        
        # Broadcast that this user is now online
        await self.broadcast_to_group(group_id, {
            "event_type": "USER_ONLINE",
            "user_id": user_id
        }, exclude_user_id=user_id)

    async def disconnect(self, websocket: WebSocket, group_id: str, user_id: str):
        try:
            if group_id in self.active_connections and user_id in self.active_connections[group_id]:
                if websocket in self.active_connections[group_id][user_id]:
                    self.active_connections[group_id][user_id].remove(websocket)
                    
                    # If this was their last active device, broadcast they are offline
                    if not self.active_connections[group_id][user_id]:
                        del self.active_connections[group_id][user_id]
                        await self.broadcast_to_group(group_id, {
                            "event_type": "USER_OFFLINE",
                            "user_id": user_id
                        })
                        
                # Cleanup empty groups
                if not self.active_connections[group_id]:
                    del self.active_connections[group_id]
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")

    async def broadcast_to_group(self, group_id: str, message: dict, exclude_user_id: str = None):
        """
        Production Broadcast:
        If Redis is available, it publishes the message to the Redis channel so ALL workers get it.
        If running locally without Redis, it falls back to a local broadcast.
        """
        # Inject the excluded user ID into the payload so other workers know who to ignore
        if exclude_user_id:
            message["_exclude_user_id"] = exclude_user_id
            
        json_message = json.dumps(message, default=str)
        
        if self.is_redis_connected:
            try:
                # Publish to Redis channel. The _listen_to_redis task on ALL workers (including this one) 
                # will pick it up and route it to the actual websockets via _local_broadcast
                await self.redis_client.publish(f"chat:{group_id}", json_message)
            except Exception as e:
                logger.error(f"Failed to publish to Redis, falling back to local: {e}")
                await self._local_broadcast(group_id, json_message)
        else:
            # Fallback for local development
            await self._local_broadcast(group_id, json_message)

    async def _local_broadcast(self, group_id: str, json_message: str):
        """Actually sends the text over the physical WebSocket connections on this specific worker"""
        if group_id in self.active_connections:
            # Check if there is an exclusion rule
            try:
                data = json.loads(json_message)
                exclude_user_id = data.pop("_exclude_user_id", None)
                # Re-serialize without the internal routing flag
                final_json = json.dumps(data) if exclude_user_id else json_message
            except Exception:
                exclude_user_id = None
                final_json = json_message
                
            # Create a safe copy of the items to iterate over
            for user_id, websockets in list(self.active_connections[group_id].items()):
                if exclude_user_id and user_id == exclude_user_id:
                    continue
                
                for connection in websockets:
                    try:
                        await connection.send_text(final_json)
                    except Exception as e:
                        logger.error(f"Failed to send to user {user_id}: {e}")

    def broadcast_to_group_sync(self, group_id: str, message: dict, exclude_user_id: str = None):
        """Synchronously broadcast to group, safely handling running or stopped event loops."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.broadcast_to_group(group_id, message, exclude_user_id))
            else:
                loop.run_until_complete(self.broadcast_to_group(group_id, message, exclude_user_id))
        except Exception:
            try:
                asyncio.run(self.broadcast_to_group(group_id, message, exclude_user_id))
            except Exception as e:
                logger.warning(f"broadcast_to_group_sync failed: {e}")

    async def force_disconnect_user(self, user_id: str, reason: str = "Session invalidated"):
        """
        Immediately closes all active WebSocket connections for a user across all groups.
        Used when a user is banned, removed from a group, or their JWT is explicitly revoked.
        """
        for group_id in list(self.active_connections.keys()):
            if user_id in self.active_connections[group_id]:
                websockets = self.active_connections[group_id][user_id]
                for ws in websockets:
                    try:
                        await ws.close(code=1008, reason=reason)
                    except Exception:
                        pass
                
                # Cleanup state and broadcast offline event
                del self.active_connections[group_id][user_id]
                await self.broadcast_to_group(group_id, {
                    "event_type": "USER_OFFLINE",
                    "user_id": user_id
                })

# Global singleton to be imported by the API endpoints
ws_manager = ConnectionManager()
