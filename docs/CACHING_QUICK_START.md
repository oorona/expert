# Context Caching - Quick Start Guide

## What Was Implemented

✅ **Explicit context caching** for system prompts using Gemini API's caching feature
✅ **Automatic cache management** - creates, reuses, and invalidates caches
✅ **Cost optimization** - 75% discount on cached tokens
✅ **Admin endpoints** - monitor and manage caches
✅ **Complete documentation** - setup, testing, troubleshooting

## How to Use

### No Code Changes Required!

The caching system is **automatically enabled** for all diagnosis requests. Simply use the existing API as normal:

```bash
curl -X POST http://localhost:3000/api/diagnose \
  -F "error_text=Your error here" \
  -F "expert_id=1" \
  -F "model=gemini-2.5-flash"
```

### First Request
- Creates a cache for the system prompt
- Stores it for 1 hour (configurable)
- Normal token costs

### Subsequent Requests (Same Expert + Model)
- Automatically uses cached system prompt
- 75% discount on those tokens
- Faster response times

## Configuration (Optional)

Set cache TTL via environment variable:

```bash
# In docker-compose.yml or .env
CACHE_TTL_SECONDS=3600  # 1 hour (default)
```

Recommended values:
- **Development**: 300s (5 min) - prompts change frequently
- **Production**: 3600s (1 hour) - stable prompts, maximize savings

## Monitoring

### Check Cache Status

```bash
curl -H "X-Client-Key: YOUR_KEY" \
  http://localhost:8000/api/admin/cache/status
```

### Watch Logs

```bash
docker logs -f expert-backend | grep cache
```

Look for:
- `Creating new cache` → First request
- `Using existing cache` → Cache hit (saving money!)
- `cached_content_token_count: 2000` → Tokens that were cached

### Verify Savings

Check the `usage` field in API responses:

```json
{
  "usage": {
    "cached_content_token_count": 2000  ← > 0 means caching is working!
  }
}
```

## Files Modified

1. [backend/config.py](../backend/config.py) - Added `CACHE_TTL_SECONDS` setting
2. [backend/services/gemini.py](../backend/services/gemini.py) - Core caching logic
3. [backend/routers/diagnose.py](../backend/routers/diagnose.py) - Passes caching params
4. [backend/routers/admin.py](../backend/routers/admin.py) - Cache monitoring endpoints

## Complete Documentation

- **[CACHING_IMPLEMENTATION.md](../CACHING_IMPLEMENTATION.md)** - Complete overview
- **[CONTEXT_CACHING.md](CONTEXT_CACHING.md)** - Technical deep dive
- **[CACHING_EXAMPLE.md](CACHING_EXAMPLE.md)** - Testing guide

## Cost Savings Example

**100 requests to the same expert:**

| Without Caching | With Caching | Savings |
|----------------|--------------|---------|
| $0.02025 | $0.00626 | **69%** |

*Based on 2500 token system prompt + 200 token user prompts*

## Next Steps

1. **Deploy** - No changes needed, caching is automatic
2. **Monitor** - Use admin endpoints to verify caching is working
3. **Optimize** - Adjust TTL based on your prompt update frequency
4. **Scale** - Enjoy cost savings as request volume increases

## Need Help?

- **Troubleshooting**: See [CACHING_EXAMPLE.md](CACHING_EXAMPLE.md)
- **Technical details**: See [CONTEXT_CACHING.md](CONTEXT_CACHING.md)
- **API Reference**: See [API_INGESTION.md](API_INGESTION.md)
