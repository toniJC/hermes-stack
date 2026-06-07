#!/usr/bin/env python3
"""
Thin proxy for Devstral/llama-server that converts Mistral [TOOL_CALLS]
raw content into structured OpenAI-compatible tool_calls.

Listens on :8005, forwards to llama-server on :8004.
"""
import json
import re
import uuid
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

UPSTREAM = "http://localhost:8004"
app = FastAPI()

# Prepended to the system message when tools are present.
# Devstral narrates instead of calling tools without explicit instruction.
TOOL_USE_PREAMBLE = (
    "You are an autonomous coding agent. Follow these rules strictly:\n"
    "1. NEVER describe what you are going to do — just do it using tools.\n"
    "2. NEVER show code blocks in chat — use write/edit tools to create files directly.\n"
    "3. NEVER ask for confirmation before taking action — the user's request is your authorization.\n"
    "4. For memory/recall operations: call mem_search or mem_context immediately.\n"
    "5. For simple tasks (single file, clear requirement): use write/edit/bash tools directly.\n"
    "6. For complex multi-file changes that need planning: use subagent with one of these exact names:\n"
    "   sdd-init, sdd-explore, sdd-proposal, sdd-spec, sdd-design, sdd-tasks, sdd-apply, sdd-verify, sdd-archive\n"
    "7. When you have enough context to act, act. Do not plan in chat.\n\n"
)


def _random_tool_id() -> str:
    return uuid.uuid4().hex[:9]


def _parse_tool_calls(content: str) -> list | None:
    """Extract tool calls from [TOOL_CALLS][...] raw model output."""
    match = re.match(r"\[TOOL_CALLS\]\s*(\[.*?\])\s*$", content.strip(), re.DOTALL)
    if not match:
        return None
    try:
        raw = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    calls = []
    for item in raw:
        name = item.get("name") or item.get("function", {}).get("name", "")
        args = item.get("arguments") or item.get("function", {}).get("arguments", {})
        if not isinstance(args, str):
            args = json.dumps(args)
        calls.append({
            "id": item.get("id", _random_tool_id()),
            "type": "function",
            "function": {"name": name, "arguments": args},
        })
    return calls if calls else None


