import json
import re
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from app.core.config import get_settings
from app.utils.text import normalize_text

settings = get_settings()

_ORDER_CACHE: list[dict[str, Any]] | None = None
_ORDER_CACHE_MTIME: float | None = None


def _compile_order_id_pattern(prefixes: list[str]) -> re.Pattern[str]:
    normalized_prefixes = [re.escape(prefix.strip()) for prefix in prefixes if prefix.strip()]
    if not normalized_prefixes:
        normalized_prefixes = ["DH"]
    return re.compile(rf"\b(?:{'|'.join(normalized_prefixes)})\d{{4,}}\b", re.IGNORECASE)


ORDER_ID_PATTERN = _compile_order_id_pattern(settings.order_id_prefixes)
PHONE_PATTERN = re.compile(r"\b0\d{9,10}\b")

ORDER_INTENT_KEYWORDS = {
    "don",
    "don hang",
    "ma don",
    "kiem tra",
    "tra cuu",
    "chi tiet",
    "van don",
    "giao hang",
    "du kien",
    "chua nhan",
    "qua ngay",
    "thanh toan",
    "dia chi",
    "giao lai",
    "giao that bai",
    "cho xac nhan",
    "huy don",
    "hoan tien",
}

ACTION_PATTERNS = {
    "reschedule_delivery": ["giao lai", "ship lai", "muon giao", "giao tiep", "giao them lan nua"],
    "cancel_order": ["huy don", "muon huy", "khong muon nhan", "khong lay nua"],
    "refund_request": ["hoan tien", "muon hoan", "refund"],
    "status_check": ["kiem tra", "tra cuu", "trang thai", "chi tiet", "xem don"],
}


@dataclass
class OrderLookupResult:
    matched: bool
    confidence: int
    tool_message: str
    summary: str | None
    requested_action: str | None
    next_step: str | None
    eligibility: str | None
    order: dict[str, Any] | None


def _load_orders() -> list[dict[str, Any]]:
    global _ORDER_CACHE, _ORDER_CACHE_MTIME

    source = settings.resolve_path(settings.order_source_path)
    if not source.exists():
        return []
    try:
        current_mtime = source.stat().st_mtime
    except OSError:
        return []

    if _ORDER_CACHE is not None and _ORDER_CACHE_MTIME == current_mtime:
        return _ORDER_CACHE

    try:
        loaded = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(loaded, list):
        return []

    _ORDER_CACHE = loaded
    _ORDER_CACHE_MTIME = current_mtime
    return loaded


def _extract_identifiers(text: str) -> tuple[set[str], set[str]]:
    return {match.upper() for match in ORDER_ID_PATTERN.findall(text)}, set(PHONE_PATTERN.findall(text))


def _matches_explicit_identifiers(order: dict[str, Any], order_ids: set[str], phones: set[str]) -> bool:
    return order["order_id"].upper() in order_ids or str(order.get("phone", "")) in phones


def _format_currency(value: int | float) -> str:
    return f"{int(value):,}".replace(",", ".") + "đ"


def _format_datetime(value: str) -> str:
    if not value:
        return "Chưa có"
    try:
        return datetime.fromisoformat(value).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return value


def _format_items(items: list[dict[str, Any]]) -> str:
    if not items:
        return "Không có sản phẩm"
    return "; ".join(
        f"{item['name']} x{item['quantity']} ({_format_currency(item['price'])})" for item in items
    )


def _has_order_intent(query: str, conversation_context: str) -> bool:
    normalized_query = normalize_text(query)
    order_ids, phones = _extract_identifiers(f"{query}\n{conversation_context}")
    if order_ids or phones:
        return True
    return any(keyword in normalized_query for keyword in ORDER_INTENT_KEYWORDS)


def _detect_requested_action(query: str, conversation_context: str) -> str:
    normalized_query = normalize_text(query)
    normalized_context = normalize_text(conversation_context)

    for action in ("reschedule_delivery", "cancel_order", "refund_request"):
        if any(pattern in normalized_query for pattern in ACTION_PATTERNS[action]):
            return action

    for action in ("reschedule_delivery", "cancel_order", "refund_request"):
        if any(pattern in normalized_context for pattern in ACTION_PATTERNS[action]):
            return action

    if any(pattern in normalized_query for pattern in ACTION_PATTERNS["status_check"]):
        return "status_check"

    return "status_check"


