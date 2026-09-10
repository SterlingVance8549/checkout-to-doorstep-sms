import asyncio

import pytest

from order_updates.receipt_sender import (
    CampaignRequest,
    OrderMessage,
    OrderUpdate,
    render_customer_update,
    send_campaign,
)


class RecordingSender:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    async def send(self, *, to: str, message: str, idempotency_key: str) -> dict[str, object]:
        self.calls.append({"to": to, "message": message, "idempotency_key": idempotency_key})
        return {"message_id": f"msg-{len(self.calls)}"}


def test_receipt_update_requires_a_receipt_link() -> None:
    order = OrderMessage(
        order_id="ORDER-7",
        customer_name="Mina",
        phone="+14155550123",
        update=OrderUpdate.RECEIPT_READY,
    )
    with pytest.raises(ValueError, match="receipt_url is required"):
        render_customer_update(order)


def test_batch_preserves_order_mapping_and_retry_identity() -> None:
    sender = RecordingSender()
    request = CampaignRequest(
        campaign_id="drop-9",
        orders=[
            OrderMessage(
                order_id="ORDER-7",
                customer_name="Mina",
                phone="+14155550123",
                update=OrderUpdate.RECEIPT_READY,
                receipt_url="https://shop.example/receipts/ORDER-7",
            ),
            OrderMessage(
                order_id="ORDER-8",
                customer_name="Noah",
                phone="+14155550124",
                update=OrderUpdate.SHIPPED,
                tracking_code="TRACK-8",
            ),
        ],
    )

    result = asyncio.run(send_campaign(request, sender))

    assert [item.order_id for item in result.messages] == ["ORDER-7", "ORDER-8"]
    assert sender.calls[0]["idempotency_key"] == "drop-9:ORDER-7:receipt_ready"
    assert "receipts/ORDER-7" in sender.calls[0]["message"]
    assert "TRACK-8" in sender.calls[1]["message"]

