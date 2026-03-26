from app.tools.order_lookup import OrderLookupResult, should_infer_order_action


def test_should_infer_order_action_skips_llm_for_confident_explicit_match():
    order_result = OrderLookupResult(
        matched=True,
        confidence=100,
        tool_message="",
        summary=None,
        requested_action="cancel_order",
        next_step=None,
        eligibility=None,
        order={"order_id": "DH1001"},
    )

    assert should_infer_order_action("toi muon huy don DH1001", order_result) is False


def test_should_infer_order_action_keeps_llm_for_ambiguous_latest_query():
    order_result = OrderLookupResult(
        matched=True,
        confidence=100,
        tool_message="",
        summary=None,
        requested_action="cancel_order",
        next_step=None,
        eligibility=None,
        order={"order_id": "DH1001"},
    )

    assert should_infer_order_action("don DH1001 gio xu ly sao", order_result) is True
