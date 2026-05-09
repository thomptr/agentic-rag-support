# API Key Management

## Overview

API keys allow your applications to authenticate with our platform programmatically. Each API key is tied to your account and inherits your account's permissions.

## Creating an API Key

1. Log in to your account
2. Navigate to Settings → Developer → API Keys
3. Click "Generate New Key"
4. Enter a descriptive name for the key (e.g., "Production App", "CI/CD Pipeline")
5. Select the key's permission scope:
   - **Read-only**: Can query data but cannot modify anything
   - **Read/Write**: Full access to create, update, and delete resources
   - **Admin**: Full access including user management (use with caution)
6. Click "Generate" — the key is shown once; copy it immediately
7. Store the key securely (e.g., environment variable, secrets manager)

## Rotating an API Key

API keys should be rotated every 90 days or immediately if compromised:
1. Navigate to Settings → Developer → API Keys
2. Click "Rotate" next to the key you want to replace
3. A new key is generated — copy it immediately
4. Update your application with the new key
5. The old key remains valid for 24 hours (transition window), then is revoked

## Revoking an API Key

To immediately invalidate a key (e.g., suspected compromise):
1. Navigate to Settings → Developer → API Keys
2. Click "Revoke" next to the key
3. Confirm revocation — this is immediate and cannot be undone
4. Any application using the revoked key will receive 401 Unauthorized responses

## API Key Best Practices

- Never hardcode API keys in source code
- Use environment variables or a secrets manager (AWS Secrets Manager, HashiCorp Vault)
- Use the least-privilege scope required
- Monitor API key usage in Settings → Developer → Usage Logs
- Rotate keys regularly and revoke unused keys

## Troubleshooting: 401 Unauthorized

If you receive a 401 error:
1. Verify the key is correctly copied (no extra spaces)
2. Confirm the key has not been revoked
3. Check the key's permission scope matches the operation attempted
4. Ensure the Authorization header format is correct: `Authorization: Bearer YOUR_API_KEY`
5. Check if your IP is on the allowlist (if IP restriction is enabled)

## API Rate Limits

| Plan | Requests/minute | Requests/day |
|------|----------------|--------------|
| Basic | 60 | 10,000 |
| Professional | 300 | 100,000 |
| Enterprise | Custom | Unlimited |

Rate limit headers are included in every response: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.
