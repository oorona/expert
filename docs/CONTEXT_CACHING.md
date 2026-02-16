# Context Caching for System Prompts

## Overview

The Expert Diagnostic Engine implements **explicit context caching** using the Gemini API's caching feature to optimize performance and reduce costs. System prompts for each expert are cached and reused across multiple diagnosis requests, significantly reducing the number of tokens that need to be processed.

## How It Works

### Cache Creation

When a new analysis request is made, the system:

1. **Generates a cache key** based on:
   - `expert_id` - The specific expert being used
   - `prompt_category` - Either "grounded" (web search) or "file_search" (RAG)
   - `model` - The Gemini model being used (e.g., "gemini-2.5-flash")

2. **Checks for existing cache**:
   - If a valid cache exists for this combination → reuses it
   - If cache expired or prompt changed → deletes old cache and creates new one
   - If no cache exists → creates new cache

3. **Creates cache** with:
   - System instruction (the expert's system prompt)
   - Configurable TTL (Time To Live)
   - Empty contents array (only system instruction is cached)

### Cache Usage

When making a diagnosis request:

```python
# Cache hit: uses cached system prompt
config = types.GenerateContentConfig(
    cached_content="cached_content_name_here",
    # system_instruction is NOT sent again
    temperature=1.0,
    ...
)
```

Instead of sending the full system prompt (which can be 2000+ tokens) with every request, the API only needs to reference the cached content.

## Benefits

### Cost Savings

Gemini API pricing for cached tokens is **75% cheaper** than regular input tokens:
- Regular input: $0.075 per 1M tokens (gemini-2.5-flash)
- Cached input: $0.01875 per 1M tokens
- Output tokens: $0.30 per 1M tokens

For a typical system prompt of 2000 tokens processed 100 times:
- **Without caching**: 200,000 input tokens = $0.015
- **With caching**: 2000 + (99 × cached) = $0.0018
- **Savings**: ~88% reduction in input token costs

### Performance Improvements

- Faster response times (less data to process)
- Reduced latency for first token
- Better throughput for concurrent requests

## Configuration

### Environment Variables

Set the cache TTL in your environment:

```bash
# Cache TTL in seconds (default: 3600 = 1 hour)
CACHE_TTL_SECONDS=3600
```

### Recommended TTL Values

| Use Case | TTL | Reasoning |
|----------|-----|-----------|
| Development | 300s (5 min) | Prompts change frequently |
| Staging | 1800s (30 min) | Moderate stability |
| Production | 3600s (1 hour) | Stable prompts, max cache benefit |
| High-volume | 7200s (2 hours) | Maximize cost savings |

### Maximum TTL

Gemini API enforces maximum TTL limits (typically 24 hours). Check the latest API documentation for current limits.

## Cache Invalidation

Caches are automatically invalidated when:

1. **TTL expires**: Cache is deleted and recreated on next request
2. **System prompt changes**: Hash comparison detects changes, triggers recreation
3. **Expert configuration changes**: Different expert_id = different cache

### Manual Cache Management

The system stores cache metadata in memory:

```python
class CacheMetadata:
    cache_name: str       # Resource name in Gemini API
    expires_at: datetime  # When cache expires
    prompt_hash: str      # SHA-256 hash of system prompt
```

## Implementation Details

### Cache Key Format

```
expert_{expert_id}_{prompt_category}_{model}
```

Examples:
- `expert_1_grounded_gemini-2.5-flash`
- `expert_2_file_search_gemini-2.5-flash`

### Cache Lifecycle

```
Request → Check cache key → Valid cache exists?
                               ↓ Yes        ↓ No
                           Use cache    Create new cache
                               ↓              ↓
                           Make API call ←────┘
                               ↓
                           Return result
```

## Monitoring Cache Usage

### Usage Metadata

Every API response includes token usage information:

```json
{
  "usage": {
    "prompt_token_count": 150,
    "cached_content_token_count": 2000,
    "candidates_token_count": 500,
    "total_token_count": 2650
  }
}
```

- `cached_content_token_count` > 0 means cache was used successfully
- Monitor this field to verify caching is working

### Logs

The system logs cache operations:

```
INFO: Creating new cache for expert_1_grounded_gemini-2.5-flash
INFO: Created cache cachedContents/abc123, expires at 2026-02-14 15:30:00
INFO: Using existing cache for expert_1_grounded_gemini-2.5-flash
INFO: Using cached system prompt for expert 1
```

## Troubleshooting

### Cache Not Being Used

**Symptom**: `cached_content_token_count` is always 0

**Possible causes**:
1. **System prompt is too short** - Minimum requirements:
   - Flash models (gemini-2.5-flash, gemini-3-flash): **1024 tokens**
   - Pro models (gemini-2.5-pro, gemini-3-pro): **4096 tokens**
   - Check logs for: `Skipping cache for ...: prompt too small`
2. Cache creation failed (check logs)
3. expert_id or prompt_category not being passed to the service
4. Model doesn't support caching

**Solution**:
- Check logs for cache creation messages
- Ensure system prompts are detailed enough (> 1024 tokens for flash, > 4096 for pro)
- Verify parameters are being passed correctly

### Stale Prompt Content

**Symptom**: Changes to system prompts not taking effect

**Possible causes**:
1. Cache TTL is very long
2. Prompt hash not detecting changes

**Solution**:
- Restart the backend service to clear in-memory cache metadata
- Reduce TTL for development environments

### High Cache Miss Rate

**Symptom**: Many cache creations in logs

**Possible causes**:
1. Different models being used for each request
2. TTL too short
3. Multiple backend instances with independent cache storage

**Solution**:
- Use consistent model selection
- Increase TTL
- Consider shared cache state (Redis) for multi-instance deployments

## Best Practices

1. **Use consistent models**: Don't switch models frequently for the same expert
2. **Set appropriate TTL**: Balance cost savings vs. prompt update frequency
3. **Monitor usage metadata**: Verify `cached_content_token_count` in responses
4. **Stable system prompts**: Cache works best with infrequently-changing prompts
5. **Single backend instance**: Current implementation stores cache metadata in memory

## Future Enhancements

Potential improvements to the caching system:

- [ ] Shared cache metadata storage (Redis) for multi-instance deployments
- [ ] Cache warming on startup for frequently-used experts
- [ ] Analytics dashboard for cache hit rates
- [ ] Automatic TTL optimization based on prompt update frequency
- [ ] Cache preloading for all active experts

## References

- [Gemini API Caching Documentation](https://ai.google.dev/gemini-api/docs/caching)
- [Gemini API Pricing](https://ai.google.dev/pricing)
