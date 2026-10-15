
import hashlib
import json

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

app = FastAPI()

EMAIL = "25f2004338@ds.study.iitm.ac.in"

TOOLS = [
    {
        "name": "solve_challenge",
        "description": "Compute the required SHA-256 challenge response.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    }
]

@app.get("/mcp")
async def mcp_health():
    return {
        "status": "ok",
        "endpoint": "/mcp"
    }


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    # Read the JSON-RPC request.
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None,
             "error": {"code": -32700, "message": "Parse error"}},
            status_code=400,
        )

    # Support JSON-RPC batches as well as individual requests.
    if isinstance(body, list):
        results = []
        for item in body:
            result = await handle_rpc(item, request)
            if result is not None:
                results.append(result)

        if not results:
            return Response(status_code=202)

        return JSONResponse(results)

    result = await handle_rpc(body, request)

    # Notifications do not receive JSON-RPC responses.
    if result is None:
        return Response(status_code=202)

    return JSONResponse(result)


async def handle_rpc(message: dict, request: Request):
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") or {}

    def reply(result):
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }

    def error(code, text):
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": text},
        }

    # Notifications have no id and require no response.
    if method == "notifications/initialized":
        return None

    if method == "initialize":
        version = params.get("protocolVersion", "2025-03-26")
        supported = {"2024-11-05", "2025-03-26", "2025-06-18"}

        return reply({
            "protocolVersion": (
                version if version in supported else "2025-03-26"
            ),
            "capabilities": {"tools": {}},
            "serverInfo": {
                "name": "exam-challenge-server",
                "version": "1.0.0",
            },
        })

    if method == "ping":
        return reply({})

    if method == "tools/list":
        return reply({"tools": TOOLS})

    if method == "tools/call":
        if params.get("name") != "solve_challenge":
            return error(-32602, "Unknown tool")

        # IMPORTANT: use the HTTP header for THIS call,
        # never a value supplied in the JSON request body.
        challenge = request.headers.get("x-exam-challenge")

        if not challenge:
            return error(-32602, "Missing X-Exam-Challenge header")

        digest = hashlib.sha256(
            f"{challenge}:{EMAIL}".encode("utf-8")
        ).hexdigest()[:16]

        return reply({
            "content": [
                {"type": "text", "text": digest}
            ],
            "isError": False,
        })

    if request_id is None:
        return None

    return error(-32601, "Method not found")
