from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Optional
from loguru import logger
import asyncio
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.user_connections: Dict[str, Dict[str, WebSocket]] = {}  # user_id -> {chat_id: websocket}

    async def connect(self, chat_id: str, websocket: WebSocket, user_id: Optional[str] = None):
        """Connect a WebSocket to a specific chat"""
        await websocket.accept()

        # Add to chat connections
        self.active_connections.setdefault(chat_id, []).append(websocket)

        # Track user connections if user_id provided
        if user_id:
            self.user_connections.setdefault(user_id, {})[chat_id] = websocket

        logger.info(f"WebSocket connected to chat {chat_id}" + (f" for user {user_id}" if user_id else ""))

    def disconnect(self, chat_id: str, websocket: WebSocket, user_id: Optional[str] = None):
        """Disconnect a WebSocket from a chat"""
        try:
            # Remove from chat connections
            if chat_id in self.active_connections:
                if websocket in self.active_connections[chat_id]:
                    self.active_connections[chat_id].remove(websocket)

                # Clean up empty chat connection list
                if not self.active_connections[chat_id]:
                    del self.active_connections[chat_id]

            # Remove from user connections
            if user_id and user_id in self.user_connections:
                if chat_id in self.user_connections[user_id]:
                    del self.user_connections[user_id][chat_id]

                # Clean up empty user connection dict
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]

            logger.info(f"WebSocket disconnected from chat {chat_id}" + (f" for user {user_id}" if user_id else ""))

        except Exception as e:
            logger.error(f"Error during WebSocket disconnect: {str(e)}")

    async def broadcast_to_chat(self, chat_id: str, message: dict, exclude_websocket: Optional[WebSocket] = None):
        """Broadcast message to all connections in a specific chat"""
        if chat_id not in self.active_connections:
            return

        # Create a copy of the list to avoid modification during iteration
        connections = self.active_connections[chat_id][:]
        dead_connections = []

        for websocket in connections:
            if websocket == exclude_websocket:
                continue

            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send message to WebSocket in chat {chat_id}: {str(e)}")
                dead_connections.append(websocket)

        # Clean up dead connections
        for dead_ws in dead_connections:
            self._remove_dead_connection(chat_id, dead_ws)

    async def send_to_user(self, user_id: str, chat_id: str, message: dict):
        """Send message to a specific user in a specific chat"""
        if user_id not in self.user_connections:
            return False

        if chat_id not in self.user_connections[user_id]:
            return False

        websocket = self.user_connections[user_id][chat_id]
        try:
            await websocket.send_json(message)
            return True
        except Exception as e:
            logger.warning(f"Failed to send message to user {user_id} in chat {chat_id}: {str(e)}")
            self._remove_dead_connection(chat_id, websocket, user_id)
            return False

    async def broadcast_to_user_chats(self, user_id: str, message: dict):
        """Broadcast message to all chats where user is connected"""
        if user_id not in self.user_connections:
            return

        user_chats = list(self.user_connections[user_id].keys())
        for chat_id in user_chats:
            await self.send_to_user(user_id, chat_id, message)

    def has_connections(self, chat_id: str) -> bool:
        """Check if a chat has any active connections"""
        return chat_id in self.active_connections and len(self.active_connections[chat_id]) > 0

    def get_connection_count(self, chat_id: str) -> int:
        """Get number of active connections for a chat"""
        return len(self.active_connections.get(chat_id, []))

    def get_active_chats(self) -> List[str]:
        """Get list of chat IDs with active connections"""
        return list(self.active_connections.keys())

    def get_user_active_chats(self, user_id: str) -> List[str]:
        """Get list of chat IDs where user has active connections"""
        return list(self.user_connections.get(user_id, {}).keys())

    def _remove_dead_connection(self, chat_id: str, websocket: WebSocket, user_id: Optional[str] = None):
        """Internal method to remove a dead connection"""
        try:
            # Remove from chat connections
            if chat_id in self.active_connections:
                if websocket in self.active_connections[chat_id]:
                    self.active_connections[chat_id].remove(websocket)

                if not self.active_connections[chat_id]:
                    del self.active_connections[chat_id]

            # Remove from user connections if user_id known
            if user_id and user_id in self.user_connections:
                if chat_id in self.user_connections[user_id]:
                    del self.user_connections[user_id][chat_id]

                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
            else:
                # If user_id not provided, search through all users
                for uid, chats in list(self.user_connections.items()):
                    for cid, ws in list(chats.items()):
                        if ws == websocket and cid == chat_id:
                            del chats[cid]
                            if not chats:
                                del self.user_connections[uid]
                            break

        except Exception as e:
            logger.error(f"Error removing dead connection: {str(e)}")

    async def ping_connections(self):
        """Ping all connections to check if they're alive (run this periodically)"""
        all_connections = []

        # Collect all connections
        for chat_id, connections in self.active_connections.items():
            for ws in connections:
                all_connections.append((chat_id, ws))

        # Ping each connection
        for chat_id, websocket in all_connections:
            try:
                await websocket.send_json({"type": "ping"})
            except Exception as e:
                logger.warning(f"Connection dead during ping in chat {chat_id}: {str(e)}")
                self._remove_dead_connection(chat_id, websocket)

    def get_stats(self) -> dict:
        """Get connection statistics"""
        total_connections = sum(len(connections) for connections in self.active_connections.values())
        return {
            "total_connections": total_connections,
            "active_chats": len(self.active_connections),
            "connected_users": len(self.user_connections),
            "chats_with_connections": {
                chat_id: len(connections)
                for chat_id, connections in self.active_connections.items()
            }
        }


# Global instance
ws_manager = ConnectionManager()

# Optional: Background task to clean up dead connections
async def cleanup_dead_connections():
    """Background task to periodically clean up dead connections"""
    while True:
        try:
            await ws_manager.ping_connections()
            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"Error in connection cleanup task: {str(e)}")
            await asyncio.sleep(60)


# asyncio.create_task(cleanup_dead_connections())
