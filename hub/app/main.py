"""Mimic Hub — FastAPI service skeleton. Plan §3.4 H-01."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Mimic Hub", version="0.2.0-alpha.0")


class ScenarioManifest(BaseModel):
    id: str
    name: str
    version: str
    author_did: str
    oci_digest: str
    sigstore_log_id: str | None = None


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}


@app.get("/search")
async def search(q: str | None = None, tier: str | None = None) -> list[ScenarioManifest]:
    raise HTTPException(status_code=501, detail="not implemented (H-01)")


@app.get("/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str) -> ScenarioManifest:
    raise HTTPException(status_code=501, detail="not implemented (H-01)")


@app.post("/publish")
async def publish() -> dict:
    raise HTTPException(status_code=501, detail="not implemented (H-01)")


@app.get("/badges/{scenario_id}")
async def get_badge(scenario_id: str) -> dict:
    raise HTTPException(status_code=501, detail="not implemented (H-05)")
