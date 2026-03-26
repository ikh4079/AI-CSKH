import json

from sqlalchemy.orm import Session

from app.models.chat_log import ChatLog


class ChatLogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        trace_id: str,
        session_id: str,
        user_id: str,
        query: str,
        response: str,
        tool_calls: list[str],
    ) -> ChatLog:
        record = ChatLog(
            trace_id=trace_id,
            session_id=session_id,
            user_id=user_id,
            query=query,
            response=response,
            tool_calls=json.dumps(tool_calls, ensure_ascii=False),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

