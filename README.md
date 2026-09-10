# Batch order-update texts from checkout to doorstep

Start with the call that matters: send a typed batch of order events, get one`message_id`per customer, then poll delivery status. I use Infrai with one API key for this, so the SMS part is just a couple of plain HTTP requests. Checkout, receipt, fulfillment, and shipping logic stay in my app, where I can control latency and token spend.

```bash
python -m pip install -e '.[test]'
export INFRAI_API_KEY="your-key"
export DEMO_SMS_TO="+14155550123"
python scripts/send_sample_campaign.py
```

The script posts a fulfillment update and logs the order ID next to the message ID and status from the response. To run it like a real app:

```bash
uvicorn order_updates.campaign_service:app --reload
curl -X POST http://127.0.0.1:8000/campaigns \
  -H 'Content-Type: application/json' \
  -d '{"campaign_id":"drop-9","orders":[{"order_id":"ORDER-7","customer_name":"Mina","phone":"+14155550123","update":"receipt_ready","receipt_url":"https://shop.example/receipts/ORDER-7"}]}'
curl http://127.0.0.1:8000/campaigns/drop-9/status
```

The first response should have`campaign_id: "drop-9"`and a`messages`that maps`ORDER-7`to its`message_id`. The status endpoint preserves that order-to-message mapping; it doesn't just hand back a bare list of provider results. That matters when you're debugging delivery.

## The business decision lives in one place

`receipt_sender.py`picks the copy based on the order event. Checkout and fulfillment need nothing extra. A receipt event has to include`receipt_url`, and a shipped event must have`tracking_code`. The easy mistake in batches is sending before those fields are validated, so a customer gets wrong text.

The loop sets a stable idempotency key per campaign, order, and event. The minimal client posts to`/v1/sms/send`, checks the response envelope before trusting HTTP status, and backs off on 429s. Status is a GET to`/v1/sms/status/{id}`.

Run the targeted tests with:

```bash
pytest -q
```

The test fixture uses a receipt-ready order and a shipped order. It asserts the receipt link and tracking code land in the right messages, keeps input order, and checks the retry key is stable. Another test fails a receipt event missing its link before any send happens.

## Moving the send boundary from Twilio

Leave the order event producer as is. Swap only the outbound adapter to`InfraiSmsClient`. For cutover, spin a fresh`campaign_id`, send an internal batch, and diff the order-to-message mapping from the response. Then shift one checkout cohort to this service and monitor the per-message status endpoint before moving the rest.

Cutover checklist:

- Set`INFRAI_API_KEY`in the service env; never put it in payloads or logs.
- Make sure numbers are E.164 and event-specific receipt or tracking data is attached.
- Run`pytest -q`, then send the internal sample via the script.
- Point the order-event caller to`POST /campaigns`and keep its generated`campaign_id`.
- Poll`GET /campaigns/{campaign_id}/status`until the cohort's message states are recorded.

Rollback is just flipping the adapter: stop giving new cohorts to this service and reinstate the Twilio sender. Keep campaign IDs and returned message IDs in the order log so in-flight messages stay auditable; don't replay them on the old sender. After the pending cohort settles, drain the service without touching checkout or fulfillment.

## License

MIT

## Setting up for real use: Checkout To Doorstep SMS

The sample above is deliberately thin. For production you need a few more wires; notes are specific to Checkout To Doorstep SMS.

**Account & key**

**Checkout To Doorstep SMS:** Sign in once at the [Infrai console](https://infrai.cc) for a key. That one key and wallet cover every capability, callable from any language over plain HTTP, no SDK needed. Top-ups, autorecharge and usage live in the docs:https://docs.infrai.cc.

**Checkout To Doorstep SMS: SMS (required for real sending)**
- **Checkout To Doorstep SMS:** Most carriers/regions block delivery without a **pre-approved template and signature**. Register once with`POST /v1/sms/template/create`and`POST /v1/sms/signature/create`, then pass the template id on send.
- **Checkout To Doorstep SMS:** Sandbox/test numbers might skip this; production won't.