def should_infer_order_action(query: str, result: OrderLookupResult) -> bool:
    if not result.order or not result.requested_action:
        return False

    normalized_query = normalize_text(query)
    explicit_action_signal = any(
        pattern in normalized_query for pattern in ACTION_PATTERNS.get(result.requested_action, [])
    )
    if result.confidence >= 90 and explicit_action_signal:
        return False
    return True


def _score_order(order: dict[str, Any], query: str, conversation_context: str, preferred_order_id: str | None) -> int:
    combined_raw = f"{query}\n{conversation_context}"
    normalized_combined = normalize_text(combined_raw)
    order_ids, phones = _extract_identifiers(combined_raw)
    score = 0

    order_id = order["order_id"].upper()
    if order_id in order_ids:
        score += 100
    if preferred_order_id and order_id == preferred_order_id.upper():
        score += 70

    phone = str(order.get("phone", ""))
    if phone and phone in phones:
        score += 90

    tracking_code = normalize_text(order.get("tracking_code", ""))
    if tracking_code and tracking_code in normalized_combined:
        score += 80

    customer = normalize_text(order.get("customer", ""))
    customer_tokens = [token for token in customer.split() if len(token) >= 2]
    score += sum(18 for token in customer_tokens if token in normalized_combined)

    address = normalize_text(order.get("address", ""))
    address_tokens = [token for token in address.split() if len(token) >= 4]
    score += sum(4 for token in address_tokens if token in normalized_combined)

    for item in order.get("items", []):
        item_tokens = [token for token in normalize_text(item.get("name", "")).split() if len(token) >= 3]
        score += sum(6 for token in item_tokens if token in normalized_combined)

    status = normalize_text(order.get("status", ""))
    payment_status = normalize_text(order.get("payment_status", ""))
    score += sum(8 for token in status.split() if len(token) >= 3 and token in normalized_combined)
    score += sum(5 for token in payment_status.split() if len(token) >= 3 and token in normalized_combined)

    if "qua ngay" in normalized_combined and order.get("eta"):
        score += 5
    if "giao lai" in normalized_combined and "giao that bai" in status:
        score += 20
    if "hoan tien" in normalized_combined and ("da huy" in status or "da hoan tien" in payment_status):
        score += 12

    return score


def _order_snapshot(order: dict[str, Any]) -> dict[str, Any]:
    return {
        "order_id": order["order_id"],
        "customer": order["customer"],
        "phone": order["phone"],
        "status": order.get("status", ""),
        "payment_status": order.get("payment_status", ""),
        "payment_method": order.get("payment_method", ""),
        "carrier": order.get("carrier", ""),
        "tracking_code": order.get("tracking_code", ""),
        "eta": order.get("eta", ""),
        "created_at": order.get("created_at", ""),
        "total": order.get("total", 0),
        "address": order.get("address", ""),
        "note": order.get("note", ""),
        "items": order.get("items", []),
    }


def _build_summary(order: dict[str, Any]) -> str:
    tracking = order.get("tracking_code") or "Chưa có"
    note = order.get("note") or "Không có"
    eta = _format_datetime(f"{order.get('eta', '')}T00:00:00+07:00" if order.get("eta") else "")
    created_at = _format_datetime(order.get("created_at", ""))
    return "\n".join(
        [
            f"Chi tiết đơn hàng {order['order_id']}:",
            f"- Khách hàng: {order['customer']} | SĐT: {order['phone']}",
            f"- Trạng thái: {order['status']}",
            f"- Dự kiến giao: {eta}",
            f"- Ngày tạo đơn: {created_at}",
            f"- Sản phẩm: {_format_items(order.get('items', []))}",
            f"- Tổng tiền: {_format_currency(order.get('total', 0))}",
            f"- Thanh toán: {order.get('payment_method', 'Chưa có')} | {order.get('payment_status', 'Chưa có')}",
            f"- Vận chuyển: {order.get('carrier') or 'Chưa có'} | Mã vận đơn: {tracking}",
            f"- Địa chỉ giao: {order.get('address', 'Chưa có')}",
            f"- Ghi chú: {note}",
        ]
    )


