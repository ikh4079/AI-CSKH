from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.core.config import get_settings


class SessionMemory:
    def __init__(self, window_size: int) -> None:
        self._messages: deque[BaseMessage] = deque(maxlen=max(window_size * 2, 2))

    def load_memory_variables(self, _: dict[str, Any]) -> dict[str, list[BaseMessage]]:
        return {"history": list(self._messages)}

    def save_context(self, inputs: dict[str, Any], outputs: dict[str, Any]) -> None:
        user_input = str(inputs.get("input", "")).strip()
        assistant_output = str(outputs.get("output", "")).strip()
        if user_input:
            self._messages.append(HumanMessage(content=user_input))
        if assistant_output:
            self._messages.append(AIMessage(content=assistant_output))


@dataclass
class SessionState:
    memory: SessionMemory
    expires_at: datetime
    active_order_id: str | None = None


class MemoryStore:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._sessions: dict[str, SessionState] = {}

    def _new_session(self) -> SessionState:
        now = datetime.utcnow()
        return SessionState(
            memory=SessionMemory(self.settings.memory_window_size),
            expires_at=now + timedelta(seconds=self.settings.memory_ttl_seconds),
        )

    def _get_session(self, session_id: str) -> SessionState:
        now = datetime.utcnow()
        session = self._sessions.get(session_id)
        if session is None or session.expires_at <= now:
            session = self._new_session()
            self._sessions[session_id] = session
        else:
            session.expires_at = now + timedelta(seconds=self.settings.memory_ttl_seconds)
        return session

    def get(self, session_id: str) -> SessionMemory:
        return self._get_session(session_id).memory

    def get_active_order_id(self, session_id: str) -> str | None:
        return self._get_session(session_id).active_order_id

    def set_active_order_id(self, session_id: str, order_id: str) -> None:
        session = self._get_session(session_id)
        session.active_order_id = order_id

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


memory_store = MemoryStore()
