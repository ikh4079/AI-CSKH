import asyncio

from app.services.llm import LLMService, OrderActionDecision


class FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeStructuredClient:
    def __init__(self, result: OrderActionDecision | Exception) -> None:
        self.result = result

    async def ainvoke(self, _: list) -> OrderActionDecision:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeClient:
    def __init__(self, content: str = "", structured_result: OrderActionDecision | Exception | None = None) -> None:
        self.content = content
        self.structured_result = structured_result

    async def ainvoke(self, _: list) -> FakeResponse:
        return FakeResponse(self.content)

    def with_structured_output(self, _: type[OrderActionDecision]) -> FakeStructuredClient:
        assert self.structured_result is not None
        return FakeStructuredClient(self.structured_result)


def test_infer_order_action_falls_back_when_structured_output_fails():
    service = LLMService()
    service.client = FakeClient(structured_result=ValueError("invalid schema"))

    result = asyncio.run(
        service.infer_order_action(
            query="toi muon huy don",
            conversation_context="",
            order_snapshot={"order_id": "DH1001"},
            fallback_action="cancel_order",
        )
    )

    assert result.requested_action == "cancel_order"
    assert result.confidence == 0.35
    assert "fallback" in result.reasoning.lower()


def test_infer_order_action_uses_structured_output():
    service = LLMService()
    service.client = FakeClient(
        structured_result=OrderActionDecision(
            requested_action="refund_request",
            confidence=0.91,
            reasoning="Khach muon hoan tien.",
        )
    )

    result = asyncio.run(
        service.infer_order_action(
            query="toi muon hoan tien",
            conversation_context="",
            order_snapshot={"order_id": "DH1002"},
            fallback_action="status_check",
        )
    )

    assert result.requested_action == "refund_request"
    assert result.confidence == 0.91
    assert result.reasoning == "Khach muon hoan tien."


def test_invoke_returns_demo_message_without_client():
    service = LLMService()
    service.client = None

    result = asyncio.run(service.invoke([], "don hang cua toi", "ngu canh test"))

    assert "[Demo mode]" in result.content
    assert "ngu canh test" in result.content