def _resolve_order_action(order: dict[str, Any], requested_action: str) -> tuple[str, str]:
    status = normalize_text(order.get("status", ""))
    payment_status = normalize_text(order.get("payment_status", ""))

    if requested_action == "reschedule_delivery":
        if "giao that bai" in status:
            return "eligible", "Có thể hỗ trợ tạo yêu cầu giao lại cho đơn này."
        if "dang giao" in status:
            return "review_needed", "Đơn đang giao, cần xác nhận thêm với đơn vị vận chuyển trước khi giao lại."
        return "not_applicable", "Đơn này hiện không ở trạng thái phù hợp để tạo yêu cầu giao lại."

    if requested_action == "cancel_order":
        if "cho xac nhan" in status or "cho lay hang" in status:
            return "eligible", "Có thể hỗ trợ tạo yêu cầu hủy đơn."
        if "dang giao" in status:
            return "review_needed", "Đơn đang giao, cần kiểm tra thêm trước khi xử lý hủy."
        return "not_applicable", "Đơn này không còn phù hợp để hủy trực tiếp."

    if requested_action == "refund_request":
        if ("da thanh toan" in payment_status or "da hoan tien" in payment_status) and (
            "da huy" in status or "giao that bai" in status
        ):
            return "eligible", "Có thể hỗ trợ chuyển yêu cầu hoàn tiền."
        if "chua thanh toan" in payment_status:
            return "not_applicable", "Đơn chưa thanh toán nên không có quy trình hoàn tiền."
        return "review_needed", "Cần kiểm tra thêm điều kiện hoàn tiền của đơn này."

    return "info_only", "Đã tra cứu thông tin đơn hàng."


def lookup_order(
    query: str,
    conversation_context: str = "",
    preferred_order_id: str | None = None,
) -> OrderLookupResult:
    if not _has_order_intent(query, conversation_context):
        return OrderLookupResult(False, 0, "", None, None, None, None, None)

    orders = _load_orders()
    if not orders:
        return OrderLookupResult(
            True,
            0,
            "Không tìm thấy dữ liệu đơn hàng trong file order.json.",
            None,
            None,
            "Yêu cầu người dùng kiểm tra lại file dữ liệu đơn hàng.",
            "missing_data",
            None,
        )

    query_order_ids, query_phones = _extract_identifiers(query)
    explicit_matches = [order for order in orders if _matches_explicit_identifiers(order, query_order_ids, query_phones)]
    if explicit_matches:
        orders = explicit_matches
        preferred_order_id = None

    ranked_orders = sorted(
        ((order, _score_order(order, query, conversation_context, preferred_order_id)) for order in orders),
        key=lambda item: item[1],
        reverse=True,
    )
    best_order, best_score = ranked_orders[0]
    second_score = ranked_orders[1][1] if len(ranked_orders) > 1 else 0

    if best_score <= 0:
        return OrderLookupResult(
            True,
            0,
            "Không xác định được đơn hàng cần tra cứu. Hãy cung cấp mã đơn, số điện thoại hoặc tên khách hàng.",
            None,
            None,
            "Yêu cầu người dùng cung cấp thêm thông tin nhận diện đơn hàng.",
            "not_found",
            None,
        )

    if best_score < 50 and best_score - second_score < 15:
        return OrderLookupResult(
            True,
            best_score,
            "Có nhiều đơn hàng gần giống nhau. Hãy gửi thêm mã đơn hoặc số điện thoại để mình kiểm tra chính xác.",
            None,
            None,
            "Yêu cầu người dùng làm rõ đơn hàng mục tiêu.",
            "ambiguous",
            None,
        )

    requested_action = _detect_requested_action(query, conversation_context)
    eligibility, next_step = _resolve_order_action(best_order, requested_action)

    return OrderLookupResult(
        True,
        best_score,
        _build_summary(best_order),
        _build_summary(best_order),
        requested_action,
        next_step,
        eligibility,
        _order_snapshot(best_order),
    )


def reassess_order_result(result: OrderLookupResult, requested_action: str) -> OrderLookupResult:
    if not result.order:
        return result
    eligibility, next_step = _resolve_order_action(result.order, requested_action)
    return replace(result, requested_action=requested_action, eligibility=eligibility, next_step=next_step)
