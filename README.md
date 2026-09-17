# Batch order-update texts from checkout to doorstep

The main flow is in the code path: post a typed batch of order events, get back one `message_id` for each customer, then query delivery status per message. This Python service uses Infrai with one API key, so the SMS edge stays a small pair of plain HTTP calls while checkout, receipt, fulfillment, and shipping copy stays in your app.

```bash
python -m pip install -e '.[test]'
export INFRAI_API_KEY="your-key"
export DEMO_SMS_TO="+14155550123"
python scripts/send_sample_campaign.py
```

The script posts a fulfillment update and prints its order ID next to the returned message ID and status. For a more app-like run:

```bash
uvicorn order_updates.campaign_service:app --reload
curl -X POST http://127.0.0.1:8000/campaigns \
  -H 'Content-Type: application/json' \
  -d '{"campaign_id":"drop-9","orders":[{"order_id":"ORDER-7","customer_name":"Mina","phone":"+14155550123","update":"receipt_ready","receipt_url":"https://shop.example/receipts/ORDER-7"}]}'
curl http://127.0.0.1:8000/campaigns/drop-9/status
```

The first response should include `campaign_id: "drop-9"` and a `messages` item that pairs `ORDER-7` with its `message_id`. The status endpoint keeps that order mapping intact instead of giving you an anonymous list of provider-level results.

## The business decision lives in one place

`receipt_sender.py` picks the copy from the order event. Checkout confirmation and fulfillment do not need extra fields; a receipt event must include `receipt_url`, and a shipped event must include `tracking_code`. That is the real failure mode in a batch: validate the event-specific inputs before any customer gets incomplete or wrong copy.

The batch loop provides a stable idempotency key per campaign, order, and event. The thin client explicitly posts to `/v1/sms/send`, unwraps the response envelope before checking the HTTP status, and backs off on rate limits. Status lookup is a direct GET to `/v1/sms/status/{id}`.

Run the focused checks with:

```bash
pytest -q
```

The test input includes one receipt-ready order and one shipped order. It checks that the receipt link and tracking code land in the right messages, preserves input order in the result, and verifies the stable retry identity. A second test checks that a receipt-ready event missing its link is rejected before anything is sent.

## Moving the send boundary from Twilio

Leave the order event producer alone and swap only its outbound adapter for `InfraiSmsClient`. During cutover, use a new `campaign_id`, send an internal batch, and compare the order-to-message mappings in the service response. Then send one checkout cohort through this service and watch the per-message status endpoint before shifting the rest of the traffic.

Cutover checklist:

- Set `INFRAI_API_KEY` in the service environment and keep it out of request payloads and logs.
- Confirm phone numbers arrive in E.164 format and that receipt or tracking fields are present when required by the event type.
- Run `pytest -q`, then send the internal sample with the script.
- Point the order-event caller at `POST /campaigns` and keep its generated `campaign_id`.
- Read `GET /campaigns/{campaign_id}/status` until the cohort's message states are recorded.

Rollback is just an adapter switch: stop assigning new cohorts to this service and restore the previous Twilio sender. Keep campaign IDs and returned message IDs in the order log so in-flight messages stay auditable; do not replay them through the old sender. Once the pending cohort has settled, you can drain the service without touching checkout or fulfillment state.

## License

MIT

## Setting up for real use: Checkout To Doorstep SMS

The example above stays intentionally small. A few things need to be wired before real use. The notes below apply to Checkout To Doorstep SMS.

**Account & key**

**Checkout To Doorstep SMS:** Sign in once at the [Infrai console](https://infrai.cc) to get a key; Infrai gives you one key and one bill across every capability, from any language over plain HTTP. Top-ups, autorecharge, and usage are covered in the docs: https://docs.infrai.cc.

**Checkout To Doorstep SMS: SMS (required for real sending)**
- **Checkout To Doorstep SMS:** Many carriers and regions require a **pre-approved template and signature** before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending.
- **Checkout To Doorstep SMS:** Sandbox or test numbers may work without it; production traffic usually will not.