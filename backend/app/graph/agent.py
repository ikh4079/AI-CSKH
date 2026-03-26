from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.services.llm import llm_service
from app.services.memory import memory_store
from app.services.rag import rag_service
from app.services.safety import sanitize_user_input
from app.tools.order_lookup import lookup_order, reassess_order_result, should_infer_order_action
from app.tools.ticketing import create_ticket
from app.utils.text import normalize_text


class AgentState(TypedDict, total=False):
    session_id: str
    query: str
    clean_query: str
    flagged: bool
    context: str
    response: str
    tool_calls: list[str]
    order_lookup: dict[str, Any]
    ticket: dict[str, Any]
    tool_payloads: list[dict[str, Any]]
    needs_clarification: bool
    llm_request: dict[str, Any]
    response_source: str


async def sanitize_node(state: AgentState) -> AgentState:
    cleaned, flagged = sanitize_user_input(state["query"])
    return {
        "clean_query": cleaned,
        "flagged": flagged,
        "tool_calls": [],
        "tool_payloads": [],
        "needs_clarification": False,
    }


async def retrieve_node(state: AgentState) -> AgentState:
    context = rag_service.format_context(state["clean_query"])
    return {"context": context}


def _serialize_order_lookup(order_lookup: dict[str, Any]) -> str:
    order = order_lookup.get("order") or {}
    if not order:
        return order_lookup.get("tool_message", "")
    return "\n".join(
        filter(
            None,
            [
                order_lookup.get("tool_message"),
                f"Hành động suy luận: {order_lookup.get('requested_action')}",
                f"Nguồn quyết định: {order_lookup.get('decision_source')}",
                f"Độ tin cậy: {order_lookup.get('decision_confidence')}",
                f"Lý do suy luận: {order_lookup.get('reasoning')}",
                f"Khả năng xử lý: {order_lookup.get('eligibility')}",
                f"Bước tiếp theo đề xuất: {order_lookup.get('next_step')}",
            ],
        )
    )


def _clarification_question(order_lookup: dict[str, Any]) -> str:
    order = order_lookup.get("order") or {}
    order_id = order.get("order_id", "đơn này")
    return (
        f"Mình đã tìm thấy {order_id}, nhưng chưa đủ chắc để tự xử lý tiếp. "
        "Bạn muốn mình kiểm tra trạng thái, yêu cầu giao lại, hủy đơn hay hỗ trợ hoàn tiền?"
    )


def _build_order_response(order_lookup: dict[str, Any]) -> str | None:
    tool_message = order_lookup.get("tool_message", "")
    if not order_lookup.get("order"):
        return tool_message or None

    requested_action = order_lookup.get("requested_action")
    eligibility = order_lookup.get("eligibility")
    order = order_lookup["order"]
    order_id = order["order_id"]

    if requested_action == "reschedule_delivery":
        if eligibility == "eligible":
            return (
                f"Mình đã kiểm tra đơn {order_id}. Đơn đang ở trạng thái {order['status']}. "
                "Mình đã tạo ticket giao lại để nhân viên tiếp nhận."
            )
        if eligibility == "review_needed":
            return (
                f"Mình đã kiểm tra đơn {order_id}. Đơn hiện {order['status']}. "
                "Cần kiểm tra thêm với đơn vị vận chuyển trước khi chốt giao lại."
            )
        return (
            f"Mình đã kiểm tra đơn {order_id}. Trạng thái hiện tại là {order['status']}, "
            "nên chưa thể xử lý giao lại trực tiếp."
        )

    if requested_action == "cancel_order":
        if eligibility == "eligible":
            return (
                f"Mình đã kiểm tra đơn {order_id}. Đơn vẫn có thể hủy ở trạng thái {order['status']}. "
                "Mình đã tạo ticket để bộ phận hỗ trợ xử lý."
            )
        return (
            f"Mình đã kiểm tra đơn {order_id}. Đơn hiện {order['status']}, "
            "nên cần nhân viên kiểm tra thêm trước khi xác nhận hủy."
        )

    if requested_action == "refund_request":
        if eligibility == "eligible":
            return (
                f"Mình đã kiểm tra đơn {order_id}. Đơn đủ điều kiện tiếp nhận yêu cầu hoàn tiền. "
                "Mình đã tạo ticket để bộ phận hỗ trợ xử lý."
            )
        return (
            f"Mình đã kiểm tra đơn {order_id}. {order_lookup.get('next_step')} "
            "Nếu cần, mình có thể chuyển tiếp cho nhân viên hỗ trợ."
        )

    return tool_message or None


