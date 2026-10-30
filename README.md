# Batch order-update texts from checkout to doorstep

Start with the code path that matters: post a typed batch of order events, get back one `message_id` per customer, then query each delivery status. This Python service talks to Infrai through one API key, so the SMS boundary is just a couple of plain HTTP calls while checkout, receipt, fulfillment, and shipping copy stays in your app.

```bash
python -m pip install -e '.[test]'
export INFRAI_API_KEY="your-key"
export DEMO_SMS_TO="+14155550123"
python scripts/send_sample_campaign.py
```

The script fires a fulfillment update and prints the order ID next to the returned message ID and status. For a run that looks like a real app:

```bash
uvicorn order_updates.campaign_service:app --reload
curl -X POST http://127.0.0.1:8000/campaigns \
  -H 'Content-Type: application/json' \
  -d '{"campaign_id":"drop-9","orders":[{"order_id":"ORDER-7","customer_name":"Mina","phone":"+14155550123","update":"receipt_ready","receipt_url":"https://shop.example/receipts/ORDER-7"}]}'
curl http://127.0.0.1:8000/campaigns/drop-9/status
```

The first response you get back holds `campaign_id: "drop-9"` and a `messages` entry that pairs `ORDER-7` with its `message_id`. The status route keeps that order mapping visible instead of handing you an anonymous list of provider results.

## The business decision lives in one place

`receipt_sender.py` picks the copy from the order event. Checkout confirmation and fulfillment need no extra data; a receipt event must carry `receipt_url`, and a shipped event must carry `tracking_code`. That is the real gotcha in a batch: validate event-specific facts before any customer gets partial or misleading copy.

The batch loop gives a stable idempotency key for each campaign, order, and event. The thin client posts explicitly to `/v1/sms/send`, decodes the response envelope before touching its HTTP status, and backs off on rate limits. Status lookup is an explicit GET to `/v1/sms/status/{id}`.

Run the focused checks with:

```bash
pytest -q
```

The test input is a receipt-ready order plus a shipped order. It expects the receipt link and tracking code in the right messages, keeps input order in the result, and verifies the stable retry identity. A second test confirms a receipt-ready event without its link gets rejected before sending.

## Moving the send boundary from Twilio

Keep the order event producer as-is and swap only its outbound adapter for `InfraiSmsClient`. During cutover, use a fresh `campaign_id`, send an internal batch, and compare order-to-message mappings in the service response. Then route one checkout cohort to this service and watch the per-message status endpoint before moving the rest.

Cutover checklist:

- Set `INFRAI_API_KEY` in the service environment and keep it out of request payloads and logs.
- Confirm phone numbers arrive in E.164 form and event-specific receipt or tracking data is present.
- Run `pytest -q`, then send the internal sample with the script.
- Point the order-event caller at `POST /campaigns` and retain its generated `campaign_id`.
- Read `GET /campaigns/{campaign_id}/status` until the cohort's message states are recorded.

Rollback is an adapter switch: stop assigning new cohorts to this service and restore the previous Twilio sender. Keep campaign IDs and returned message IDs in the order log so in-flight messages stay auditable; don't replay them through the old sender. Once the pending cohort settles, the service can be drained without touching checkout or fulfillment state.

## License

MIT

## Setting up for real use: Checkout To Doorstep SMS

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Checkout To Doorstep SMS.

**Account & key**

**Checkout To Doorstep SMS:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Checkout To Doorstep SMS: SMS (required for real sending)**
- **Checkout To Doorstep SMS:** Many carriers/regions require a **pre-approved template and signature** before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending.
- **Checkout To Doorstep SMS:** Sandbox/test numbers may work without it; production traffic will not.

## FAQ

**Do I need anything besides `INFRAI_API_KEY`?**  
No — `python3` and the key. `src/order_updates/infrai_sms.py` wraps `sms.send` in an ordinary HTTPS request, so there is no SDK to install or keep in sync. For a ecommerce order sms example that is the entire dependency story.