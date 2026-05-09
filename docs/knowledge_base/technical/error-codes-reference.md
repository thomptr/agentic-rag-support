# Error Codes Reference

## HTTP Status Codes

| Status Code | Meaning | Common Cause |
|---|---|---|
| 200 | OK | Request succeeded |
| 201 | Created | Resource successfully created |
| 204 | No Content | Request succeeded, no response body |
| 400 | Bad Request | Invalid request format or missing required fields |
| 401 | Unauthorized | Missing or invalid API key |
| 403 | Forbidden | Valid key but insufficient permissions |
| 404 | Not Found | Resource does not exist |
| 409 | Conflict | Resource already exists or state conflict |
| 422 | Unprocessable Entity | Request format valid but business validation failed |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Unexpected server error |
| 503 | Service Unavailable | Platform maintenance or outage |

## Application Error Codes

All API error responses follow this format:
```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Human-readable description",
    "details": {}
  }
}
```

### Authentication Errors (AUTH_*)

| Code | Description | Resolution |
|---|---|---|
| AUTH_KEY_MISSING | No API key in request | Add `Authorization: Bearer YOUR_KEY` header |
| AUTH_KEY_INVALID | Key format invalid | Check key was copied correctly |
| AUTH_KEY_REVOKED | Key has been revoked | Generate a new API key |
| AUTH_KEY_EXPIRED | Key has expired (if expiry set) | Rotate the key |
| AUTH_INSUFFICIENT_SCOPE | Key lacks required permission | Use a key with appropriate scope |

### Validation Errors (VALIDATION_*)

| Code | Description | Resolution |
|---|---|---|
| VALIDATION_FAILED | One or more fields invalid | Check `details` for field-specific errors |
| VALIDATION_REQUIRED_FIELD | Required field missing | Include all required fields |
| VALIDATION_FIELD_TOO_LONG | Field exceeds max length | Truncate the field value |
| VALIDATION_INVALID_FORMAT | Field format incorrect | Check format requirements (e.g., UUID, email) |

### Resource Errors (RESOURCE_*)

| Code | Description | Resolution |
|---|---|---|
| RESOURCE_NOT_FOUND | Resource with given ID not found | Verify the ID is correct |
| RESOURCE_ALREADY_EXISTS | Duplicate resource | Use PUT to update or provide unique identifier |
| RESOURCE_DELETED | Resource was soft-deleted | Restore or use a different resource |

### Rate Limit Errors (RATE_*)

| Code | Description | Resolution |
|---|---|---|
| RATE_LIMIT_EXCEEDED | Too many requests | Wait for `X-RateLimit-Reset`, implement backoff |
| RATE_LIMIT_BURST_EXCEEDED | Burst limit exceeded | Spread requests over time |

### Server Errors (SERVER_*)

| Code | Description | Resolution |
|---|---|---|
| SERVER_ERROR | Unexpected internal error | Retry with backoff; contact support if persistent |
| SERVER_TIMEOUT | Request processing timed out | Reduce payload size or use async endpoints |
| SERVER_MAINTENANCE | Planned maintenance | Check status.example.com for updates |

## Debugging Tips

1. Always log the full error response including `error.code` and `error.details`
2. Include the `X-Request-ID` response header when contacting support
3. Use our API explorer at api.example.com/docs to test requests interactively
