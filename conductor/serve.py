import asyncio
import http.server
import json
import os
import re
import subprocess
import threading
import webbrowser
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

PORT = 8080
ROOT = Path(__file__).parent.parent
TASKS_DIR = Path.home() / ".claude" / "scheduled-tasks"

# Find the claude CLI binary
CLAUDE_CLI = None
_claude_code_dir = Path.home() / "Library" / "Application Support" / "Claude" / "claude-code"
if _claude_code_dir.exists():
    # Find the latest version
    versions = sorted(_claude_code_dir.iterdir(), reverse=True)
    for v in versions:
        candidate = v / "claude.app" / "Contents" / "MacOS" / "claude"
        if candidate.exists():
            CLAUDE_CLI = str(candidate)
            break

# Map widget IDs to scheduled task IDs
WIDGET_TO_TASK = {
    "gmail-digest": "gmail-daily-digest",
    "gchat-digest": "gchat-daily-digest",
    "clickup-morning": "clickup-daily-digest",
    "clickup-eod": "clickup-eod-status",
    "intel-focused": "strategic-intel-scan",
    "intel-japan": "strategic-intel-scan-japan",
    "intel-broad": "strategic-intel-scan-broad",
    "competitor-dive": "competitor-deep-dive",
    "producthunt-hn": "producthunt-hackernews-scan",
    "research-patents": "research-patent-tracker",
    "conference-events": "conference-event-tracker",
    "weekly-rollup": "weekly-intel-rollup",
}

# Tasks that need browser/MCP tools — must run via `claude` CLI
BROWSER_TASKS = {"gchat-digest", "clickup-morning", "clickup-eod", "gmail-digest"}

# Track which tasks are currently running
running_tasks = set()
analyzing_insights = False


