import json
import uuid
from datetime import datetime
from pathlib import Path

DATA_FILE = Path(__file__).parent.parent / "data" / "reminders.json"


def _load_reminders() -> list[dict]:
    if not DATA_FILE.exists():
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        DATA_FILE.write_text("[]")
        return []
    return json.loads(DATA_FILE.read_text())


def _save_reminders(reminders: list[dict]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(reminders, indent=2))


async def add_reminder(args: dict) -> dict:
    reminders = _load_reminders()
    entry = {
        "id": str(uuid.uuid4())[:8],
        "title": args["title"],
        "due": args.get("due", ""),
        "recurring": args.get("recurring", ""),
        "created": datetime.now().isoformat(),
    }
    reminders.append(entry)
    _save_reminders(reminders)
    return {"content": [{"type": "text", "text": f"Reminder added (id: {entry['id']}): {entry['title']} — due: {entry['due'] or 'no date'}"}]}


async def list_reminders(args: dict) -> dict:
    reminders = _load_reminders()
    filter_type = args.get("filter", "all")
    now = datetime.now().isoformat()

    if filter_type == "overdue":
        reminders = [r for r in reminders if r.get("due") and r["due"] < now]
    elif filter_type == "today":
        today = datetime.now().strftime("%Y-%m-%d")
        reminders = [r for r in reminders if r.get("due", "").startswith(today)]

    if not reminders:
        return {"content": [{"type": "text", "text": "No reminders found."}]}

    lines = []
    for r in reminders:
        due = r.get("due") or "no date"
        recurring = f" (recurring: {r['recurring']})" if r.get("recurring") else ""
        lines.append(f"- [{r['id']}] {r['title']} — due: {due}{recurring}")

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


async def remove_reminder(args: dict) -> dict:
    reminders = _load_reminders()
    before = len(reminders)
    reminders = [r for r in reminders if r["id"] != args["id"]]
    _save_reminders(reminders)

    if len(reminders) < before:
        return {"content": [{"type": "text", "text": f"Reminder {args['id']} removed."}]}
    return {"content": [{"type": "text", "text": f"No reminder found with id {args['id']}."}]}
