import json
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.schemas import ChatRequest, ChatResponse, SessionResetRequest, SessionResetResponse
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine, get_db
from app.graph.agent import agent_app
from app.repositories.chat_logs import ChatLogRepository
from app.services.llm import llm_service
from app.services.memory import memory_store

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def run_agent(payload: ChatRequest) -> dict:
    trace_id = uuid.uuid4().hex
    result = await agent_app.ainvoke(
        {"query": payload.message, "session_id": payload.session_id},
        {"recursion_limit": settings.max_agent_steps},
    )
    return {
        "trace_id": trace_id,
        "response": result.get("response"),
        "tool_calls": result.get("tool_calls", []),
        "tool_payloads": result.get("tool_payloads", []),
        "response_source": result.get("response_source", "tool"),
        "llm_request": result.get("llm_request"),
    }


async def finalize_response(payload: ChatRequest, run_result: dict) -> tuple[str, str, list[str], list[dict]]:
    response_text = run_result.get("response")
    llm_request = run_result.get("llm_request")
    if response_text is None and llm_request:
        try:
            result = await llm_service.invoke(
                llm_request["history"],
                llm_request["query"],
                llm_request["context"],
            )
            response_text = result.content
        except Exception:
            response_text = "Xin lỗi hệ thống đang bận, thử lại sau ít phút."

    response_text = response_text or "Xin lỗi hiện tại tôi chưa tạo được phản hồi phù hợp."
    memory_store.get(payload.session_id).save_context({"input": payload.message}, {"output": response_text})
    return (
        run_result["trace_id"],
        response_text,
        run_result.get("tool_calls", []),
        run_result.get("tool_payloads", []),
    )


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    run_result = await run_agent(payload)
    trace_id, response_text, tool_calls, tool_payloads = await finalize_response(payload, run_result)
    ChatLogRepository(db).create(
        trace_id=trace_id,
        session_id=payload.session_id,
        user_id=payload.user_id,
        query=payload.message,
        response=response_text,
        tool_calls=tool_calls,
    )
    return ChatResponse(
        trace_id=trace_id,
        session_id=payload.session_id,
        answer=response_text,
        tool_calls=tool_calls,
        tool_payloads=tool_payloads,
    )


@app.post("/api/chat/reset", response_model=SessionResetResponse)
def reset_chat_session(payload: SessionResetRequest) -> SessionResetResponse:
    memory_store.clear(payload.session_id)
    return SessionResetResponse(session_id=payload.session_id)


@app.post("/api/chat/stream")
async def stream_chat(payload: ChatRequest, db: Session = Depends(get_db)):
    run_result = await run_agent(payload)
    trace_id = run_result["trace_id"]
    tool_calls = run_result.get("tool_calls", [])
    tool_payloads = run_result.get("tool_payloads", [])
    llm_request = run_result.get("llm_request")
    preset_response = run_result.get("response")

    async def event_stream() -> AsyncGenerator[str, None]:
        response_parts: list[str] = []
        if llm_request:
            try:
                async for chunk in llm_service.stream_completion(
                    llm_request["history"],
                    llm_request["query"],
                    llm_request["context"],
                ):
                    response_parts.append(chunk)
                    yield chunk
            except Exception:
                fallback = "Xin lỗi hệ thống đang bận, thử lại sau ít phút."
                response_parts.append(fallback)
                yield fallback
        else:
            text = preset_response or "Xin lỗi hiện tại tôi chưa tạo được phản hồi phù hợp."
            response_parts.append(text)
            yield text

        full_response = "".join(response_parts)
        memory_store.get(payload.session_id).save_context({"input": payload.message}, {"output": full_response})
        ChatLogRepository(db).create(
            trace_id=trace_id,
            session_id=payload.session_id,
            user_id=payload.user_id,
            query=payload.message,
            response=full_response,
            tool_calls=tool_calls,
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/plain; charset=utf-8",
        headers={
            "X-Accel-Buffering": "no",
            "X-Trace-Id": trace_id,
            "X-Tool-Calls": json.dumps(tool_calls),
            "X-Tool-Payloads": json.dumps(tool_payloads),
        },
    )