def _should_auto_create_ticket(order_lookup: dict[str, Any]) -> bool:
    requested_action = order_lookup.get("requested_action")
    eligibility = order_lookup.get("eligibility")
    return (
        not order_lookup.get("needs_clarification")
        and requested_action in {"reschedule_delivery", "cancel_order", "refund_request"}
        and eligibility == "eligible"
    )


def _build_ticket_summary(order_lookup: dict[str, Any]) -> str:
    order = order_lookup.get("order") or {}
    return (
        f"Yêu cầu {order_lookup.get('requested_action')} cho đơn {order.get('order_id', 'N/A')} - "
        f"khách {order.get('customer', 'N/A')}"
    )


async def tool_node(state: AgentState) -> AgentState:
    tool_calls: list[str] = list(state.get("tool_calls", []))
    tool_payloads: list[dict[str, Any]] = list(state.get("tool_payloads", []))
    clean_query = state["clean_query"]
    memory = memory_store.get(state["session_id"])
    active_order_id = memory_store.get_active_order_id(state["session_id"])
    history = memory.load_memory_variables({}).get("history", [])
    conversation_context = "\n".join(
        getattr(message, "content", "") for message in history[-6:] if getattr(message, "content", "")
    )

    try:
        order_result = lookup_order(clean_query, conversation_context, active_order_id)
    except Exception:
        return {
            "context": state.get("context", ""),
            "tool_calls": tool_calls,
            "tool_payloads": tool_payloads,
        }

    if order_result.matched:
        decision_source = "heuristic"
        decision_confidence = float(order_result.confidence) / 100 if order_result.confidence else 0.0
        reasoning = "Fallback heuristic from local rules."
        needs_clarification = False

        if should_infer_order_action(clean_query, order_result):
            try:
                decision = await llm_service.infer_order_action(
                    query=clean_query,
                    conversation_context=conversation_context,
                    order_snapshot=order_result.order,
                    fallback_action=order_result.requested_action,
                )
                order_result = reassess_order_result(order_result, decision.requested_action)
                decision_source = "llm"
                decision_confidence = decision.confidence
                reasoning = decision.reasoning
                needs_clarification = decision.confidence < 0.6
            except Exception:
                pass

        tool_calls.append("file_search.order_lookup")
        order_payload = {
            "type": "order_lookup",
            "tool": "file_search.order_lookup",
            "tool_message": order_result.tool_message,
            "summary": order_result.summary,
            "requested_action": order_result.requested_action,
            "next_step": order_result.next_step,
            "eligibility": order_result.eligibility,
            "order": order_result.order,
            "confidence": decision_confidence,
            "decision_confidence": decision_confidence,
            "decision_source": decision_source,
            "reasoning": reasoning,
            "needs_clarification": needs_clarification,
        }
        tool_payloads.append(order_payload)
        result: AgentState = {
            "context": "\n".join(filter(None, [state.get("context", ""), _serialize_order_lookup(order_payload)])),
            "tool_calls": tool_calls,
            "order_lookup": order_payload,
            "tool_payloads": tool_payloads,
            "needs_clarification": needs_clarification,
        }
        if order_result.order and order_result.order.get("order_id"):
            memory_store.set_active_order_id(state["session_id"], order_result.order["order_id"])

        if _should_auto_create_ticket(order_payload):
            try:
                ticket_id = create_ticket(_build_ticket_summary(order_payload), state["session_id"])
                ticket_payload = {
                    "type": "ticket",
                    "tool": "ticket.create",
                    "ticket_id": ticket_id,
                    "requested_action": order_payload.get("requested_action"),
                    "order_id": (order_payload.get("order") or {}).get("order_id"),
                    "message": f"Đã tạo ticket với mã {ticket_id}.",
                }
                tool_calls.append("ticket.create")
                tool_payloads.append(ticket_payload)
                result["tool_calls"] = tool_calls
                result["tool_payloads"] = tool_payloads
                result["ticket"] = ticket_payload
                result["context"] = "\n".join(filter(None, [result["context"], ticket_payload["message"]]))
            except Exception:
                pass
        return result

    lowered = normalize_text(clean_query)
    if "ticket" in lowered or "khieu nai" in lowered or "ho tro them" in lowered:
        try:
            ticket_id = create_ticket(clean_query, state["session_id"])
            tool_calls.append("ticket.create")
            ticket_payload = {
                "type": "ticket",
                "tool": "ticket.create",
                "ticket_id": ticket_id,
                "requested_action": "manual_support",
                "order_id": (state.get("order_lookup") or {}).get("order", {}).get("order_id"),
                "message": f"Đã tạo ticket hỗ trợ với mã {ticket_id}.",
            }
            tool_payloads.append(ticket_payload)
            return {
                "context": "\n".join(filter(None, [state.get("context", ""), ticket_payload["message"]])),
                "tool_calls": tool_calls,
                "ticket": ticket_payload,
                "tool_payloads": tool_payloads,
            }
        except Exception:
            return {"tool_calls": tool_calls, "tool_payloads": tool_payloads}

    return {"tool_calls": tool_calls, "tool_payloads": tool_payloads}


