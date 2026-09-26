"""Small trusted host bridge from the local workspace to Codex App Server.

The browser never receives Codex credentials or talks to MCP directly.  A fresh
stdio App Server connection owns one turn, inherits the user's authenticated
Codex session, and discovers the configured SceneLyr MCP server.
"""
from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path


CODEX = Path("/Applications/ChatGPT.app/Contents/Resources/codex")
ROOT = Path(__file__).resolve().parents[2]


def _start_process() -> subprocess.Popen:
    if not CODEX.is_file():
        raise RuntimeError("The Codex application is not installed on this computer.")
    environment = os.environ.copy()
    environment["SCENELYR_DATA_DIR"] = str(ROOT / "data")
    return subprocess.Popen(
        [str(CODEX), "app-server", "--stdio",
         "-c", 'plugins."scenelyr@personal".mcp_servers.scenelyr.default_tools_approval_mode="auto"'],
        cwd=ROOT, env=environment,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, bufsize=1,
    )


def _stop_process(process: subprocess.Popen) -> None:
    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()


def _send(process: subprocess.Popen, method: str, request_id: int | None, params: dict) -> None:
    value = {"method": method, "params": params}
    if request_id is not None:
        value["id"] = request_id
    assert process.stdin is not None
    process.stdin.write(json.dumps(value) + "\n")
    process.stdin.flush()


def _activity(value: dict, report: Callable[[dict], None] | None) -> None:
    if report is None:
        return
    method, params = value.get("method"), value.get("params") or {}
    item = params.get("item") or {}
    if method == "turn/started":
        report({"stage": "codex", "state": "running", "message": "Codex started understanding the request."})
    elif method == "item/started" and item.get("type") == "mcpToolCall":
        arguments = item.get("arguments") or {}
        report({"stage": "tool", "state": "running", "tool": item.get("tool"),
                "message": f'Calling {item.get("tool", "SceneLyr tool")} with {json.dumps(arguments, ensure_ascii=False)}'})
    elif method == "item/completed" and item.get("type") == "mcpToolCall":
        state = "complete" if item.get("status") == "completed" and not item.get("error") else "failed"
        report({"stage": "tool", "state": state, "tool": item.get("tool"),
                "message": f'{item.get("tool", "SceneLyr tool")} {"completed" if state == "complete" else "failed"}.'})


def _read_until(process: subprocess.Popen, predicate, messages: list[dict],
                report: Callable[[dict], None] | None = None) -> dict:
    assert process.stdout is not None
    while True:
        line = process.stdout.readline()
        if not line:
            raise RuntimeError("Codex App Server stopped before completing the request.")
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        messages.append(value)
        _activity(value, report)
        if value.get("method") == "mcpServer/elicitation/request" and value.get("id") is not None:
            params = value.get("params") or {}
            accepted = params.get("serverName") == "scenelyr" and params.get("mode") in {"form", "openai/form"}
            assert process.stdin is not None
            process.stdin.write(json.dumps({"id": value["id"], "result": {
                "action": "accept" if accepted else "decline", "content": {} if accepted else None
            }}) + "\n")
            process.stdin.flush()
            if report:
                tool = (params.get("_meta") or {}).get("tool_description", "SceneLyr MCP tool")
                report({"stage": "approval", "state": "complete" if accepted else "failed",
                        "message": f'{"Approved" if accepted else "Declined"}: {tool}'})
            continue
        if value.get("method") and value.get("id") not in {None, 1, 2, 3}:
            raise RuntimeError("Codex requested an interaction this workspace does not support yet.")
        if value.get("error"):
            raise RuntimeError(value["error"].get("message", "Codex request failed."))
        if predicate(value):
            return value


def list_codex_models() -> list[dict]:
    """Return the account's picker-visible App Server models and efforts."""
    process = _start_process()
    events: list[dict] = []
    try:
        _send(process, "initialize", 1, {"clientInfo": {
            "name": "scenelyr_workspace", "title": "SceneLyr Workspace", "version": "0.1.0"
        }})
        _read_until(process, lambda item: item.get("id") == 1, events)
        _send(process, "initialized", None, {})
        _send(process, "model/list", 4, {"limit": 50, "includeHidden": False})
        result = _read_until(process, lambda item: item.get("id") == 4, events)
        return (result.get("result") or {}).get("data") or []
    finally:
        _stop_process(process)


