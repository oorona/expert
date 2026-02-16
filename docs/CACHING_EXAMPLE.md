# Context Caching Example & Testing

## Quick Test

Here's how to verify that context caching is working:

### 1. Check Initial State

```bash
# Check if any caches exist
curl -H "X-Client-Key: YOUR_API_KEY" \
  http://localhost:8000/api/admin/cache/status
```

Expected response (no caches yet):
```json
{
  "active_caches": [],
  "total_count": 0
}
```

### 2. Run First Diagnosis

```bash
# Submit an error for diagnosis (creates cache on first request)
curl -X POST http://localhost:3000/api/diagnose \
  -H "X-Client-Key: YOUR_API_KEY" \
  -F "error_text=Error: Connection timeout after 30s" \
  -F "expert_id=1" \
  -F "model=gemini-2.5-flash" \
  -F "thinking_level=medium" \
  -F "use_grounding=true"
```

**Check backend logs** - you should see:
```
INFO: Creating new cache for expert_1_grounded_gemini-2.5-flash
INFO: Created cache cachedContents/abc123, expires at 2026-02-14 15:30:00
```

### 3. Check Cache Was Created

```bash
curl -H "X-Client-Key: YOUR_API_KEY" \
  http://localhost:8000/api/admin/cache/status
```

Expected response:
```json
{
  "active_caches": [
    {
      "cache_key": "expert_1_grounded_gemini-2.5-flash",
      "cache_name": "cachedContents/abc123xyz",
      "expires_at": "2026-02-14T15:30:00",
      "is_expired": false,
      "prompt_hash": "a1b2c3d4e5f6g7h8..."
    }
  ],
  "total_count": 1
}
```

### 4. Run Second Diagnosis (Uses Cache)

```bash
# Submit another error with same expert/model (should use cached prompt)
curl -X POST http://localhost:3000/api/diagnose \
  -H "X-Client-Key: YOUR_API_KEY" \
  -F "error_text=Error: Database connection refused" \
  -F "expert_id=1" \
  -F "model=gemini-2.5-flash" \
  -F "thinking_level=medium" \
  -F "use_grounding=true"
```

**Check backend logs** - you should see:
```
INFO: Using existing cache for expert_1_grounded_gemini-2.5-flash
INFO: Using cached system prompt for expert 1
```

### 5. Verify Token Usage

In the response from step 4, check the `usage` field:

```json
{
  "usage": {
    "prompt_token_count": 150,
    "cached_content_token_count": 2000,  ← This should be > 0!
    "candidates_token_count": 500,
    "total_token_count": 2650
  }
}
```

**If `cached_content_token_count` > 0**, caching is working! ✅

## Testing Different Scenarios

### Test 1: Different Experts (Creates Separate Caches)

```bash
# Expert 1
curl -X POST http://localhost:3000/api/diagnose \
  -F "error_text=Error A" -F "expert_id=1" -F "model=gemini-2.5-flash" ...

# Expert 2 (creates new cache)
curl -X POST http://localhost:3000/api/diagnose \
  -F "error_text=Error B" -F "expert_id=2" -F "model=gemini-2.5-flash" ...
```

Should create 2 separate caches:
- `expert_1_grounded_gemini-2.5-flash`
- `expert_2_grounded_gemini-2.5-flash`

### Test 2: Different Categories (Creates Separate Caches)

```bash
# Grounded mode
curl -X POST http://localhost:3000/api/diagnose \
  -F "expert_id=1" -F "use_grounding=true" -F "use_file_search=false" ...

# File search mode (creates new cache)
curl -X POST http://localhost:3000/api/diagnose \
  -F "expert_id=1" -F "use_grounding=false" -F "use_file_search=true" ...
```

Should create 2 separate caches:
- `expert_1_grounded_gemini-2.5-flash`
- `expert_1_file_search_gemini-2.5-flash`

### Test 3: Different Models (Creates Separate Caches)

```bash
# Flash model
curl -X POST http://localhost:3000/api/diagnose \
  -F "expert_id=1" -F "model=gemini-2.5-flash" ...

# Pro model (creates new cache)
curl -X POST http://localhost:3000/api/diagnose \
  -F "expert_id=1" -F "model=gemini-2.5-pro" ...
```

Should create 2 separate caches:
- `expert_1_grounded_gemini-2.5-flash`
- `expert_1_grounded_gemini-2.5-pro`

### Test 4: Cache Expiration

```bash
# Set short TTL for testing (5 minutes)
export CACHE_TTL_SECONDS=300

# Make diagnosis request
curl -X POST http://localhost:3000/api/diagnose -F "expert_id=1" ...

# Wait 6 minutes...
sleep 360

# Check cache status
curl -H "X-Client-Key: YOUR_API_KEY" \
  http://localhost:8000/api/admin/cache/status

# Cache should show is_expired: true
```

