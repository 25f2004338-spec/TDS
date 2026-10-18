
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

ALLOWED_ORIGIN = "https://dash-q9rngna.example.com"
EMAIL = "YOUR_IITM_EMAIL"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
    expose_headers=["*"]
)

@app.middleware("http")
async def add_required_headers(request: Request, call_next):
    start = time.perf_counter()
    request_id = str(uuid.uuid4())

    try:
        response = await call_next(request)
    except Exception:
        response = JSONResponse(
            status_code=500,
            content={"detail": "Internal Server Error"},
        )

    elapsed = time.perf_counter() - start
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{elapsed:.6f}"
    return response


@app.get("/stats")
def stats(values: str = Query(...)):
    try:
        numbers = [int(item.strip()) for item in values.split(",")]
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="values must contain comma-separated integers",
        )

    if not numbers or any(not item.strip() for item in values.split(",")):
        raise HTTPException(status_code=400, detail="No empty values allowed")

    return {
        "email": "25f2004338@ds.study.iitm.ac.in",
        "count": len(numbers),
        "sum": sum(numbers),
        "min": min(numbers),
        "max": max(numbers),
        "mean": sum(numbers) / len(numbers),
    }