def generate_node(state: AgentState) -> AgentState:
    if state["flagged"]:
        return {
            "response_source": "safety",
            "response": (
                "Mình không làm theo yêu cầu thay đổi hoặc bỏ qua system prompt. "
                "Nếu cần hỗ trợ CSKH, hỏi trực tiếp về đơn hàng, chính sách hoặc ticket."
            ),
        }

    if state.get("needs_clarification") and state.get("order_lookup"):
        return {"response_source": "clarification", "response": _clarification_question(state["order_lookup"])}

    order_response = _build_order_response(state.get("order_lookup", {}))
    ticket = state.get("ticket")
    if order_response and ticket:
        return {
            "response_source": "tool",
            "response": f"{order_response}\n\n{ticket['message']} Nhân viên sẽ tiếp nhận và xử lý sớm.",
        }
    if order_response:
        return {"response_source": "tool", "response": order_response}
    if ticket:
        return {
            "response_source": "tool",
            "response": f"{ticket['message']} Nhân viên sẽ tiếp nhận và xử lý sớm.",
        }

    memory = memory_store.get(state["session_id"])
    history = memory.load_memory_variables({}).get("history", [])
    return {
        "response_source": "llm",
        "llm_request": {
            "history": history,
            "query": state["clean_query"],
            "context": state.get("context", ""),
        },
    }


def route_after_sanitize(state: AgentState) -> str:
    return "generate" if state.get("flagged") else "retrieve"


def build_agent():
    graph = StateGraph(AgentState)
    graph.add_node("sanitize", sanitize_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("tool", tool_node)
    graph.add_node("generate", generate_node)
    graph.add_edge(START, "sanitize")
    graph.add_conditional_edges("sanitize", route_after_sanitize, {"retrieve": "retrieve", "generate": "generate"})
    graph.add_edge("retrieve", "tool")
    graph.add_edge("tool", "generate")
    graph.add_edge("generate", END)
    return graph.compile()


agent_app = build_agent()