def run_codex(scene_id: str, message: str, selected: str | None = None,
              report: Callable[[dict], None] | None = None,
              model: str | None = None, effort: str | None = None) -> dict:
    process = _start_process()
    events: list[dict] = []
    try:
        _send(process, "initialize", 1, {"clientInfo": {
            "name": "scenelyr_workspace", "title": "SceneLyr Workspace", "version": "0.1.0"
        }})
        if report:
            report({"stage": "connection", "state": "running", "message": "Connecting to your signed-in Codex session."})
        _read_until(process, lambda item: item.get("id") == 1, events, report)
        _send(process, "initialized", None, {})
        _send(process, "model/list", 4, {"limit": 50, "includeHidden": False})
        model_result = _read_until(process, lambda item: item.get("id") == 4, events, report)
        models = (model_result.get("result") or {}).get("data") or []
        chosen = next((item for item in models if model in {item.get("model"), item.get("id")}), None)
        chosen = chosen or next((item for item in models if item.get("isDefault")), models[0] if models else {})
        model_id = chosen.get("model") or chosen.get("id")
        model_name = chosen.get("displayName") or model_id or "Codex"
        supported = {item.get("reasoningEffort") for item in chosen.get("supportedReasoningEfforts") or []}
        selected_effort = effort if effort in supported else chosen.get("defaultReasoningEffort")
        if report:
            detail = f" with {selected_effort} reasoning" if selected_effort else ""
            report({"stage": "model", "state": "complete",
                    "message": f"Using {model_name}{detail}."})
        _send(process, "thread/start", 2, {
            "cwd": str(ROOT), "approvalPolicy": "on-request", "sandbox": "workspace-write",
            "serviceName": "scenelyr_workspace", **({"model": model_id} if model_id else {}),
        })
        started = _read_until(process, lambda item: item.get("id") == 2, events, report)
        thread_id = started["result"]["thread"]["id"]
        selection = selected or "none"
        prompt = f'''You are the natural-language editing agent embedded in the SceneLyr workspace.
The open scene ID is {scene_id!r}; the selected object or connection is {selection!r}.
Use the configured SceneLyr MCP tools to inspect and fulfill the user's request. Do not edit source
code or JSON files directly, and do not use shell commands for scene changes. For an edit, call the
appropriate SceneLyr MCP tool and then inspect or render the saved scene to verify it. If the request
is ambiguous, explain the exact missing choice instead of guessing. Keep the final response concise
and describe which scene changes were actually saved.

User request: {message}'''
        _send(process, "turn/start", 3, {
            "threadId": thread_id, "input": [{"type": "text", "text": prompt}],
            "cwd": str(ROOT), "approvalPolicy": "on-request",
            **({"model": model_id} if model_id else {}),
            **({"effort": selected_effort} if selected_effort else {}),
            "sandboxPolicy": {"type": "workspaceWrite", "writableRoots": [str(ROOT)],
                              "networkAccess": False},
        })
        _read_until(process, lambda item: item.get("id") == 3, events, report)
        _read_until(process, lambda item: item.get("method") == "turn/completed", events, report)
        replies: list[str] = []
        tools: list[str] = []
        for item in events:
            method, params = item.get("method", ""), item.get("params") or {}
            if method == "item/completed":
                completed = params.get("item") or {}
                if completed.get("type") == "agentMessage" and completed.get("text"):
                    replies.append(completed["text"])
                if completed.get("type") in {"mcpToolCall", "functionCall"}:
                    name = completed.get("tool") or completed.get("name")
                    if name:
                        tools.append(name)
        return {"message": replies[-1] if replies else "Codex completed the request.",
                "tools": list(dict.fromkeys(tools)), "threadId": thread_id,
                "model": model_id, "modelName": model_name, "effort": selected_effort}
    finally:
        _stop_process(process)