def extract_prompt(skill_path: Path) -> str | None:
    """Extract the prompt content from a SKILL.md file (after frontmatter)."""
    if not skill_path.exists():
        return None
    text = skill_path.read_text()
    match = re.match(r"^---\n.*?\n---\n(.*)", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def run_task_via_cli(widget_id: str, task_id: str):
    """Run a task via the `claude` CLI so it has access to MCP tools and browser."""
    skill_path = TASKS_DIR / task_id / "SKILL.md"
    prompt = extract_prompt(skill_path)
    if not prompt:
        running_tasks.discard(widget_id)
        return

    try:
        print(f"  [{widget_id}] Running via claude CLI...")
        cli = CLAUDE_CLI or "claude"
        result = subprocess.run(
            [cli, "--print", "--dangerously-skip-permissions", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(ROOT),
        )
        # If the task didn't write its own JSON, write the output
        out_path = ROOT / "data" / "dashboard" / f"{widget_id}.json"
        if not out_path.exists() or (datetime.now().timestamp() - out_path.stat().st_mtime > 60):
            output_data = {
                "title": widget_id,
                "updated": datetime.now().isoformat(),
                "content": result.stdout[:10000] if result.stdout else f"**Error**\n\n`{result.stderr[:2000]}`",
                "status": "success" if result.returncode == 0 else "error",
            }
            out_path.write_text(json.dumps(output_data, indent=2))
        print(f"  [{widget_id}] CLI task completed (exit code {result.returncode})")
    except subprocess.TimeoutExpired:
        out_path = ROOT / "data" / "dashboard" / f"{widget_id}.json"
        out_path.write_text(json.dumps({
            "title": widget_id,
            "updated": datetime.now().isoformat(),
            "content": "**Task timed out** (10 minute limit)",
            "status": "error",
        }, indent=2))
    except FileNotFoundError:
        out_path = ROOT / "data" / "dashboard" / f"{widget_id}.json"
        out_path.write_text(json.dumps({
            "title": widget_id,
            "updated": datetime.now().isoformat(),
            "content": "**Error**: `claude` CLI not found. Ensure the Claude desktop app is installed.",
            "status": "error",
        }, indent=2))
    except Exception as e:
        out_path = ROOT / "data" / "dashboard" / f"{widget_id}.json"
        out_path.write_text(json.dumps({
            "title": widget_id,
            "updated": datetime.now().isoformat(),
            "content": f"**Error running task**\n\n`{e}`",
            "status": "error",
        }, indent=2))
    finally:
        running_tasks.discard(widget_id)


def run_task_via_sdk(widget_id: str, task_id: str):
    """Run a task via the Claude Agent SDK (for non-browser tasks)."""
    from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock

    skill_path = TASKS_DIR / task_id / "SKILL.md"
    prompt = extract_prompt(skill_path)
    if not prompt:
        running_tasks.discard(widget_id)
        return

    async def execute():
        try:
            options = ClaudeAgentOptions(
                permission_mode="acceptEdits",
                model="claude-sonnet-4-5",
                allowed_tools=["WebSearch", "WebFetch", "Read", "Write", "Bash", "Glob", "Grep"],
            )
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            print(f"  [{widget_id}] {block.text[:100]}...")
        except Exception as e:
            out_path = ROOT / "data" / "dashboard" / f"{widget_id}.json"
            out_path.write_text(json.dumps({
                "title": widget_id,
                "updated": datetime.now().isoformat(),
                "content": f"**Error running task**\n\n`{e}`",
                "status": "error",
            }, indent=2))
        finally:
            running_tasks.discard(widget_id)

    asyncio.run(execute())


def run_insights_analysis(content: str):
    """Analyze intel content and extract top 3 strategic insights."""
    from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock

    global analyzing_insights

    prompt = f"""You are a strategic intelligence analyst for NotVerify / Straker.AI — an AI-powered enterprise localization QA platform with agent orchestration, trust scoring, explainability, and compliance features.

Below is the combined output from multiple intelligence scans. Analyze ALL of it and extract the TOP 3 most valuable strategic insights. These should be the findings most likely to impact business decisions.

Do NOT include insights about email, chat, or project management. Focus ONLY on:
- Competitive threats or opportunities
- Market trends that affect the platform
- Acquisition or partnership targets
- Technology shifts to adopt or defend against
- Regulatory changes that create demand

After your analysis, you MUST write the results to a JSON file using the Write tool.

Write to: `/Users/nake/Desktop/Nake the Conductor/data/dashboard/top-insights.json`

The JSON format MUST be exactly:
{{
  "updated": "<current ISO 8601 datetime>",
  "insights": [
    {{
      "headline": "<short punchy headline, max 12 words>",
      "analysis": "<2-3 sentence strategic analysis — what it means for NotVerify and what to do>",
      "tag": "action",
      "tag_label": "Take Action"
    }},
    {{
      "headline": "<headline>",
      "analysis": "<analysis>",
      "tag": "watch",
      "tag_label": "Watch Closely"
    }},
    {{
      "headline": "<headline>",
      "analysis": "<analysis>",
      "tag": "threat",
      "tag_label": "Emerging Threat"
    }}
  ]
}}

Use these tag values based on urgency:
- "action" / "Take Action" — requires immediate response
- "watch" / "Watch Closely" — important but not urgent
- "threat" / "Emerging Threat" — competitive or market risk

Here is the intelligence data to analyze:

{content[:30000]}"""

    async def execute():
        global analyzing_insights
        try:
            options = ClaudeAgentOptions(
                permission_mode="acceptEdits",
                model="claude-sonnet-4-5",
                allowed_tools=["Write"],
            )
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            print(f"  [insights] {block.text[:100]}...")
        except Exception as e:
            out_path = ROOT / "data" / "dashboard" / "top-insights.json"
            out_path.write_text(json.dumps({
                "updated": datetime.now().isoformat(),
                "insights": [{
                    "headline": "Analysis failed",
                    "analysis": str(e),
                    "tag": "threat",
                    "tag_label": "Error",
                }],
            }, indent=2))
        finally:
            analyzing_insights = False

    asyncio.run(execute())


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        # POST /api/analyze — run top insights analysis
        if self.path == "/api/analyze":
            global analyzing_insights
            if analyzing_insights:
                self._json_response(409, {"error": "Analysis already running"})
                return

            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode() if content_length else '{}'
            data = json.loads(body)
            content = data.get('content', '')

            if not content:
                self._json_response(400, {"error": "No intel content provided"})
                return

            analyzing_insights = True
            thread = threading.Thread(
                target=run_insights_analysis,
                args=(content,),
                daemon=True,
            )
            thread.start()
            print("[analyze] Started insights analysis")
            self._json_response(200, {"status": "analyzing"})
            return

        match = re.match(r"^/api/run/([\w-]+)$", self.path)
        if match:
            widget_id = match.group(1)
            task_id = WIDGET_TO_TASK.get(widget_id)

            if not task_id:
                self._json_response(404, {"error": f"Unknown widget: {widget_id}"})
                return

            if widget_id in running_tasks:
                self._json_response(409, {"error": "Task already running", "widget": widget_id})
                return

            running_tasks.add(widget_id)

            # Choose execution method based on task type
            if widget_id in BROWSER_TASKS:
                target = run_task_via_cli
            else:
                target = run_task_via_sdk

            thread = threading.Thread(
                target=target,
                args=(widget_id, task_id),
                daemon=True,
            )
            thread.start()
            method = "CLI" if widget_id in BROWSER_TASKS else "SDK"
            print(f"[run] Started task: {widget_id} ({task_id}) via {method}")
            self._json_response(200, {"status": "started", "widget": widget_id, "task": task_id})
            return

        self._json_response(404, {"error": "Not found"})

    def do_GET(self):
        if self.path == "/api/status":
            self._json_response(200, {"running": list(running_tasks)})
            return
        super().do_GET()

    def _json_response(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        if "/api/" in (args[0] if args else ""):
            super().log_message(format, *args)


def run():
    load_dotenv(ROOT / ".env")
    os.chdir(ROOT)
    server = http.server.HTTPServer(("localhost", PORT), DashboardHandler)
    print(f"Dashboard running at http://localhost:{PORT}/dashboard.html")
    webbrowser.open(f"http://localhost:{PORT}/dashboard.html")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
        server.shutdown()


if __name__ == "__main__":
    run()
