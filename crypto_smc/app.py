#!/usr/bin/env python3
"""SmartFlow — multi-timeframe technical + Smart Money analysis server."""

from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from analyzer.data import DataError
from analyzer.pipeline import analyze_query


ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"

app = FastAPI(title="SmartFlow", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
class NoCacheStatic(StaticFiles):
    def is_not_modified(self, *args, **kwargs) -> bool:
        return False

    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        return resp


app.mount("/static", NoCacheStatic(directory=str(STATIC)), name="static")


class AnalyzeBody(BaseModel):
    query: str = Field(..., min_length=1, max_length=800)


@app.get("/")
def index():
    return FileResponse(
        STATIC / "index.html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


@app.get("/api/health")
def health():
    return {"ok": True, "service": "smartflow"}


@app.post("/api/analyze")
def analyze(body: AnalyzeBody):
    try:
        return analyze_query(body.query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"خطای داخلی تحلیل: {exc}") from exc


@app.get("/api/analyze")
def analyze_get(q: str):
    return analyze(AnalyzeBody(query=q))


if __name__ == "__main__":
    import sys

    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args and args[0] not in ("serve", "server"):
        from analyzer.pipeline import analyze_query

        print(analyze_query(" ".join(args))["report"])
    else:
        uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
