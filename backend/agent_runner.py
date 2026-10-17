"""AI Warden Agent Runner for Anything-to-MCP Studio.
Loads backend/generated_mcp_server.py dynamically and executes tool-augmented tasks
using Google GenAI (Gemini 2.5 Flash) with a bulletproof deterministic fallback.
"""

import importlib.util
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Dynamic Server Loader
# ---------------------------------------------------------------------------
def load_generated_mcp_module() -> Any:
    """Dynamically load or reload backend/generated_mcp_server.py without stale caching."""
    # Check potential server paths
    possible_paths = [
        Path(__file__).parent / "generated_mcp_server.py",
        Path(r"C:\Users\vjcha\OneDrive\SUSANTH\anything-to-mcp-studio\backend\generated_mcp_server.py"),
        Path(r"C:\Users\vjcha\.gemini\antigravity\scratch\backend\generated_mcp_server.py"),
    ]

    target_path = None
    for p in possible_paths:
        if p.exists():
            target_path = p
            break

    # If no server has been generated yet, auto-generate default v1 spec server
    if not target_path or not target_path.exists():
        from backend.demo_api import get_spec
        from backend.generator import generate_mcp_code

        spec_v1 = get_spec("v1")
        generate_mcp_code(spec=spec_v1, read_only=False)
        target_path = possible_paths[0]

    module_name = f"generated_mcp_server_{os.getpid()}"
    spec = importlib.util.spec_from_file_location(module_name, str(target_path))
    if not spec or not spec.loader:
        raise RuntimeError(f"Failed to load MCP server from {target_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Deterministic Intent Fallback Matcher
# ---------------------------------------------------------------------------
def run_fallback_intent_matching(
    user_prompt: str,
    module: Any,
    tools_registry: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Offline rule-based intent matcher executing real tool calls when Gemini API is unavailable."""
    prompt_lower = user_prompt.lower()
    tool_calls: List[Dict[str, Any]] = []
    reply = ""

    tool_names = [t["name"] for t in tools_registry]

    # Find specific tools by semantic role
    resolve_tool_name = next((t["name"] for t in tools_registry if "resolve" in t["name"]), None)
    delete_tool_name = next((t["name"] for t in tools_registry if "delete" in t["name"]), None)
    report_tool_name = next((t["name"] for t in tools_registry if "report" in t["name"] or "create" in t["name"] or "post" in t["name"]), None)
    list_tool_name = next((t["name"] for t in tools_registry if "list" in t["name"] or "get" in t["name"]), None)

    # 1. Resolve Issue Intent
    resolve_match = re.search(r"(?:resolve|fix|close|mark\s+(?:as\s+)?resolved)\s+(?:issue\s+)?(?:#|id\s*)?(\d+)", prompt_lower)
    if not resolve_match:
        resolve_match = re.search(r"issue\s+(?:#|id\s*)?(\d+).*(?:resolve|fix|close)", prompt_lower)

    if resolve_match:
        issue_id = int(resolve_match.group(1))
        # Extract optional warden note
        note_match = re.search(r"(?:note|comment|action)[:\s]+[\"']?([^\"'\n]+)[\"']?", user_prompt, re.IGNORECASE)
        note = note_match.group(1).strip() if note_match else "Issue repaired and verified by Warden."

        if resolve_tool_name and hasattr(module, resolve_tool_name):
            tool_fn = getattr(module, resolve_tool_name)
            try:
                res = tool_fn(issue_id=issue_id, warden_note=note)
                tool_calls.append({"name": resolve_tool_name, "args": {"issue_id": issue_id, "warden_note": note}, "result": res})
                reply = f"Marked issue #{issue_id} as Resolved with warden note: '{note}'."
            except Exception as e:
                reply = f"Error resolving issue #{issue_id}: {str(e)}"
        else:
            reply = (
                f"Notice: No 'resolve' tool is present in the currently compiled MCP server "
                f"(Read-Only mode is enabled or Spec v1 is active). Cannot resolve issue #{issue_id}."
            )
        return {"reply": reply, "tool_calls": tool_calls}

    # 2. Delete Issue Intent
    delete_match = re.search(r"(?:delete|remove|cancel|dismiss)\s+(?:issue\s+)?(?:#|id\s*)?(\d+)", prompt_lower)
    if delete_match:
        issue_id = int(delete_match.group(1))
        if delete_tool_name and hasattr(module, delete_tool_name):
            tool_fn = getattr(module, delete_tool_name)
            try:
                res = tool_fn(issue_id=issue_id)
                tool_calls.append({"name": delete_tool_name, "args": {"issue_id": issue_id}, "result": res})
                reply = f"Successfully deleted hostel issue #{issue_id}."
            except Exception as e:
                reply = f"Error deleting issue #{issue_id}: {str(e)}"
        else:
            reply = f"Notice: No 'delete' tool is available in the currently compiled MCP server."
        return {"reply": reply, "tool_calls": tool_calls}

    # 3. Report/Create Issue Intent
    if any(k in prompt_lower for k in ["report", "create issue", "file complaint", "submit issue", "new complaint", "new issue"]):
        # Extract room
        room_match = re.search(r"room\s+([A-Za-z0-9\-]+)", user_prompt, re.IGNORECASE)
        room = room_match.group(1) if room_match else "305"

        # Extract category
        if "plumb" in prompt_lower or "water" in prompt_lower or "tap" in prompt_lower:
            category = "Plumbing"
        elif "electr" in prompt_lower or "fan" in prompt_lower or "light" in prompt_lower:
            category = "Electrical"
        elif "wifi" in prompt_lower or "internet" in prompt_lower or "router" in prompt_lower:
            category = "Internet"
        else:
            category = "General"

        # Extract priority
        if "high" in prompt_lower or "urgent" in prompt_lower or "emergency" in prompt_lower:
            priority = "High"
        elif "low" in prompt_lower:
            priority = "Low"
        else:
            priority = "Medium"

        description = user_prompt.strip()

        if report_tool_name and hasattr(module, report_tool_name):
            tool_fn = getattr(module, report_tool_name)
            try:
                res = tool_fn(room=room, category=category, priority=priority, description=description)
                tool_calls.append({
                    "name": report_tool_name,
                    "args": {"room": room, "category": category, "priority": priority, "description": description},
                    "result": res,
                })
                reply = f"Filed new hostel maintenance ticket for Room {room} [{priority} priority]: '{description}'."
            except Exception as e:
                reply = f"Error reporting hostel issue: {str(e)}"
        else:
            reply = f"Notice: No 'report' tool is available in the currently compiled MCP server (read-only mode active)."
        return {"reply": reply, "tool_calls": tool_calls}

    # 4. List Issues Intent (Default)
    status_filter = None
    if "open" in prompt_lower and "resolved" not in prompt_lower:
        status_filter = "Open"
    elif "resolved" in prompt_lower and "open" not in prompt_lower:
        status_filter = "Resolved"

    if list_tool_name and hasattr(module, list_tool_name):
        tool_fn = getattr(module, list_tool_name)
        try:
            res = tool_fn(status=status_filter) if status_filter else tool_fn()
            tool_calls.append({"name": list_tool_name, "args": {"status": status_filter} if status_filter else {}, "result": res})
            if isinstance(res, list):
                header = f"Found {len(res)} hostel issue(s)" + (f" with status '{status_filter}'" if status_filter else "") + ":\n"
                items_str = []
                for item in res:
                    note_str = f" | Note: {item.get('warden_note')}" if item.get("warden_note") else ""
                    items_str.append(
                        f"- #{item.get('id')} [Room {item.get('room')} | {item.get('category')} | {item.get('priority')}] "
                        f"{item.get('description')} (Status: {item.get('status')}{note_str})"
                    )
                reply = header + "\n".join(items_str)
            else:
                reply = f"Result from {list_tool_name}: {str(res)}"
        except Exception as e:
            reply = f"Error fetching issues: {str(e)}"
    else:
        reply = f"I am your AI Hostel Warden. Available MCP tools in the studio: {', '.join(tool_names)}."

    return {"reply": reply, "tool_calls": tool_calls}


# ---------------------------------------------------------------------------
# Main Agent Task Runner
# ---------------------------------------------------------------------------
def run_agent_task(
    user_prompt: str,
    api_token: str = "hostel-secret-123",
    gemini_key: str = "",
    api_base_url: str = "",
) -> Dict[str, Any]:
    """Execute user prompt against generated MCP tools using Gemini 2.5 Flash with fallback."""
    # Inject API Token & Base URL into environment for the MCP module
    if api_token:
        os.environ["DEMO_API_KEY"] = api_token
    if api_base_url:
        os.environ["API_BASE_URL"] = api_base_url

    # 1. Dynamically load latest generated MCP server
    module = load_generated_mcp_module()
    tools_registry: List[Dict[str, Any]] = getattr(module, "TOOLS_REGISTRY", [])
    available_tools = [t["name"] for t in tools_registry]

    active_gemini_key = gemini_key.strip() if gemini_key else os.environ.get("GEMINI_API_KEY", "").strip()

    # 2. Attempt Google GenAI LLM Agent Loop if key is available
    if active_gemini_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=active_gemini_key)

            # Collect callable tool functions from module
            callable_tools = []
            for t in tools_registry:
                fn = getattr(module, t["name"], None)
                if fn and callable(fn):
                    callable_tools.append(fn)

            config = types.GenerateContentConfig(
                tools=callable_tools,
                temperature=0.2,
                system_instruction=(
                    "You are the CampusCare AI Hostel Warden. "
                    "Manage student issues, maintenance tickets, and repairs using the provided MCP tools. "
                    "Always call the appropriate tool to read or modify issues, and summarize what you did clearly."
                ),
            )

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=user_prompt,
                config=config,
            )

            tool_calls = []
            # Check for function calls executed by the model
            if response.function_calls:
                for call in response.function_calls:
                    fn_name = call.name
                    fn_args = dict(call.args or {})
                    if hasattr(module, fn_name):
                        tool_fn = getattr(module, fn_name)
                        try:
                            result = tool_fn(**fn_args)
                            tool_calls.append({"name": fn_name, "args": fn_args, "result": result})
                        except Exception as exc:
                            tool_calls.append({"name": fn_name, "args": fn_args, "error": str(exc)})

            # Extract or build reply
            reply_text = response.text or ""
            if not reply_text and tool_calls:
                first_call = tool_calls[0]
                reply_text = f"Executed {first_call['name']}: {first_call.get('result') or first_call.get('error')}"

            if not reply_text:
                reply_text = "Task completed by AI Warden."

            return {
                "reply": reply_text.strip(),
                "tool_calls": tool_calls,
                "available_tools": available_tools,
                "mode": "gemini",
            }

        except Exception as e:
            # If Gemini fails (network, quota, invalid key), seamlessly use fallback
            pass

    # 3. Bulletproof Fallback
    fallback_result = run_fallback_intent_matching(user_prompt, module, tools_registry)
    return {
        "reply": fallback_result["reply"],
        "tool_calls": fallback_result["tool_calls"],
        "available_tools": available_tools,
        "mode": "fallback",
    }