Next request will automatically recreate the cache.

### Test 5: Manual Cache Cleanup

```bash
# Clear all expired caches manually
curl -X POST -H "X-Client-Key: YOUR_API_KEY" \
  http://localhost:8000/api/admin/cache/clear-expired
```

Response:
```json
{
  "status": "success",
  "cleared_count": 2
}
```

## Expected Log Output

### First Request (Cache Creation)

```
INFO: Checking for similar incidents…
INFO: Loading prompts & schema…
INFO: Analyzing with Gemini…
INFO: Creating new cache for expert_1_grounded_gemini-2.5-flash
INFO: Created cache cachedContents/abc123, expires at 2026-02-14 15:30:00
INFO: Generating report…
INFO: Saving results…
```

### Second Request (Cache Hit)

```
INFO: Checking for similar incidents…
INFO: Loading prompts & schema…
INFO: Analyzing with Gemini…
INFO: Using existing cache for expert_1_grounded_gemini-2.5-flash
INFO: Using cached system prompt for expert 1
INFO: Generating report…
INFO: Saving results…
```

### Cache Invalidation (Prompt Changed)

```
INFO: Analyzing with Gemini…
INFO: Cache expert_1_grounded_gemini-2.5-flash expired or prompt changed, recreating
INFO: Creating new cache for expert_1_grounded_gemini-2.5-flash
INFO: Created cache cachedContents/xyz789, expires at 2026-02-14 16:45:00
```

## Performance Comparison

### Without Caching

```
Request 1:
- Prompt tokens: 2500 (system) + 200 (user) = 2700
- Cost: $0.0002025

Request 2:
- Prompt tokens: 2500 (system) + 200 (user) = 2700
- Cost: $0.0002025

Total: $0.000405 for 2 requests
```

### With Caching

```
Request 1 (creates cache):
- Prompt tokens: 2500 (system) + 200 (user) = 2700
- Cost: $0.0002025

Request 2 (uses cache):
- Cached tokens: 2500 (at 75% discount)
- Regular tokens: 200 (user)
- Cost: $0.000046875 + $0.000015 = $0.000061875

Total: $0.000264375 for 2 requests
Savings: 34.7%
```

**More requests = more savings!** With 100 requests, savings approach 75%.

## Monitoring in Production

### Check Cache Hit Rate

```bash
# Get cache status periodically
while true; do
  curl -s -H "X-Client-Key: $API_KEY" \
    http://localhost:8000/api/admin/cache/status | jq
  sleep 60
done
```

### Monitor Token Usage

Extract `cached_content_token_count` from diagnosis responses:

```bash
# Run diagnosis and check usage
curl -X POST http://localhost:3000/api/diagnose ... | \
  jq '.usage.cached_content_token_count'
```

If this value is:
- **> 0**: Cache is working ✅
- **0**: Cache miss or not created ⚠️

### Watch Logs

```bash
# Follow backend logs
docker logs -f expert-backend | grep -i cache
```

Look for:
- `Creating new cache` - New cache created
- `Using existing cache` - Cache hit
- `expired or prompt changed` - Cache invalidated

## Troubleshooting

### Problem: cached_content_token_count is always 0

**Diagnosis**:
```bash
# Check if expert_id is being passed
# Check logs for cache creation errors
docker logs expert-backend | grep -i cache

# Verify cache status
curl -H "X-Client-Key: $API_KEY" \
  http://localhost:8000/api/admin/cache/status
```

**Common causes**:
1. System prompt < 1024 tokens (below minimum for caching)
2. Model doesn't support caching
3. Cache creation failed (API error)

### Problem: Cache not persisting across requests

**Diagnosis**:
```bash
# Check cache status between requests
curl -H "X-Client-Key: $API_KEY" \
  http://localhost:8000/api/admin/cache/status
```

**Common causes**:
1. Multiple backend instances (caches stored in memory, not shared)
2. Backend restarting between requests
3. TTL too short

**Solution**: Check that only one backend instance is running:
```bash
docker ps | grep expert-backend
```

### Problem: Prompt changes not taking effect

**Diagnosis**:
```bash
# Check cache metadata
curl -H "X-Client-Key: $API_KEY" \
  http://localhost:8000/api/admin/cache/status | jq '.active_caches[0]'
```

**Common causes**:
1. Cache still valid and using old prompt
2. Need to wait for TTL expiration

**Solution**:
```bash
# Restart backend to clear in-memory caches
docker restart expert-backend

# Or manually clear expired caches
curl -X POST -H "X-Client-Key: $API_KEY" \
  http://localhost:8000/api/admin/cache/clear-expired
```
