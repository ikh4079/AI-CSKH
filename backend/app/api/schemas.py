from pydantic import BaseModel, Field
from typing import Any


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str = Field(min_length=1, max_length=128)
    user_id: str = Field(default="demo-user", min_length=1, max_length=128)


class ChatResponse(BaseModel):
    trace_id: str
    session_id: str
    answer: str
    tool_calls: list[str] = Field(default_factory=list)
    tool_payloads: list[dict[str, Any]] = Field(default_factory=list)


class SessionResetRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)


class SessionResetResponse(BaseModel):
    session_id: str
    reset: bool = True
