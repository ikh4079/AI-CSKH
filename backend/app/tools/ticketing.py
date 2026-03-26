import json
from datetime import datetime

from app.core.config import get_settings

settings = get_settings()


def create_ticket(summary: str, session_id: str) -> str:
    output_path = settings.resolve_path(settings.ticket_output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tickets = []
    if output_path.exists():
        tickets = json.loads(output_path.read_text(encoding="utf-8"))

    ticket_id = f"TCK-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    tickets.append(
        {
            "ticket_id": ticket_id,
            "session_id": session_id,
            "summary": summary,
            "created_at": datetime.utcnow().isoformat(),
        }
    )
    output_path.write_text(json.dumps(tickets, ensure_ascii=False, indent=2), encoding="utf-8")
    return ticket_id

