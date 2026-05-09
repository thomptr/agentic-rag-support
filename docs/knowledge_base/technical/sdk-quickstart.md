# SDK Quickstart

## Overview

Our SDKs provide idiomatic client libraries for the most common languages. This guide covers installation, authentication, and your first API call.

**Prerequisite**: You need an API key. See the **API Key Management** document for instructions on creating one. API access requires a Professional or Enterprise plan.

## Installation

### Python

```bash
pip install example-sdk
# or with poetry
poetry add example-sdk
```

Requires Python 3.8+.

### Node.js

```bash
npm install @example/sdk
# or with yarn
yarn add @example/sdk
```

Requires Node.js 16+.

### Go

```bash
go get github.com/example/sdk-go
```

Requires Go 1.19+.

## Authentication Setup

Store your API key as an environment variable — never hardcode it in source files.

```bash
# .env file or shell
export EXAMPLE_API_KEY="your-api-key-here"
```

The SDK reads `EXAMPLE_API_KEY` automatically. You can also pass it explicitly:

### Python

```python
from example_sdk import Client

# Reads EXAMPLE_API_KEY from environment automatically
client = Client()

# Or pass explicitly
client = Client(api_key="your-api-key-here")
```

### Node.js

```javascript
const { Client } = require('@example/sdk');

// Reads EXAMPLE_API_KEY from environment automatically
const client = new Client();

// Or pass explicitly
const client = new Client({ apiKey: 'your-api-key-here' });
```

### Go

```go
import "github.com/example/sdk-go"

// Reads EXAMPLE_API_KEY from environment automatically
client := example.NewClient()

// Or pass explicitly
client := example.NewClient(example.WithAPIKey("your-api-key-here"))
```

## First API Call

### Python

```python
from example_sdk import Client

client = Client()
response = client.resources.list()
print(response.items)
```

### Node.js

```javascript
const { Client } = require('@example/sdk');

const client = new Client();
const response = await client.resources.list();
console.log(response.items);
```

### Go

```go
resp, err := client.Resources.List(context.Background(), nil)
if err != nil {
    log.Fatal(err)
}
fmt.Println(resp.Items)
```

## Common Setup Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `401 Unauthorized` | API key missing, invalid, or revoked | Verify key in Account Settings → Developer → API Keys |
| `403 Forbidden` | API key lacks required permission scope | Regenerate key with Read/Write scope |
| `429 Too Many Requests` | Rate limit exceeded | Implement exponential backoff; see Rate Limits document |
| `Connection refused` | Wrong base URL or network issue | Confirm the SDK's base URL matches your account region |
| `SSLError` | Certificate issue in some corporate networks | Ensure system CA bundle is up to date |

## Rate Limits

API calls are subject to rate limits based on your plan. When you exceed the limit, you receive a `429 Too Many Requests` response. See the **Rate Limits** document for per-plan limits, response headers, and how to implement backoff.

## Related Documents

- **API Key Management**: Creating, rotating, and revoking API keys
- **Rate Limits**: Per-plan limits and handling 429 responses
- **Error Codes Reference**: Full list of error codes and resolutions
