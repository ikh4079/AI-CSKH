import json
import os

from app.tools import order_lookup


def test_lookup_order_uses_configurable_prefix(tmp_path, monkeypatch):
    source = tmp_path / "orders.json"
    source.write_text(
        json.dumps(
            [
                {
                    "order_id": "OD2001",
                    "customer": "Test User",
                    "phone": "0900000000",
                    "address": "HCM",
                    "status": "cho xac nhan",
                    "items": [],
                    "total": 100000,
                    "payment_method": "COD",
                    "payment_status": "chua thanh toan",
                    "carrier": "",
                    "tracking_code": "",
                    "note": "",
                    "created_at": "2026-03-26T10:00:00+07:00",
                    "eta": "2026-03-28",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(order_lookup.settings, "order_source_path", str(source))
    monkeypatch.setattr(order_lookup.settings, "order_id_prefixes", ["OD"])
    monkeypatch.setattr(
        order_lookup,
        "ORDER_ID_PATTERN",
        order_lookup._compile_order_id_pattern(order_lookup.settings.order_id_prefixes),
    )
    monkeypatch.setattr(order_lookup, "_ORDER_CACHE", None)
    monkeypatch.setattr(order_lookup, "_ORDER_CACHE_MTIME", None)

    result = order_lookup.lookup_order("kiem tra don OD2001")

    assert result.matched is True
    assert result.order is not None
    assert result.order["order_id"] == "OD2001"


def test_load_orders_uses_cache_until_file_mtime_changes(tmp_path, monkeypatch):
    source = tmp_path / "orders.json"
    source.write_text(json.dumps([{"order_id": "DH1001"}]), encoding="utf-8")
    initial_stat = source.stat()

    monkeypatch.setattr(order_lookup.settings, "order_source_path", str(source))
    monkeypatch.setattr(order_lookup, "_ORDER_CACHE", None)
    monkeypatch.setattr(order_lookup, "_ORDER_CACHE_MTIME", None)

    first_load = order_lookup._load_orders()
    source.write_text(json.dumps([{"order_id": "DH1002"}]), encoding="utf-8")
    os.utime(source, (initial_stat.st_atime, initial_stat.st_mtime))
    second_load = order_lookup._load_orders()

    assert first_load == second_load
    assert second_load[0]["order_id"] == "DH1001"

    current_stat = source.stat()
    os.utime(source, (current_stat.st_atime, current_stat.st_mtime + 5))

    third_load = order_lookup._load_orders()

    assert third_load[0]["order_id"] == "DH1002"


def test_lookup_order_prefers_explicit_order_id_in_latest_query_over_active_context():
    result = order_lookup.lookup_order(
        "muon hoan tien don DH1004",
        (
            "Minh da kiem tra don DH1007. "
            "Don chua thanh toan nen khong co quy trinh hoan tien. "
            "Neu can, minh co the chuyen tiep cho nhan vien ho tro.\nok"
        ),
        "DH1007",
    )

    assert result.order is not None
    assert result.order["order_id"] == "DH1004"
    assert result.requested_action == "refund_request"
