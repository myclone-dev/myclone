# Webhook Integration Hooks

TanStack Query hooks for managing account-level webhooks.

## Overview

- **Account-level configuration** - One webhook per account applies to all personas
- **HTTPS only** - HTTP URLs are blocked for security
- **Supported events**: `conversation.finished` (sent when voice conversation ends)
- **Supported providers**: Zapier, Make, n8n, Slack, Discord, custom HTTPS endpoints

## Quick Start

```tsx
import {
  useGetWebhook,
  useCreateWebhook,
  useUpdateWebhook,
  useDeleteWebhook,
  useWebhookHealth,
} from "@/lib/queries/webhooks";

function WebhookSettings() {
  // Fetch current webhook config (account-level)
  const { data: webhook, isLoading } = useGetWebhook();

  // Mutations
  const createWebhook = useCreateWebhook();
  const updateWebhook = useUpdateWebhook();
  const deleteWebhook = useDeleteWebhook();

  // Check system health (optional)
  const { data: health } = useWebhookHealth();

  const handleCreate = () => {
    createWebhook.mutate({
      url: "https://hooks.zapier.com/hooks/catch/123456/abcdef/",
      events: ["conversation.finished"],
      secret: "optional_secret_key", // Optional
    });
  };

  const handleToggle = () => {
    updateWebhook.mutate({
      enabled: !webhook?.enabled,
    });
  };

  const handleDelete = () => {
    deleteWebhook.mutate();
  };

  return (
    <div>
      {isLoading ? (
        <p>Loading...</p>
      ) : webhook?.enabled ? (
        <div>
          <p>Webhook URL: {webhook.url}</p>
          <p>Status: {webhook.enabled ? "Enabled" : "Disabled"}</p>
          <p>Applies to: {webhook.personas_count} personas</p>
          <button onClick={handleToggle}>Toggle</button>
          <button onClick={handleDelete}>Delete</button>
        </div>
      ) : (
        <button onClick={handleCreate}>Create Webhook</button>
      )}
    </div>
  );
}
```

## Hooks

### `useGetWebhook()`

Fetch webhook configuration for the account.

**Returns:** `WebhookConfigResponse | null`

```typescript
{
  enabled: boolean;
  url: string | null;
  events: ["conversation.finished"];
  has_secret: boolean;
  personas_count: number;
}
```

### `useCreateWebhook()`

Create or replace webhook configuration (account-level).

**Usage:**

```typescript
const createWebhook = useCreateWebhook();

createWebhook.mutate({
  url: "https://hooks.zapier.com/...", // Required, must be HTTPS
  events: ["conversation.finished"], // Optional, defaults to ["conversation.finished"]
  secret: "my_secret_key", // Optional, max 255 chars
});
```

### `useUpdateWebhook()`

Partially update webhook configuration. Only provided fields are updated.

**Usage:**

```typescript
const updateWebhook = useUpdateWebhook();

// Change URL only
updateWebhook.mutate({
  url: "https://hooks.make.com/new-url",
});

// Toggle enabled status
updateWebhook.mutate({
  enabled: false,
});

// Update events
updateWebhook.mutate({
  events: ["conversation.finished"],
});
```

### `useDeleteWebhook()`

Delete webhook configuration completely.

**Usage:**

```typescript
const deleteWebhook = useDeleteWebhook();

deleteWebhook.mutate();
```

### `useWebhookHealth()`

Check webhook system health and supported features (public endpoint).

**Returns:**

```typescript
{
  status: "healthy" | "unhealthy";
  message: string;
  supported_providers: ["zapier", "make", "n8n", "slack", "discord", "custom"];
  supported_events: ["conversation.finished"];
}
```

## Webhook Payload

When `conversation.finished` event fires, this payload is POSTed to your webhook URL:

```json
{
  "event": "conversation.finished",
  "timestamp": "2026-01-12T10:30:00Z",
  "persona": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "name": "Dr. Sarah Chen",
    "persona_name": "dr-sarah-ai"
  },
  "data": {
    "conversation_id": "conv_123",
    "duration_seconds": 180,
    "transcript": "Full conversation transcript...",
    "summary": "Brief summary of the conversation..."
  }
}
```

## Error Handling

All mutations include automatic error tracking via Sentry and toast notifications:

- **Success**: Toast notification shown automatically
- **Error**: Error message displayed in toast
- **Tracking**: All operations tracked with `trackDashboardOperation()`

## Security

- **HTTPS Required**: HTTP URLs are rejected by the backend
- **SSRF Protection**: Private IPs and localhost are blocked
- **Secret Storage**: Webhook secret is never exposed in API responses (only `has_secret` boolean)
- **Authentication**: All endpoints require JWT token

## Supported Providers

### Zapier

```typescript
{
  url: "https://hooks.zapier.com/hooks/catch/123456/abcdef/";
}
```

### Make (Integromat)

```typescript
{
  url: "https://hook.make.com/abc123def456";
}
```

### n8n

```typescript
{
  url: "https://your-n8n-instance.com/webhook/abc123";
}
```

### Slack

```typescript
{
  url: "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXX";
}
```

### Discord

```typescript
{
  url: "https://discord.com/api/webhooks/123456789/abc-def-ghi";
}
```

### Custom HTTPS Endpoint

```typescript
{
  url: "https://your-api.com/webhooks/persona-events",
  secret: "your_secret_key", // Use secret for signature verification
}
```

## Best Practices

1. **Always use HTTPS** - HTTP URLs are blocked for security
2. **Use webhook secrets** - For custom endpoints, always include a secret for signature verification
3. **Handle errors gracefully** - Webhook delivery failures are retried automatically by the backend
4. **Test your endpoint** - Use the health check to verify system status before configuring
5. **Monitor delivery** - Check your webhook endpoint logs for successful deliveries
6. **Account-wide scope** - Remember that one webhook applies to all your personas

## API Endpoints

All endpoints are account-level and require JWT authentication:

- `POST /api/v1/account/webhook` - Create or replace webhook config
- `GET /api/v1/account/webhook` - Get webhook config
- `PATCH /api/v1/account/webhook` - Update webhook (partial)
- `DELETE /api/v1/account/webhook` - Delete webhook
- `GET /api/v1/personas/webhook/health` - Health check (public endpoint)
