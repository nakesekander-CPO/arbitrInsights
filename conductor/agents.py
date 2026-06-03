from datetime import datetime

import anthropic

from tools.scheduler_tools import add_reminder, list_reminders, remove_reminder

_EMAIL_SYSTEM = """You are an email assistant. You help the user manage their Gmail inbox.

Your capabilities:
- Search and read emails
- Summarize email threads concisely
- Draft reply emails in a professional tone
- Triage inbox by importance

Guidelines:
- Always summarize before showing full email content
- When drafting replies, match the tone of the conversation
- Never send emails without explicit user confirmation
- Group related emails by thread when summarizing"""

_RESEARCH_SYSTEM = """You are a research assistant. You search the web, gather information, and produce clear summaries.

Your capabilities:
- Web search for current information
- Fetch and read web pages
- Summarize findings into structured reports
- Compare information from multiple sources

Guidelines:
- Always cite your sources
- Present findings in a structured format (bullet points, sections)
- Distinguish between facts and opinions
- If information is uncertain or conflicting, say so"""

_SCHEDULER_SYSTEM = """You are a scheduling assistant. You help the user track reminders and deadlines.

Your capabilities:
- Add new reminders with due dates
- List existing reminders (all, today, overdue)
- Remove completed reminders
- Parse natural language dates (e.g., "next Monday", "in 2 hours")

Guidelines:
- When adding reminders, always confirm the parsed date
- Use ISO format (YYYY-MM-DDTHH:MM:SS) for the 'due' field
- For recurring reminders, describe the pattern in the 'recurring' field
- Proactively mention overdue reminders"""

_SCHEDULER_TOOLS = [
    {
        "name": "add_reminder",
        "description": "Create a new reminder or deadline",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Reminder title"},
                "due": {"type": "string", "description": "Due date/time in ISO format (YYYY-MM-DDTHH:MM:SS)"},
                "recurring": {"type": "string", "description": "Recurrence pattern, e.g. 'every Monday 9am'"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "list_reminders",
        "description": "List reminders, optionally filtered",
        "input_schema": {
            "type": "object",
            "properties": {
                "filter": {"type": "string", "enum": ["all", "today", "overdue"], "description": "Filter type"},
            },
            "required": [],
        },
    },
    {
        "name": "remove_reminder",
        "description": "Remove a reminder by its ID",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "The reminder ID to remove"},
            },
            "required": ["id"],
        },
    },
]


def _extract_text(response: anthropic.types.Message) -> str:
    parts = [b.text for b in response.content if b.type == "text"]
    return "\n".join(parts).strip()


def _run_scheduler_tool(name: str, args: dict) -> str:
    import asyncio
    if name == "add_reminder":
        result = asyncio.run(add_reminder(args))
    elif name == "list_reminders":
        result = asyncio.run(list_reminders(args))
    elif name == "remove_reminder":
        result = asyncio.run(remove_reminder(args))
    else:
        return f"Unknown tool: {name}"
    blocks = result.get("content", [])
    return "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text")


def run_email_agent(client: anthropic.Anthropic, request: str) -> str:
    messages = [{"role": "user", "content": request}]
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=_EMAIL_SYSTEM,
            tools=[
                {"type": "web_search_20260209", "name": "web_search"},
                {"type": "web_fetch_20260209", "name": "web_fetch"},
            ],
            messages=messages,
        )
        if response.stop_reason != "pause_turn":
            return _extract_text(response)
        messages = [
            {"role": "user", "content": request},
            {"role": "assistant", "content": response.content},
        ]


def run_research_agent(client: anthropic.Anthropic, request: str) -> str:
    messages = [{"role": "user", "content": request}]
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=_RESEARCH_SYSTEM,
            tools=[
                {"type": "web_search_20260209", "name": "web_search"},
                {"type": "web_fetch_20260209", "name": "web_fetch"},
            ],
            messages=messages,
        )
        if response.stop_reason != "pause_turn":
            return _extract_text(response)
        messages = [
            {"role": "user", "content": request},
            {"role": "assistant", "content": response.content},
        ]


def run_scheduler_agent(client: anthropic.Anthropic, request: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    system = _SCHEDULER_SYSTEM + f"\n\nCurrent date and time: {today}"
    messages = [{"role": "user", "content": request}]
    while True:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=2048,
            system=system,
            tools=_SCHEDULER_TOOLS,
            messages=messages,
        )

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result_text = _run_scheduler_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_text,
                })

        if response.stop_reason == "end_turn" or not tool_results:
            return _extract_text(response)

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})
