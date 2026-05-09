# Rate Limits

## Overview

Rate limits protect the platform from abuse and ensure fair resource allocation across all customers. Every API request counts against your rate limit.

## Rate Limit Tiers by Plan

| Plan | Requests/Minute | Requests/Day | Burst Allowance |
|------|----------------|--------------|-----------------|
| Basic | N/A (no API access) | N/A | N/A |
| Professional | 300 | 100,000 | 50 requests in any 5-second window |
| Enterprise | Custom (default: 1,000) | Unlimited | Negotiated per contract |

**Note**: Rate limits apply per API key. If you use multiple API keys under the same account, each key has its own limit.

## Rate Limit Response Headers

Every API response includes headers so your client can track usage:

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Your plan's total request limit per minute |
| `X-RateLimit-Remaining` | Remaining requests in the current window |
| `X-RateLimit-Reset` | Unix timestamp when the current window resets |

**Example response headers**:

```
X-RateLimit-Limit: 300
X-RateLimit-Remaining: 247
X-RateLimit-Reset: 1746789060
```

## Handling 429 Responses

When you exceed your rate limit, the API returns:

```
HTTP 429 Too Many Requests
Retry-After: 12
```

The `Retry-After` header indicates how many seconds to wait before retrying.

### Implementing Exponential Backoff

Use exponential backoff with jitter to avoid thundering-herd retries:

```python
import time
import random

def call_with_backoff(fn, max_retries=5):
    for attempt in range(max_retries):
        response = fn()
        if response.status_code != 429:
            return response
        wait = (2 ** attempt) + random.uniform(0, 1)
        time.sleep(wait)
    raise Exception("Max retries exceeded")
```

**Recommended wait times**:
- Attempt 1: ~2 seconds
- Attempt 2: ~4 seconds
- Attempt 3: ~8 seconds
- Attempt 4: ~16 seconds
- Attempt 5: ~32 seconds

Always add random jitter (0–1 second) to prevent synchronized retries from multiple clients.

## Requesting a Rate Limit Increase

If your application consistently hits rate limits:

1. Review your API usage patterns — consider caching responses to reduce redundant calls
2. If increased limits are genuinely needed, contact support with:
   - Your account ID
   - The API key hitting the limit
   - Estimated requests/minute and requests/day needed
   - Use case description
3. Enterprise customers can negotiate custom limits as part of their contract

**Response time**: Rate limit increase requests are reviewed within 3 business days for Professional plans and within 1 business day for Enterprise plans.

## How Plan Upgrades Affect Rate Limits

Upgrading your plan increases your rate limit immediately upon plan activation — you do not need to rotate your API key. The new limits are reflected in the `X-RateLimit-Limit` header on your next request after the upgrade.

If you downgrade your plan, rate limits are reduced at the end of the current billing period, not immediately.

## Rate Limits and Webhooks

Webhook delivery does not count against your API rate limits. Only outbound API calls from your application consume rate limit quota.

## Related Documents

- **API Key Management**: Creating and managing API keys
- **SDK Quickstart**: Example code for handling 429 responses
- **Subscription Management**: How plan changes affect API access
