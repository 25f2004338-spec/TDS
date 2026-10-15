
import hashlib
import json

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

import re
from pathlib import Path
from datetime import datetime, date
from zoneinfo import ZoneInfo
from collections import defaultdict

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

BUSINESS_TZ = ZoneInfo("Asia/Kolkata")

USD_PER_UNIT = {
    "USD": 1.0,
    "EUR": 1.09,
    "INR": 0.0118,
}

DATA_FILE = Path(__file__).with_name("orders.jsonl")

PRODUCTS = [
    "Air Fryer", "Blender", "Grinder", "Juicer",
    "Kettle", "Mixer", "Rice Cooker", "Toaster",
]

REGIONS = ["North", "South", "East", "West", "Central"]

MONTHS = {
    name.lower(): number
    for number, name in enumerate(
        ["", "January", "February", "March", "April",
         "May", "June", "July", "August", "September",
         "October", "November", "December"]
    )
    if name
}


def parse_timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_current_orders():
    latest = {}

    with DATA_FILE.open(encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue

            order = json.loads(line)
            order_id = order["id"]

            if order_id not in latest:
                latest[order_id] = order
            elif (
                parse_timestamp(order["updated_at"])
                > parse_timestamp(latest[order_id]["updated_at"])
            ):
                latest[order_id] = order

    return list(latest.values())


ORDERS = load_current_orders()


def amount_usd(order):
    return order["amount"] * USD_PER_UNIT[order["currency"]]


def order_date(order):
    return (
        parse_timestamp(order["created_at"])
        .astimezone(BUSINESS_TZ)
        .date()
    )


def date_range(question):
    q = question.lower()

    # Explicit date range: between 2026-03-01 and 2026-03-31
    match = re.search(
        r"between\s+(\d{4}-\d{2}-\d{2})\s+and\s+(\d{4}-\d{2}-\d{2})",
        q,
    )
    if match:
        return date.fromisoformat(match.group(1)), date.fromisoformat(match.group(2))

    # Quarter: Q1 2026, first quarter of 2026, etc.
    match = re.search(r"\bq([1-4])\s*(20\d{2})\b", q)
    if match:
        quarter = int(match.group(1))
        year = int(match.group(2))
        start_month = (quarter - 1) * 3 + 1
        end_month = start_month + 2
        if end_month == 12:
            end = date(year, 12, 31)
        else:
            end = date(year, end_month + 1, 1).fromordinal(
                date(year, end_month + 1, 1).toordinal() - 1
            )
        return date(year, start_month, 1), end

    # Month and year: March 2026, March of 2026, etc.
    for month_name, month_number in MONTHS.items():
        match = re.search(
            rf"\b{month_name}\s+(?:of\s+)?(20\d{{2}})\b", q
        )
        if match:
            year = int(match.group(1))
            start = date(year, month_number, 1)

            if month_number == 12:
                end = date(year, 12, 31)
            else:
                end = date(year, month_number + 1, 1).fromordinal(
                    date(year, month_number + 1, 1).toordinal() - 1
                )

            return start, end

    # A year on its own.
    match = re.search(r"\b(20\d{2})\b", q)
    if match:
        year = int(match.group(1))
        return date(year, 1, 1), date(year, 12, 31)

    return None


def filter_orders(question):
    q = question.lower()
    selected = list(ORDERS)

    # Use current status, not historical status.
    if any(word in q for word in ["refund", "refunded"]):
        selected = [o for o in selected if o["status"] == "refunded"]
    elif any(word in q for word in ["void", "voided"]):
        selected = [o for o in selected if o["status"] == "void"]
    elif any(word in q for word in ["revenue", "sales", "sold", "earnings"]):
        selected = [o for o in selected if o["status"] == "paid"]
    elif re.search(r"\bpaid\b", q):
        selected = [o for o in selected if o["status"] == "paid"]

    for region in REGIONS:
        if re.search(rf"\b{region.lower()}\b", q):
            selected = [o for o in selected if o["region"] == region]
            break

    for product in PRODUCTS:
        if product.lower() in q:
            selected = [o for o in selected if o["product"] == product]
            break

    customer_match = re.search(r"\bC\d{4}\b", question, re.I)
    if customer_match:
        customer_id = customer_match.group(0).upper()
        selected = [o for o in selected if o["customer"] == customer_id]

    dates = date_range(question)
    if dates:
        start, end = dates
        selected = [
            o for o in selected
            if start <= order_date(o) <= end
        ]

    return selected


def money(value):
    return f"${value:,.2f}"


def answer_question(question):
    q = question.lower()
    selected = filter_orders(question)

    if not selected:
        return "No matching orders were found."

    # Unique customers
    if "unique customer" in q or "how many customers" in q:
        return str(len({o["customer"] for o in selected}))

    # Ranking questions
    if any(word in q for word in ["most", "highest", "top", "best-selling", "best selling"]):
        if "customer" in q or "client" in q:
            groups = defaultdict(float)
            for o in selected:
                groups[o["customer"]] += amount_usd(o)
            if groups:
                key = max(groups, key=groups.get)
                return f"{key} with {money(groups[key])} in matching orders."

        
            if "product" in q or "which item" in q:
                groups = defaultdict(float)
                for o in selected:
                    groups[o["product"]] += amount_usd(o)
                if groups:
                    key = max(groups, key=groups.get)
                    return key


    # Revenue/refund amounts
    if any(word in q for word in ["revenue", "sales", "earnings", "refund amount", "total refunds"]):
        return money(sum(amount_usd(o) for o in selected))

    # Units sold
    if "unit" in q or "quantity" in q:
        return str(sum(o["qty"] for o in selected))

    # Average order value
    if "average order value" in q or "average order amount" in q:
        return money(sum(amount_usd(o) for o in selected) / len(selected))

    # Order counts
    if any(word in q for word in ["how many", "count", "number of", "orders"]):
        return str(len(selected))

    # General fallback: return matching order count.
    return f"{len(selected)} matching orders."


@app.post("/answer")
async def answer_endpoint(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"answer": "Request body must be valid JSON."}, status_code=400)

    question = payload.get("question") if isinstance(payload, dict) else None
    if not isinstance(question, str) or not question.strip():
        return JSONResponse({"answer": "Please provide a question."}, status_code=400)

    return {"answer": answer_question(question)}



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
