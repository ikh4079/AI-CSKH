from datetime import datetime, timedelta

from app.services.memory import MemoryStore


def test_memory_store_keeps_recent_history():
    store = MemoryStore()

    memory = store.get("session-1")
    memory.save_context({"input": "xin chao"}, {"output": "chao"})

    history = memory.load_memory_variables({})["history"]

    assert len(history) == 2
    assert history[0].content == "xin chao"
    assert history[1].content == "chao"


def test_memory_store_expires_session_and_clears_active_order():
    store = MemoryStore()

    memory = store.get("session-1")
    memory.save_context({"input": "don DH1001"}, {"output": "dang giao"})
    store.set_active_order_id("session-1", "DH1001")

    session = store._sessions["session-1"]
    session.expires_at = datetime.utcnow() - timedelta(seconds=1)

    refreshed_memory = store.get("session-1")
    refreshed_history = refreshed_memory.load_memory_variables({})["history"]

    assert refreshed_history == []
    assert store.get_active_order_id("session-1") is None


def test_memory_store_clear_removes_history_and_active_order():
    store = MemoryStore()

    memory = store.get("session-1")
    memory.save_context({"input": "don DH1004"}, {"output": "da hoan tien"})
    store.set_active_order_id("session-1", "DH1004")

    store.clear("session-1")

    refreshed_memory = store.get("session-1")
    refreshed_history = refreshed_memory.load_memory_variables({})["history"]

    assert refreshed_history == []
    assert store.get_active_order_id("session-1") is None
