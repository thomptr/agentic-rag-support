# Integration Setup Guide

## Overview

Our platform supports integrations with 50+ third-party services. This guide covers how to set up, configure, and troubleshoot integrations.

## Finding and Installing Integrations

1. Navigate to Settings → Integrations
2. Browse by category or search by name
3. Click the integration to view details and required permissions
4. Click "Install" and follow the OAuth authorization flow

## OAuth-Based Integrations

For integrations using OAuth (e.g., Slack, Google Workspace, Salesforce):

1. Click "Connect" on the integration page
2. You are redirected to the third-party authorization page
3. Grant the requested permissions
4. You are redirected back to our platform — the integration is now active

**Revoking OAuth access**: To revoke, go to Settings → Integrations → [Integration Name] → Disconnect. Also revoke access in the third-party app's authorized applications settings.

## API-Based Integrations

For integrations requiring an API key from the third party:

1. Obtain an API key from the third-party service
2. Navigate to Settings → Integrations → [Integration Name]
3. Enter the API key in the "API Key" field
4. Click "Test Connection" to verify
5. Click "Save"

## Webhook Integrations

To receive data from external services:

1. Navigate to Settings → Integrations → Webhooks
2. Click "Add Webhook Endpoint"
3. Enter your endpoint URL (must be HTTPS)
4. Select the event types to subscribe to
5. Copy the webhook signing secret — use this to verify payloads:
   ```python
   import hmac, hashlib
   
   def verify_webhook(payload_bytes, signature_header, secret):
       expected = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
       return hmac.compare_digest(f"sha256={expected}", signature_header)
   ```

## Data Sync Frequency

| Integration Type | Sync Frequency |
|---|---|
| Real-time (webhooks) | Instant |
| Polling (API) | Every 15 minutes |
| Batch imports | Daily at 2:00 AM UTC |

## Troubleshooting Integrations

**Integration shows "Disconnected"**:
- OAuth token may have expired — click "Reconnect"
- API key may have been rotated — update the key in settings

**Data not syncing**:
- Check the integration's last sync time in Settings → Integrations → [Integration] → Logs
- Verify the third-party service is operational
- Check that the integration has the required permissions/scopes

**Duplicate data**:
- Check deduplication settings in Settings → Integrations → [Integration] → Advanced
- Ensure your webhook endpoint is not processing the same event multiple times (implement idempotency using the event `id` field)
