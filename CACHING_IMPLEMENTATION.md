# Context Caching Implementation Summary

## Overview

Implemented explicit context caching for system prompts using the Gemini API's caching feature. This optimization significantly reduces token costs and improves response times by caching the system instruction that remains constant across multiple diagnosis requests for the same expert.

## Changes Made

### 1. Configuration ([backend/config.py](backend/config.py))

Added configurable cache TTL setting:

```python
CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "3600"))  # 1 hour default
```

### 2. GeminiService Updates ([backend/services/gemini.py](backend/services/gemini.py))

#### New Cache Management Classes

- **`CacheMetadata`**: Tracks cache name, expiration time, and prompt hash
  - Validates cache freshness
  - Detects when system prompt changes

#### New Methods

- **`get_or_create_cache()`**: Main caching logic
  - Checks for existing valid cache
  - Creates new cache if needed
  - Handles cache expiration and invalidation
  - Returns cache name for API calls

- **`list_active_caches()`**: Returns all active caches with metadata
  - For monitoring and debugging
  - Shows expiration status and prompt hash

- **`clear_expired_caches()`**: Manual cleanup of expired caches
  - Removes from memory and Gemini API
  - Returns count of cleared caches

#### Updated Methods

- **`diagnose_error_stream()`** and **`diagnose_error()`**:
  - Added `expert_id` and `prompt_category` parameters
  - Automatic cache lookup before API calls
  - Uses `cached_content` when available
  - Logs cache hits for monitoring

### 3. Diagnose Router Updates ([backend/routers/diagnose.py](backend/routers/diagnose.py))

Updated the diagnose endpoint to pass caching parameters:

```python
async for item in gemini_service.diagnose_error_stream(
    # ... other params ...
    expert_id=expert_id,
    prompt_category=prompt_category,
):
```

### 4. Admin API Endpoints ([backend/routers/admin.py](backend/routers/admin.py))

Added two new admin endpoints:

- **`GET /api/admin/cache/status`**: View all active caches
  ```json
  {
    "active_caches": [
      {
        "cache_key": "expert_1_grounded_gemini-2.5-flash",
        "cache_name": "cachedContents/abc123",
        "expires_at": "2026-02-14T15:30:00",
        "is_expired": false,
        "prompt_hash": "a1b2c3d4..."
      }
    ],
    "total_count": 1
  }
  ```

- **`POST /api/admin/cache/clear-expired`**: Manually clean up expired caches
  ```json
  {
    "status": "success",
    "cleared_count": 2
  }
  ```

## How It Works

### Cache Key Structure

Each cache is uniquely identified by:
```
expert_{expert_id}_{prompt_category}_{model}
```

Examples:
- `expert_1_grounded_gemini-2.5-flash`
- `expert_2_file_search_gemini-2.5-pro`

### Cache Lifecycle

1. **First Request** (Cache Miss):
   ```
   Request → No cache exists → Create new cache → API call with cached_content → Store metadata
   ```

2. **Subsequent Requests** (Cache Hit):
   ```
   Request → Cache exists & valid → API call with cached_content → Faster response
   ```

3. **Cache Invalidation**:
   ```
   Cache expired OR prompt changed → Delete old cache → Create new cache
   ```

### Token Cost Savings

| Scenario | Input Tokens | Cached Tokens | Cost (per request) | Savings |
|----------|--------------|---------------|-------------------|---------|
| No cache | 2700 | 0 | $0.0002025 | - |
| First request | 2700 | 0 | $0.0002025 | 0% |
| Cached request | 200 | 2500 | $0.000062 | 69% |

**Over 100 requests**: ~67% cost reduction on input tokens

## Environment Variables

```bash
# Optional: Set custom cache TTL (default: 3600 seconds = 1 hour)
CACHE_TTL_SECONDS=3600
```

## Verification

### Check Logs

Cache hits and creations are logged:

```
INFO: Creating new cache for expert_1_grounded_gemini-2.5-flash
INFO: Created cache cachedContents/abc123, expires at 2026-02-14 15:30:00
INFO: Using existing cache for expert_1_grounded_gemini-2.5-flash
INFO: Using cached system prompt for expert 1
```

### Monitor API Responses

Check the `usage` field in diagnosis responses:

```json
{
  "usage": {
    "cached_content_token_count": 2000  ← Should be > 0 when cache is used
  }
}
```

### Use Admin Endpoints

```bash
# Check cache status
curl -H "X-Client-Key: YOUR_KEY" http://localhost:8000/api/admin/cache/status

# Clear expired caches
curl -X POST -H "X-Client-Key: YOUR_KEY" \
  http://localhost:8000/api/admin/cache/clear-expired
```

## Documentation

Created three documentation files:

1. **[CONTEXT_CACHING.md](docs/CONTEXT_CACHING.md)**: Complete technical documentation
   - How caching works
   - Configuration options
   - Cost savings analysis
   - Monitoring and troubleshooting

2. **[CACHING_EXAMPLE.md](docs/CACHING_EXAMPLE.md)**: Testing guide
   - Step-by-step verification
   - Different scenarios
   - Expected log output
   - Performance comparisons

3. **[API_INGESTION.md](docs/API_INGESTION.md)**: Existing API documentation (unchanged)

## Benefits

### 1. Cost Reduction
- 75% discount on cached tokens vs regular input tokens
- Typical savings: 60-70% on input token costs over time
- Greater savings with higher request volume

### 2. Performance
- Faster response times (less data to process)
- Reduced latency for first token
- Better throughput for concurrent requests

### 3. Scalability
- Automatic cache management
- Handles cache expiration transparently
- Detects and handles prompt changes

## Limitations & Future Improvements

### Current Limitations

1. **Single Instance Only**: Cache metadata stored in memory
   - Multi-instance deployments won't share caches
   - Each instance maintains separate cache state

2. **Manual Cleanup**: Expired caches cleaned on-demand
   - Need to call `clear_expired_caches()` manually
   - Or restart backend to clear all

### Potential Enhancements

- [ ] Redis-backed cache metadata for multi-instance deployments
- [ ] Background task for automatic expired cache cleanup
- [ ] Cache pre-warming on startup for active experts
- [ ] Analytics dashboard for cache hit rates
- [ ] Automatic TTL optimization based on usage patterns
- [ ] Cache statistics (hit rate, average age, etc.)

## Testing Checklist

- [x] Cache created on first diagnosis request
- [x] Cache reused on subsequent requests with same expert/category/model
- [x] Separate caches for different experts
- [x] Separate caches for different categories (grounded vs file_search)
- [x] Separate caches for different models
- [x] Cache invalidation when prompt changes
- [x] Cache expiration after TTL
- [x] Admin endpoints for monitoring
- [x] Token usage metadata includes cached_content_token_count
- [x] Logs show cache operations

## References

- [Gemini API Context Caching Documentation](https://ai.google.dev/gemini-api/docs/caching)
- [Gemini API Pricing](https://ai.google.dev/pricing)
