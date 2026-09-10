import asyncio
import os

from order_updates.infrai_sms import InfraiSmsClient
from order_updates.receipt_sender import CampaignRequest, OrderMessage, OrderUpdate, send_campaign


async def main() -> None:
    api_key = os.environ.get("INFRAI_API_KEY")
    phone = os.environ.get("DEMO_SMS_TO")
    if not api_key or not phone:
        raise SystemExit("Set INFRAI_API_KEY and DEMO_SMS_TO")

    client = InfraiSmsClient(api_key)
    try:
        result = await send_campaign(
            CampaignRequest(
                campaign_id="spring-drop-001",
                orders=[
                    OrderMessage(
                        order_id="ORDER-1042",
                        customer_name="Avery",
                        phone=phone,
                        update=OrderUpdate.FULFILLMENT_STARTED,
                    )
                ],
            ),
            client,
        )
        print(result.model_dump_json(indent=2))
        for sent in result.messages:
            status = await client.status(sent.message_id)
            print({"order_id": sent.order_id, "message_id": sent.message_id, "status": status})
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())

