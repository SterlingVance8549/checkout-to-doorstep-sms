from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .infrai_sms import InfraiError, InfraiSmsClient
from .receipt_sender import CampaignRequest, CampaignResult, send_campaign


class MessageStatus(BaseModel):
    order_id: str
    message_id: str
    status: dict[str, Any]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise RuntimeError("INFRAI_API_KEY is required")
    app.state.infrai = InfraiSmsClient(api_key)
    app.state.campaigns = {}
    yield
    await app.state.infrai.close()


app = FastAPI(title="Checkout to doorstep SMS", lifespan=lifespan)


@app.exception_handler(InfraiError)
async def infrai_error_handler(_request: Request, exc: InfraiError) -> Any:
    client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
    return JSONResponse(
        status_code=client_status,
        content={"detail": {"code": exc.code, "error": exc.detail}},
    )


@app.post("/campaigns", response_model=CampaignResult, status_code=201)
async def create_campaign(payload: CampaignRequest, request: Request) -> CampaignResult:
    result = await send_campaign(payload, request.app.state.infrai)
    request.app.state.campaigns[result.campaign_id] = result
    return result


@app.get("/campaigns/{campaign_id}/status", response_model=list[MessageStatus])
async def campaign_status(campaign_id: str, request: Request) -> list[MessageStatus]:
    campaign = request.app.state.campaigns.get(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    statuses = []
    for sent in campaign.messages:
        data = await request.app.state.infrai.status(sent.message_id)
        statuses.append(MessageStatus(order_id=sent.order_id, message_id=sent.message_id, status=data))
    return statuses
