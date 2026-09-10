from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class OrderUpdate(StrEnum):
    CHECKOUT_CONFIRMED = "checkout_confirmed"
    RECEIPT_READY = "receipt_ready"
    FULFILLMENT_STARTED = "fulfillment_started"
    SHIPPED = "shipped"


@dataclass
class OrderMessage:
    order_id: str
    customer_name: str
    phone: str
    update: OrderUpdate
    receipt_url: str | None = None
    tracking_code: str | None = None

    def __post_init__(self) -> None:
        if not self.order_id:
            raise ValueError("order_id must not be empty")
        if not self.customer_name:
            raise ValueError("customer_name must not be empty")
        if not re.fullmatch(r"\+[1-9]\d{7,14}", self.phone):
            raise ValueError("phone must be an E.164 number")
        self.update = OrderUpdate(self.update)


@dataclass
class CampaignRequest:
    campaign_id: str
    orders: list[OrderMessage]

    def __post_init__(self) -> None:
        if not self.campaign_id:
            raise ValueError("campaign_id must not be empty")
        if not 1 <= len(self.orders) <= 100:
            raise ValueError("orders must contain between 1 and 100 items")


@dataclass
class SentMessage:
    order_id: str
    message_id: str


@dataclass
class CampaignResult:
    campaign_id: str
    messages: list[SentMessage]


def render_customer_update(order: OrderMessage) -> str:
    if order.update is OrderUpdate.CHECKOUT_CONFIRMED:
        return f"Hi {order.customer_name}, order {order.order_id} is confirmed. We will text again when fulfillment starts."
    if order.update is OrderUpdate.RECEIPT_READY:
        if not order.receipt_url:
            raise ValueError("receipt_url is required for receipt_ready")
        return f"Hi {order.customer_name}, your receipt for order {order.order_id}: {order.receipt_url}"
    if order.update is OrderUpdate.FULFILLMENT_STARTED:
        return f"Hi {order.customer_name}, fulfillment has started for order {order.order_id}."
    if not order.tracking_code:
        raise ValueError("tracking_code is required for shipped")
    return f"Hi {order.customer_name}, order {order.order_id} shipped. Tracking: {order.tracking_code}"


async def send_campaign(request: CampaignRequest, sender: Any) -> CampaignResult:
    sent: list[SentMessage] = []
    for order in request.orders:
        data = await sender.send(
            to=order.phone,
            message=render_customer_update(order),
            idempotency_key=f"{request.campaign_id}:{order.order_id}:{order.update.value}",
        )
        sent.append(SentMessage(order_id=order.order_id, message_id=str(data["message_id"])))
    return CampaignResult(campaign_id=request.campaign_id, messages=sent)
