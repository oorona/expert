# Grounded Search Citations Fix

## Problem

Web grounding (Google Search) citations were not showing detailed citation information like file search does. The sources were only displaying as simple links without showing:
- Which parts of the response cited each source
- Confidence scores for citations
- Text segments that reference each source

## Solution

Enhanced the grounding metadata extraction to include detailed citation information from `grounding_supports`, similar to what was already implemented for file search results.

## Changes Made

### 1. Backend: Enhanced Source Extraction ([backend/services/gemini.py](../backend/services/gemini.py))

**Before** - Only extracted basic URI and title:
```python
def _extract_sources(self, response) -> list[dict]:
    for chunk in chunks:
        web = getattr(chunk, "web", None)
        if web:
            sources.append({"uri": web.uri, "title": getattr(web, "title", "Source")})
```

**After** - Extracts detailed citation information:
```python
def _extract_sources(self, response) -> list[dict]:
    # Build chunk list with web source data
    chunk_data = [{"uri": ..., "title": ...}]

    # Extract grounding_supports for detailed citations
    supports = getattr(meta, "grounding_supports", None) or []
    chunk_citations: dict[int, list[dict]] = {}

    for support in supports:
        # Extract cited text segments and confidence scores
        segment_text = getattr(segment, "text", "")
        confidence = scores[i] if i < len(scores) else 0.0
        chunk_citations[idx].append({
            "cited_text": segment_text,
            "confidence": round(confidence, 3),
        })

    # Return sources with citation details
    sources.append({
        "uri": cd["uri"],
        "title": cd["title"],
        "citations": chunk_citations.get(idx, []),
    })
```

### 2. Frontend: Updated Type Definition ([frontend/types/index.ts](../frontend/types/index.ts))

Added `citations` field to the `Source` interface:

```typescript
export interface Citation {
  cited_text: string;
  confidence: number;
}

export interface Source {
  uri: string;
  title: string;
  citations: Citation[];  // ← Added
}
```

### 3. Frontend: Enhanced SourcesList Component ([frontend/components/diagnosis/SourcesList.tsx](../frontend/components/diagnosis/SourcesList.tsx))

**Before** - Simple list of links:
```tsx
<ul>
  <li><a href={s.uri}>{s.title}</a></li>
</ul>
```

**After** - Detailed display with citations (similar to file search):
```tsx
<div className="space-y-3">
  <h3>🌐 Web Sources ({sources.length})</h3>
  {sources.map((source) => (
    <div className="border rounded-lg">
      {/* Source header */}
      <div className="bg-gray-50">
        <a href={source.uri}>{source.title}</a>
      </div>

      {/* Citation details */}
      {source.citations.map((citation) => (
        <div className="pl-3 border-l-2">
          <p>"{citation.cited_text}"</p>
          <p>Confidence: {(citation.confidence * 100).toFixed(0)}%</p>
        </div>
      ))}
    </div>
  ))}
</div>
```

## How It Works

### Backend Flow

1. **Gemini API Response** includes `grounding_metadata` with:
   - `grounding_chunks`: Web sources (URI, title)
   - `grounding_supports`: Citation mappings (text segments → source indices)

2. **Extract Web Sources**: Build list of web sources from chunks

3. **Extract Citations**: Process `grounding_supports` to map:
   - Which text segments in the response cite which sources
   - Confidence scores for each citation

4. **Return Enhanced Sources**: Each source includes:
   ```json
   {
     "uri": "https://example.com/article",
     "title": "Example Article",
     "citations": [
       {
         "cited_text": "Spain won Euro 2024, defeating England 2-1",
         "confidence": 0.95
       }
     ]
   }
   ```

### Frontend Display

The SourcesList component now:
1. Checks if sources have citation details
2. If yes: Shows detailed display with expandable citations
3. If no: Falls back to simple link list (backward compatible)

## Example Output

### Before
```
Sources:
• Example Article
```

### After
```
🌐 Web Sources (3)

┌─────────────────────────────────────────┐
│ 🔗 Example Article                       │
├─────────────────────────────────────────┤
│ Citations (2)                            │
│   │ "Spain won Euro 2024, defeating     │
│   │  England 2-1"                       │
│   └─ Confidence: 95%                    │
│                                          │
│   │ "The final was held at the          │
│   │  Olympic Stadium in Berlin"         │
│   └─ Confidence: 92%                    │
└─────────────────────────────────────────┘
```

## Streaming Compatibility

The fix works with streaming responses because:

1. The streaming loop tracks `grounding_response` (the chunk with grounding_metadata)
2. After streaming completes, it extracts sources from this tracked response
3. All citation information is available in the final chunk with `grounding_metadata`

```python
# In diagnose_error_stream
grounding_response = None
for chunk in stream:
    if chunk.candidates and getattr(chunk.candidates[0], "grounding_metadata", None):
        grounding_response = chunk  # ← Captures grounding metadata

# After streaming
sources = self._extract_sources(grounding_response)  # ← Has all citation info
```

## Testing

### Verify Citations Are Showing

1. **Run a diagnosis with grounding enabled**:
   ```bash
   curl -X POST http://localhost:3000/api/diagnose \
     -F "error_text=Your error" \
     -F "expert_id=1" \
     -F "use_grounding=true"
   ```

2. **Check the response** for citation details:
   ```json
   {
     "sources": [
       {
         "uri": "https://example.com",
         "title": "Example",
         "citations": [
           {
             "cited_text": "Some text from the response",
             "confidence": 0.95
           }
         ]
       }
     ]
   }
   ```

3. **View in UI**: The "General / Grounded" tab should show:
   - Section header: "🌐 Web Sources (N)"
   - Each source as an expandable card
   - Citation snippets with confidence scores

### Compare with File Search

Both grounded search and file search now show similar citation formats:

| Feature | Grounded Search | File Search |
|---------|----------------|-------------|
| Source title | ✅ | ✅ |
| Source link | ✅ | ✅ |
| Cited text snippets | ✅ | ✅ |
| Confidence scores | ✅ | ✅ |
| Document-specific | Text from response | Text from document |
| Icon | 🔗 | 📎 |

## Notes

- **Backward compatible**: Sources without citations still display as simple links
- **No breaking changes**: Existing code continues to work
- **Streaming safe**: Works correctly with streaming thought responses
- **Consistent UX**: Grounded and file search citations now have similar visual styles

## References

- [Gemini API Google Search Documentation](https://ai.google.dev/gemini-api/docs/google-search)
- [Gemini API Grounding Metadata](https://ai.google.dev/gemini-api/docs/grounding)
