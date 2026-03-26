from collections.abc import AsyncGenerator
from typing import Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings

settings = get_settings()


def build_messages(history: list[BaseMessage], query: str, context: str) -> list[BaseMessage]:
    system_prompt = (
        "Ban la AI CSKH tieng Viet. Tra loi ngan gon, chinh xac, huu ich. "
        "Neu du lieu chua du thi noi ro thieu gi, khong bua. "
        "Uu tien knowledge base noi bo khi co context."
    )
    messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]
    messages.extend(history)
    if context:
        messages.append(SystemMessage(content=f"Ngu canh KB:\n{context}"))
    messages.append(HumanMessage(content=query))
    return messages


class OrderActionDecision(BaseModel):
    requested_action: Literal["status_check", "reschedule_delivery", "cancel_order", "refund_request"]
    confidence: float
    reasoning: str


class LLMService:
    def __init__(self) -> None:
        self.client = None
        if settings.openai_api_key:
            self.client = ChatOpenAI(
                model=settings.openai_model,
                api_key=settings.openai_api_key,
                timeout=settings.request_timeout_seconds,
                temperature=0.2,
            )

    def _fallback_message(self, context: str) -> AIMessage:
        fallback = context or "Chua co knowledge base phu hop cho cau hoi nay."
        return AIMessage(
            content=(
                "[Demo mode] Chua cau hinh OPENAI_API_KEY. "
                f"Tom tat thong tin kha dung: {fallback}"
            )
        )

    @retry(
        reraise=True,
        stop=stop_after_attempt(settings.max_llm_retries),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        retry=retry_if_exception_type(Exception),
    )
    async def invoke(self, history: list[BaseMessage], query: str, context: str) -> AIMessage:
        if self.client is None:
            return self._fallback_message(context)
        return await self.client.ainvoke(build_messages(history, query, context))

    @retry(
        reraise=True,
        stop=stop_after_attempt(settings.max_llm_retries),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        retry=retry_if_exception_type(Exception),
    )
    async def infer_order_action(
        self,
        *,
        query: str,
        conversation_context: str,
        order_snapshot: dict,
        fallback_action: str,
    ) -> OrderActionDecision:
        if self.client is None:
            return OrderActionDecision(
                requested_action=fallback_action,
                confidence=0.35,
                reasoning="Fallback heuristic.",
            )

        prompt = (
            "Ban la bo phan phan loai y dinh CSKH cho don hang.\n"
            "Chon dung mot action trong: status_check, reschedule_delivery, cancel_order, refund_request.\n"
            "Uu tien tin nhan moi nhat cua khach; lich su chat chi de bo tro.\n"
            "Tra ve dung schema requested_action, confidence, reasoning.\n\n"
            f"Tin nhan moi nhat:\n{query}\n\n"
            f"Ngu canh hoi thoai gan day:\n{conversation_context or '(none)'}\n\n"
            f"Thong tin don da khop:\n{order_snapshot}\n\n"
            f"Hanh dong fallback theo heuristic: {fallback_action}"
        )
        try:
            structured_client = self.client.with_structured_output(OrderActionDecision)
            return await structured_client.ainvoke([SystemMessage(content=prompt)])
        except Exception:
            return OrderActionDecision(
                requested_action=fallback_action,
                confidence=0.35,
                reasoning="LLM structured output failed, fallback to heuristic.",
            )

    async def stream_completion(
        self,
        history: list[BaseMessage],
        query: str,
        context: str,
    ) -> AsyncGenerator[str, None]:
        if self.client is None:
            yield self._fallback_message(context).content
            return

        async for chunk in self.client.astream(build_messages(history, query, context)):
            if isinstance(chunk.content, str) and chunk.content:
                yield chunk.content


llm_service = LLMService()
