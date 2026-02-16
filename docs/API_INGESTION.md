# Error Ingestion API Documentation

## Overview

The Expert Diagnostic Engine provides an HTTP API for external systems to submit errors programmatically.  
Submitted errors appear in the **Incoming Errors** queue on the dashboard where an operator can review, diagnose, and resolve them.

---

## Authentication

Every request must include a **client API key** in the `X-Client-Key` header.

```
X-Client-Key: <your-client-key>
```

Client keys are managed from the web dashboard under **API Keys**.  
A key is shown only once at creation time — store it securely.

---

## Base URL

```
https://<your-host>/api/v1
```

Replace `<your-host>` with the actual hostname or IP of the deployment.

---

## Endpoints

### 1. List available experts

```
GET /api/v1/ingest/experts
```

Returns all active experts. Use the returned `id` in the `expert_id` field when submitting errors to target a specific expert for diagnosis.

**Headers**

| Header          | Required | Description         |
|-----------------|----------|---------------------|
| `X-Client-Key`  | Yes      | Client API key      |

**Example Request**

```bash
curl https://example.com/api/v1/ingest/experts \
  -H "X-Client-Key: YOUR_CLIENT_KEY"
```

**Response — 200 OK**

```json
[
  {
    "id": 1,
    "name": "Kubernetes Expert",
    "description": "Specializes in K8s cluster issues",
    "is_active": true,
    "document_count": 12,
    "system_prompt": "You are an expert diagnostic Kubernetes specialist...\n\n## Guidelines\n..."
  },
  {
    "id": 2,
    "name": "Database Expert",
    "description": "PostgreSQL and MySQL troubleshooting",
    "is_active": true,
    "document_count": 8,
    "system_prompt": "You are an expert diagnostic Database specialist...\n\n## Guidelines\n..."
  }
]
```

> **Note:** The `system_prompt` field contains the active system prompt for each expert.
> External agents can use this to understand what domain/instructions each expert is configured with.
> The field is `null` if no active system prompt is assigned.

---

### 2. Submit a single error

```
POST /api/v1/ingest
```

**Headers**

| Header          | Required | Description         |
|-----------------|----------|---------------------|
| `X-Client-Key`  | Yes      | Client API key      |
| `Content-Type`  | Yes      | `application/json`  |

**Request Body**

| Field           | Type   | Required | Max Length | Description |
|-----------------|--------|----------|------------|-------------|
| `error_text`    | string | Yes      | 50 000     | The full error message / stack trace |
| `expert_id`     | int    | Yes      | —          | Target expert ID (from `GET /v1/ingest/experts`). Determines which expert system diagnoses the error |
| `source_system` | string | No       | 200        | Identifier of the source system (e.g. `"prod-k8s"`, `"jenkins-ci"`) |
| `metadata`      | object | No       | —          | Arbitrary key-value metadata stored with the incident |

**Example Request**

```bash
curl -X POST https://example.com/api/v1/ingest \
  -H "Content-Type: application/json" \
  -H "X-Client-Key: YOUR_CLIENT_KEY" \
  -d '{
    "error_text": "java.lang.NullPointerException: Cannot invoke method on null object\n\tat com.app.Service.process(Service.java:42)\n\tat com.app.Controller.handle(Controller.java:18)",
    "expert_id": 1,
    "source_system": "prod-api-server",
    "metadata": {
      "host": "api-node-03",
      "environment": "production",
      "severity": "critical"
    }
  }'
```

**Response — 200 OK**

```json
{
  "incident_id": 42,
  "session_id": "a3f1b2c4-5d6e-7f8a-9b0c-1d2e3f4a5b6c",
  "status": "created"
}
```

---

### 3. Submit a batch of errors

```
POST /api/v1/ingest/batch
```

Submit up to **100 errors** in a single request.

**Headers**

Same as the single endpoint.

**Request Body**

| Field    | Type  | Required | Description |
|----------|-------|----------|-------------|
| `errors` | array | Yes      | Array of error objects (1–100 items) |

Each error object uses the same schema as the single endpoint (`error_text`, `expert_id`, `source_system`, `metadata`).

**Example Request**

