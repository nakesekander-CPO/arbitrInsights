from datetime import datetime

import anthropic

from conductor.agents import run_email_agent, run_research_agent, run_scheduler_agent

SYSTEM_PROMPT = """You are Nake the Conductor — a personal AI assistant orchestrator.

Your job is to understand the user's request and delegate to the right sub-agent:

- **email_agent**: For anything related to email — reading, searching, summarizing, or drafting emails
- **research_agent**: For web research, lookups, summarization, or gathering information
- **scheduler_agent**: For reminders, deadlines, recurring tasks, or anything time-based

Routing rules:
1. Analyze the user's intent
2. Delegate to the most appropriate agent using the available tools
3. If the request spans multiple agents, call them one at a time and combine results
4. For simple greetings or questions about your capabilities, respond directly

You never perform domain tasks yourself — always delegate to sub-agents."""

CONDUCTOR_TOOLS = [
    {
        "name": "email_agent",
        "description": "Handles Gmail tasks: reading inbox, searching emails, summarizing threads, drafting replies. Use for any email-related request.",
        "input_schema": {
            "type": "object",
            "properties": {
                "request": {"type": "string", "description": "The email task to handle"},
            },
            "required": ["request"],
        },
    },
    {
        "name": "research_agent",
        "description": "Gathers information from the web, summarizes findings, and generates reports. Use for any research, lookup, or summarization request.",
        "input_schema": {
            "type": "object",
            "properties": {
                "request": {"type": "string", "description": "The research query or task"},
            },
            "required": ["request"],
        },
    },
    {
        "name": "scheduler_agent",
        "description": "Manages reminders, recurring check-ins, and deadline tracking. Use for any request about reminders, deadlines, schedules, or things to remember.",
        "input_schema": {
            "type": "object",
            "properties": {
                "request": {"type": "string", "description": "The scheduling task"},
            },
            "required": ["request"],
        },
    },
]


def _dispatch(client: anthropic.Anthropic, tool_name: str, tool_input: dict) -> str:
    request = tool_input.get("request", "")
    if tool_name == "email_agent":
        return run_email_agent(client, request)
    elif tool_name == "research_agent":
        return run_research_agent(client, request)
    elif tool_name == "scheduler_agent":
        return run_scheduler_agent(client, request)
    return f"Unknown agent: {tool_name}"


def run_conductor_turn(client: anthropic.Anthropic, user_input: str) -> None:
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    system = SYSTEM_PROMPT + f"\n\nCurrent date and time: {today}"
    messages = [{"role": "user", "content": user_input}]

    while True:
        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=4096,
            system=system,
            tools=CONDUCTOR_TOOLS,
            messages=messages,
        )

        tool_results = []
        for block in response.content:
            if block.type == "text" and block.text.strip():
                print(f"\nConductor: {block.text}")
            elif block.type == "tool_use":
                print(f"\n  → [{block.name}] thinking...", end="", flush=True)
                result = _dispatch(client, block.name, block.input)
                print(f"\r  → [{block.name}] done           ")
                print(f"\n{result}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        if response.stop_reason == "end_turn" or not tool_results:
            break

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})
