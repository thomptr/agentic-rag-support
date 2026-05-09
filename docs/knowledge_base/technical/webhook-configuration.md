# Webhook Configuration

## Overview

Webhooks allow your application to receive real-time notifications when events occur in your account. Instead of polling our API, your endpoint receives an HTTP POST whenever a relevant event fires.

**Plan availability**: Webhooks are available on Professional and Enterprise plans only. Basic plan accounts do not have access to webhooks.

| Plan | Max Webhook Endpoints |
|------|-----------------------|
| Basic | 0 (not available) |
| Professional | 5 |
| Enterprise | Unlimited |

## Setting Up a Webhook Endpoint

1. Go to **Settings → Developer → Webhooks**
2. Click **Add Endpoint**
3. Enter your HTTPS endpoint URL (HTTP endpoints are not accepted)
4. Select the event types to subscribe to (see below)
5. Click **Save** — a secret signing key is generated and shown once; copy it immediately

## Supported Event Types

| Event Type | Description |
|-----------|-------------|
| `user.created` | A new user was added to the account |
| `user.removed` | A user was removed from the account |
| `subscription.changed` | Plan upgrade or downgrade processed |
| `payment.succeeded` | A payment was successfully charged |
| `payment.failed` | A payment attempt failed |
| `api_key.created` | A new API key was generated |
| `api_key.revoked` | An API key was revoked |
| `data.export_ready` | A requested data export is ready for download |

## Payload Format

All webhook payloads are JSON with the following structure:

```json
{
  "event_id": "evt_01HXYZ...",
  "event_type": "payment.failed",
  "created_at": "2026-05-09T12:34:56Z",
  "account_id": "acct_abc123",
  "data": {
    "invoice_id": "inv_xyz789",
    "amount": 29.99,
    "currency": "USD",
    "failure_reason": "card_declined"
  }
}
```

## Signature Verification

Every webhook request includes an `X-Webhook-Signature` header. Verify it to ensure the request came from us and was not tampered with.

```python
import hmac
import hashlib

def verify_signature(payload_body: bytes, signature_header: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode(),
        payload_body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature_header)
```

**Always verify signatures** before processing webhook payloads. Reject any request where verification fails with a `400 Bad Request` response.

## Retry Policy for Failed Deliveries

If your endpoint does not respond with a 2xx status code within 10 seconds, the delivery is considered failed and retried automatically:

| Attempt | Delay |
|---------|-------|
| Attempt 2 | 5 minutes |
| Attempt 3 | 5 minutes |
| Attempt 4–24 | Every 1 hour |

After 24 hours of failed retries (approximately 24 attempts), the event is marked **permanently failed** and no further retries are made. You can replay failed events manually from the webhook logs.

## Webhook Logs

Delivery logs are available in **Settings → Developer → Webhooks → [Endpoint] → Delivery History**:

- Each delivery shows the event ID, timestamp, HTTP status received, and response body (truncated to 1 KB)
- Failed deliveries show the error reason
- Logs are retained for **30 days** on Professional, **90 days** on Enterprise

You can replay any event from the logs by clicking **Resend**.

## Troubleshooting

**Endpoint receives no events**: Verify your endpoint URL is publicly accessible and returns 2xx. Test using the **Send Test Event** button in the webhook settings.

**Signature verification failing**: Ensure you are comparing against the raw request body bytes, not a parsed/reformatted version. Confirm the correct secret is being used.

**Events arriving out of order**: Webhooks are not guaranteed to arrive in order. Use the `created_at` timestamp or maintain idempotency keys in your event processing.