```bash
curl -X POST https://example.com/api/v1/ingest/batch \
  -H "Content-Type: application/json" \
  -H "X-Client-Key: YOUR_CLIENT_KEY" \
  -d '{
    "errors": [
      {
        "error_text": "TimeoutError: Connection timed out after 30s",
        "expert_id": 1,
        "source_system": "payment-service"
      },
      {
        "error_text": "MemoryError: Unable to allocate 2.0 GiB",
        "expert_id": 2,
        "source_system": "ml-pipeline",
        "metadata": { "model": "fraud-detection-v3" }
      }
    ]
  }'
```

**Response — 200 OK**

```json
{
  "ingested": [
    {
      "incident_id": 43,
      "session_id": "...",
      "status": "created"
    },
    {
      "incident_id": 44,
      "session_id": "...",
      "status": "created"
    }
  ],
  "total": 2
}
```

---

## Rate Limits

| Endpoint        | Limit           |
|-----------------|-----------------|
| `POST /v1/ingest`       | 60 requests / minute |
| `POST /v1/ingest/batch` | 10 requests / minute |

Exceeding the rate limit returns **429 Too Many Requests**.

---

## Incident Status Workflow

Each ingested error follows this lifecycle:

```
created  →  in_review  →  analyzed  →  closed
```

| Status           | Description |
|------------------|-------------|
| `created`        | Just received via the API; visible in the Incoming tab |
| `pending_review` | Acknowledged by the system; waiting for operator |
| `in_review`      | An operator has opened the error and is diagnosing it |
| `analyzed`       | Diagnosis complete; results saved to the incident |
| `closed`         | Operator has closed the incident after review |
| `resolved`       | Used for manually created diagnoses (immediate) |

The status transitions happen automatically as operators interact with errors in the dashboard:
- Opening an incoming error sets it to `in_review`.
- Running a diagnosis on it sets it to `analyzed`.
- Clicking "Close" moves it to `closed`.

Manually created errors (via the dashboard) start as `resolved` immediately.

---

## Error Responses

| HTTP Code | Meaning |
|-----------|---------|
| `401`     | Missing `X-Client-Key` header |
| `403`     | Invalid or inactive client key |
| `422`     | Validation error (missing/invalid fields) |
| `429`     | Rate limit exceeded |
| `500`     | Internal server error |

**Validation Error Example (422)**

```json
{
  "detail": [
    {
      "loc": ["body", "error_text"],
      "msg": "String should have at least 1 character",
      "type": "string_too_short"
    }
  ]
}
```

---

## Integration Examples

### Python

```python
import requests

API_URL = "https://example.com/api/v1/ingest"
CLIENT_KEY = "your-client-key"

response = requests.post(
    API_URL,
    headers={
        "Content-Type": "application/json",
        "X-Client-Key": CLIENT_KEY,
    },
    json={
        "error_text": "RuntimeError: maximum recursion depth exceeded",
        "expert_id": 1,
        "source_system": "data-pipeline",
    },
)

print(response.json())
```

### Node.js

```javascript
const response = await fetch("https://example.com/api/v1/ingest", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-Client-Key": "your-client-key",
  },
  body: JSON.stringify({
    error_text: "TypeError: Cannot read properties of undefined",
    expert_id: 1,
    source_system: "web-app",
  }),
});

const result = await response.json();
console.log(result);
```

### Shell Script (batch from log file)

```bash
#!/bin/bash
# Extract recent errors and submit as a batch
errors=$(grep -A3 "ERROR" /var/log/app.log | jq -Rs '
  split("\n--\n") | map(select(length > 0)) |
  map({error_text: ., expert_id: 1, source_system: "app-server"})
')

curl -X POST https://example.com/api/v1/ingest/batch \
  -H "Content-Type: application/json" \
  -H "X-Client-Key: $CLIENT_KEY" \
  -d "{\"errors\": $errors}"
```

---

## Getting a Client Key

1. Open the dashboard at `https://<your-host>`
2. Navigate to **API Keys** in the top navigation
3. Enter a name (e.g. `"CI Pipeline"`) and optional description
4. Click **Generate Key**
5. **Copy the key immediately** — it will not be shown again
6. Use the key in the `X-Client-Key` header for all API requests