def _transform_response(data: dict) -> dict:
    """Post-process chat completion response."""
    for choice in data.get("choices", []):
        msg = choice.get("message", {})
        content = msg.get("content") or ""
        if "[TOOL_CALLS]" in content:
            tool_calls = _parse_tool_calls(content)
            if tool_calls:
                msg["tool_calls"] = tool_calls
                msg["content"] = None
                choice["finish_reason"] = "tool_calls"
    return data


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def proxy(request: Request, path: str):
    url = f"{UPSTREAM}/{path}"
    body = await request.body()
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")}

    # Audit: print system prompt and tools breakdown on chat completions
    if request.method == "POST" and "chat/completions" in path and body:
        try:
            data = json.loads(body)
            messages = data.get("messages", [])
            tools = data.get("tools", [])
            sys_msg = next((m for m in messages if m.get("role") == "system"), None)
            sys_chars = len(sys_msg.get("content", "")) if sys_msg else 0
            tools_chars = len(json.dumps(tools))
            tool_names = [t.get("function", {}).get("name", "?") for t in tools]
            print(f"\n=== AUDIT ===")
            print(f"messages: {len(messages)} | tools: {len(tools)} | sys_chars: {sys_chars} | tools_chars: {tools_chars}")
            print(f"tool names: {tool_names}")
            if sys_msg:
                print(f"system[:300]: {sys_msg['content'][:300]}")
            # Show tool result messages (role=tool) for debugging
            tool_msgs = [m for m in messages if m.get("role") == "tool"]
            for tm in tool_msgs:
                content_preview = str(tm.get("content", ""))[:200]
                print(f"tool_result id={tm.get('tool_call_id')} content[:200]: {content_preview}")
            # Show last assistant message
            asst_msgs = [m for m in messages if m.get("role") == "assistant"]
            if asst_msgs:
                last_asst = asst_msgs[-1]
                print(f"last_assistant: content={str(last_asst.get('content'))[:100]} tool_calls={bool(last_asst.get('tool_calls'))}")
            print(f"=============\n", flush=True)
        except Exception as e:
            print(f"AUDIT ERROR: {e}", flush=True)

    is_chat = request.method == "POST" and "chat/completions" in path
    is_streaming = False

    # Inject tool-use preamble into system message when tools are present
    if is_chat and body:
        try:
            data = json.loads(body)
            is_streaming = data.get("stream", False)
            if data.get("tools"):
                messages = data.get("messages", [])
                sys_idx = next((i for i, m in enumerate(messages) if m.get("role") == "system"), None)
                if sys_idx is not None:
                    data["messages"][sys_idx]["content"] = (
                        TOOL_USE_PREAMBLE + data["messages"][sys_idx]["content"]
                    )
                else:
                    data["messages"].insert(0, {"role": "system", "content": TOOL_USE_PREAMBLE})
                body = json.dumps(data).encode()
        except Exception as e:
            print(f"PREAMBLE INJECT ERROR: {e}", flush=True)

    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
            params=dict(request.query_params),
        )

    content_type = resp.headers.get("content-type", "")

    # Non-streaming: transform [TOOL_CALLS] in the JSON response
    if "application/json" in content_type and is_chat:
        try:
            data = resp.json()
            data = _transform_response(data)
            return JSONResponse(content=data, status_code=resp.status_code)
        except Exception:
            pass

    # Streaming: buffer all SSE chunks, check last text chunk for [TOOL_CALLS],
    # convert to a single non-streaming JSON response if tool calls are found.
    if is_streaming and is_chat:
        chunks = resp.content.decode("utf-8", errors="replace")
        full_text = ""
        last_chunk_data: dict = {}
        for line in chunks.splitlines():
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
                last_chunk_data = chunk
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                full_text += delta.get("content") or ""
            except Exception:
                pass

        if "[TOOL_CALLS]" in full_text:
            tool_calls = _parse_tool_calls(full_text)
            if tool_calls:
                print(f"\n=== TOOL_CALLS DETECTED (streaming) ===")
                print(f"calls: {[tc['function']['name'] for tc in tool_calls]}", flush=True)
                msg_id = last_chunk_data.get("id", "chatcmpl-proxy")
                model_name = last_chunk_data.get("model", "devstral")
                # Return as SSE — Pi sent stream:true and expects SSE back.
                # A JSONResponse here is silently ignored; Pi already stored the
                # narration text as the assistant message. We must speak SSE.
                sse_parts = []
                for i, tc in enumerate(tool_calls):
                    chunk = {
                        "id": msg_id, "object": "chat.completion.chunk",
                        "model": model_name,
                        "choices": [{"index": 0, "delta": {
                            "role": "assistant", "content": None,
                            "tool_calls": [{"index": i, "id": tc["id"],
                                            "type": "function",
                                            "function": {"name": tc["function"]["name"],
                                                         "arguments": tc["function"]["arguments"]}}],
                        }, "finish_reason": None}],
                    }
                    sse_parts.append(f"data: {json.dumps(chunk)}\n\n")
                finish_chunk = {
                    "id": msg_id, "object": "chat.completion.chunk",
                    "model": model_name,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
                }
                sse_parts.append(f"data: {json.dumps(finish_chunk)}\n\n")
                sse_parts.append("data: [DONE]\n\n")
                return StreamingResponse(
                    content=iter(["".join(sse_parts).encode()]),
                    status_code=200,
                    media_type="text/event-stream",
                )

        # No tool calls — re-emit as streaming passthrough (re-encode chunks)
        return StreamingResponse(
            content=iter([resp.content]),
            status_code=resp.status_code,
            media_type="text/event-stream",
            headers={k: v for k, v in resp.headers.items() if k.lower() not in ("content-length",)},
        )

    return StreamingResponse(
        content=iter([resp.content]),
        status_code=resp.status_code,
        headers=dict(resp.headers),
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8005)
