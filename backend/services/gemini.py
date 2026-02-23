import asyncio
import hashlib
import json
import logging
import os
import tempfile
import time as time_module
from datetime import datetime, timedelta
from google import genai
from google.genai import types

from config import settings

logger = logging.getLogger(__name__)


class CacheMetadata:
    """Metadata for a cached system prompt."""
    def __init__(self, cache_name: str, expires_at: datetime, prompt_hash: str):
        self.cache_name = cache_name
        self.expires_at = expires_at
        self.prompt_hash = prompt_hash

    def is_expired(self) -> bool:
        return datetime.now() >= self.expires_at

    def is_valid_for_prompt(self, prompt: str) -> bool:
        """Check if this cache is still valid for the given prompt."""
        return self.prompt_hash == self._hash_prompt(prompt) and not self.is_expired()

    @staticmethod
    def _hash_prompt(prompt: str) -> str:
        return hashlib.sha256(prompt.encode()).hexdigest()


class GeminiService:
    def __init__(self):
        self.client = None
        # Cache storage: key -> CacheMetadata
        self.active_caches: dict[str, CacheMetadata] = {}

    async def initialize(self):
        if settings.GEMINI_API_KEY:
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
            logger.info("Gemini client initialized")
        else:
            logger.warning("No Gemini API key found, LLM features disabled")

    def _make_cache_key(self, expert_id: int, prompt_category: str, model: str) -> str:
        """Generate a unique cache key for an expert's system prompt.

        Cache contains ONLY system_instruction. Tools, thinking, schema are passed separately.
        """
        return f"expert_{expert_id}_{prompt_category}_{model}"

    async def get_or_create_cache(
        self,
        cache_key: str,
        model: str,
        system_prompt: str,
        tools: list | None = None,
        ttl_seconds: int | None = None,
    ) -> str | None:
        """Get existing cache or create a new one for the system prompt.

        Returns the cache name to use in API calls, or None if caching should be skipped.
        Skips caching if the prompt is too small (< 1024 tokens minimum).
        """
        if ttl_seconds is None:
            ttl_seconds = settings.CACHE_TTL_SECONDS

        # Rough token count estimation (4 chars ≈ 1 token)
        estimated_tokens = len(system_prompt) // 4
        min_tokens = 1024  # Minimum for flash models

        # Skip caching if prompt is too small
        if estimated_tokens < min_tokens:
            logger.info(
                f"Skipping cache for {cache_key}: prompt too small "
                f"(~{estimated_tokens} tokens, minimum {min_tokens})"
            )
            return None

        # Check if we have a valid cached entry
        if cache_key in self.active_caches:
            cache_meta = self.active_caches[cache_key]
            if cache_meta.is_valid_for_prompt(system_prompt):
                logger.info(f"Using existing cache for {cache_key}")
                return cache_meta.cache_name
            else:
                # Cache expired or prompt changed, delete it
                logger.info(f"Cache {cache_key} expired or prompt changed, recreating")
                try:
                    await self._delete_cache(cache_meta.cache_name)
                except Exception as e:
                    logger.warning(f"Failed to delete expired cache {cache_meta.cache_name}: {e}")
                del self.active_caches[cache_key]

        # Create new cache
        try:
            logger.info(f"Creating new cache for {cache_key} (~{estimated_tokens} tokens)")
            loop = asyncio.get_event_loop()

            # Some models require at least one content item, so provide a minimal placeholder
            placeholder_content = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text="placeholder")]
                )
            ]

            # Build cache config with ONLY system_instruction
            # Tools, thinking, schema are NOT cached - they're passed separately each time
            cache_config_kwargs = {
                "system_instruction": system_prompt,
                "contents": placeholder_content,
                "ttl": f"{ttl_seconds}s",
            }

            cache = await loop.run_in_executor(
                None,
                lambda: self.client.caches.create(
                    model=f"models/{model}",
                    config=types.CreateCachedContentConfig(**cache_config_kwargs),
                ),
            )
            cache_name = cache.name
            expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
            prompt_hash = CacheMetadata._hash_prompt(system_prompt)

            self.active_caches[cache_key] = CacheMetadata(cache_name, expires_at, prompt_hash)
            logger.info(f"Created cache {cache_name} for {cache_key}, expires at {expires_at}")
            return cache_name

        except Exception as e:
            logger.warning(f"Failed to create cache for {cache_key}: {e}")
            # Continue without caching
            return None

    async def _delete_cache(self, cache_name: str):
        """Delete a cache by name."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.client.caches.delete(name=cache_name),
        )

    async def list_active_caches(self) -> list[dict]:
        """List all active caches with their metadata.

        Returns a list of cache info dictionaries for debugging/monitoring.
        """
        result = []
        for cache_key, metadata in self.active_caches.items():
            result.append({
                "cache_key": cache_key,
                "cache_name": metadata.cache_name,
                "expires_at": metadata.expires_at.isoformat(),
                "is_expired": metadata.is_expired(),
                "prompt_hash": metadata.prompt_hash[:16] + "...",  # First 16 chars
            })
        return result

    async def clear_expired_caches(self):
        """Remove expired caches from memory and Gemini API.

        Should be called periodically to clean up stale caches.
        """
        expired_keys = []
        for cache_key, metadata in self.active_caches.items():
            if metadata.is_expired():
                expired_keys.append((cache_key, metadata.cache_name))

        for cache_key, cache_name in expired_keys:
            logger.info(f"Clearing expired cache: {cache_key}")
            try:
                await self._delete_cache(cache_name)
            except Exception as e:
                logger.warning(f"Failed to delete expired cache {cache_name}: {e}")
            del self.active_caches[cache_key]

        return len(expired_keys)

    async def diagnose_error(
        self,
        error_text: str,
        image_bytes: bytes | None,
        image_mime: str | None,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict | None,
        model: str = "gemini-2.5-flash",
        temperature: float = 1.0,
        thinking_level: str = "medium",
        use_grounding: bool = True,
        use_file_search: bool = False,
        file_search_store_names: list[str] | None = None,
        expert_id: int | None = None,
        prompt_category: str | None = None,
    ) -> dict:
        """Main diagnostic call (non-streaming). Returns structured result."""
        result = None
        async for item in self.diagnose_error_stream(
            error_text=error_text,
            image_bytes=image_bytes,
            image_mime=image_mime,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_schema=output_schema,
            model=model,
            temperature=temperature,
            thinking_level=thinking_level,
            use_grounding=use_grounding,
            use_file_search=use_file_search,
            file_search_store_names=file_search_store_names,
            expert_id=expert_id,
            prompt_category=prompt_category,
        ):
            if item["type"] == "result":
                result = item["data"]
        return result or {"raw_json": {}, "sources": [], "file_search_results": [], "usage": {}}

    async def diagnose_error_stream(
        self,
        error_text: str,
        image_bytes: bytes | None,
        image_mime: str | None,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict | None,
        model: str = "gemini-2.5-flash",
        temperature: float = 1.0,
        thinking_level: str = "medium",
        use_grounding: bool = True,
        use_file_search: bool = False,
        file_search_store_names: list[str] | None = None,
        expert_id: int | None = None,
        prompt_category: str | None = None,
    ):
        """Streaming diagnostic call. Async generator that yields:
        - {"type": "thought", "text": "..."} for thought summary chunks
        - {"type": "result", "data": {...}} for the final parsed result
        """
        parts = []
        if image_bytes and image_mime:
            parts.append(types.Part.from_bytes(data=image_bytes, mime_type=image_mime))
        parts.append(types.Part.from_text(text=user_prompt))

        tools = []
        # File search and grounding are mutually exclusive per Gemini API
        if use_file_search and file_search_store_names:
            tools.append(
                types.Tool(
                    file_search=types.FileSearch(
                        file_search_store_names=file_search_store_names
                    )
                )
            )
        elif use_grounding:
            tools.append(types.Tool(google_search=types.GoogleSearch()))

        config_kwargs: dict = {
            "system_instruction": system_prompt,
            "temperature": temperature,
        }

        if output_schema:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_json_schema"] = output_schema

        if tools:
            config_kwargs["tools"] = tools

        include_thoughts = False
        if thinking_level and thinking_level != "off":
            thinking_config = self._get_thinking_config(model, thinking_level)
            if thinking_config:
                config_kwargs["thinking_config"] = thinking_config
                include_thoughts = True

        # TODO: Context caching disabled for now
        # Can't use cached_content with tools in the request (API returns 400 INVALID_ARGUMENT)
        # Would need to put tools in cache, but our tools vary per request (grounding on/off)
        cache_name = None
        # if expert_id is not None and prompt_category is not None:
        #     cache_key = self._make_cache_key(expert_id, prompt_category, model)
        #     cache_name = await self.get_or_create_cache(...)
        #     if cache_name:
        #         config_kwargs["cached_content"] = cache_name

        config = types.GenerateContentConfig(**config_kwargs)

        # Debug logging to see actual config
        logger.error(f"DEBUG: API Config - use_grounding={use_grounding}, use_file_search={use_file_search}")
        logger.error(f"DEBUG: Config has tools: {'tools' in config_kwargs}")
        logger.error(f"DEBUG: Config has thinking: {'thinking_config' in config_kwargs}")
        logger.error(f"DEBUG: Config has schema: {'response_json_schema' in config_kwargs}")
        logger.error(f"DEBUG: Config has cache: {'cached_content' in config_kwargs}")
        if 'tools' in config_kwargs:
            # Show tool details, not just class name
            tool_details = []
            for t in config_kwargs['tools']:
                if hasattr(t, 'google_search') and t.google_search is not None:
                    tool_details.append('google_search')
                elif hasattr(t, 'file_search') and t.file_search is not None:
                    tool_details.append('file_search')
                else:
                    tool_details.append(f'unknown_{type(t).__name__}')
            logger.error(f"DEBUG: Tools configured: {tool_details}")

        # Use streaming to capture thought summaries in real time
        answer_text = ""
        last_response = None
        usage_response = None  # Track the chunk with usage_metadata
        grounding_response = None  # Track the chunk with grounding_metadata

        loop = asyncio.get_event_loop()
        stream = await loop.run_in_executor(
            None,
            lambda: self.client.models.generate_content_stream(
                model=model, contents=parts, config=config
            ),
        )
        # Iterate over the synchronous stream without blocking the event loop
        while True:
            chunk = await loop.run_in_executor(None, lambda: next(stream, None))
            if chunk is None:
                break
            last_response = chunk
            # Keep the chunk with usage_metadata (cumulative token counts)
            if getattr(chunk, "usage_metadata", None):
                usage_response = chunk
            # Keep the chunk with grounding_metadata (sources/citations)
            if chunk.candidates and getattr(chunk.candidates[0], "grounding_metadata", None):
                grounding_response = chunk
            if not chunk.candidates:
                continue
            for part in chunk.candidates[0].content.parts:
                if not part.text:
                    continue
                if include_thoughts and getattr(part, "thought", False):
                    yield {"type": "thought", "text": part.text}
                else:
                    answer_text += part.text

        # Build a result similar to _parse_response but from streamed data
        raw_json = {}
        if output_schema:
            try:
                raw_json = json.loads(answer_text)
            except json.JSONDecodeError:
                raw_json = {"response": answer_text}
        else:
            raw_json = {"response": answer_text}

        # Use the chunk that carries each type of metadata
        final = usage_response or last_response
        meta_response = grounding_response or usage_response or last_response

        # Debug: Check what we got from Gemini
        if meta_response and meta_response.candidates:
            candidate = meta_response.candidates[0]
            has_grounding = hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata is not None
            logger.error(f"DEBUG: Response has grounding_metadata: {has_grounding}")
            if has_grounding:
                meta = candidate.grounding_metadata
                logger.error(f"DEBUG: grounding_metadata attributes: {dir(meta)}")
                if hasattr(meta, 'grounding_chunks'):
                    logger.error(f"DEBUG: grounding_chunks count: {len(meta.grounding_chunks) if meta.grounding_chunks else 0}")

        sources = self._extract_sources(meta_response) if meta_response else []
        file_search_results = self._extract_file_search(meta_response) if meta_response else []
        usage = self._extract_usage(final) if final else {}

        parsed = {
            "raw_json": raw_json,
            "sources": sources,
            "file_search_results": file_search_results,
            "usage": usage,
        }

        logger.error(f"DEBUG: Extracted {len(sources)} grounding sources, {len(file_search_results)} file search results")

        yield {"type": "result", "data": parsed}

    async def _structure_response(
        self, text: str, output_schema: dict, model: str
    ) -> tuple[dict | None, dict | None]:
        """Re-process a free-form LLM response into structured JSON using the schema.
        Returns (structured_json, usage) tuple."""
        try:
            logger.info("Starting structured response extraction")
            config = types.GenerateContentConfig(
                system_instruction=(
                    "You are a data extraction assistant. Extract the information "
                    "from the provided diagnostic text and output it as JSON "
                    "matching the given schema exactly. Do not add commentary. "
                    "For the 'title' field, create a clean, concise knowledge-base "
                    "style heading (max 80 chars). Include the error code if present. "
                    "NEVER copy raw error text, timestamps, file paths, SQL, or "
                    "trace output into the title."
                ),
                temperature=0.2,
                response_mime_type="application/json",
                response_json_schema=output_schema,
            )

            # Prepare content properly
            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(
                        text=f"Extract structured data from this diagnostic response:\n\n{text}"
                    )]
                )
            ]

            logger.info("Calling Gemini API for structured response")
            loop = asyncio.get_event_loop()

            # Add timeout to prevent hanging indefinitely (60 second timeout)
            try:
                response = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: self.client.models.generate_content(
                            model=model,
                            contents=contents,
                            config=config,
                        ),
                    ),
                    timeout=60.0,
                )
                logger.info("Received structured response from Gemini API")
            except asyncio.TimeoutError:
                logger.error("Timeout while waiting for structured response from Gemini API")
                return None, None

            usage = self._extract_usage(response)
            structured_json = json.loads(response.text or "{}")
            logger.info("Successfully structured response")
            return structured_json, usage
        except json.JSONDecodeError as e:
            logger.error("Failed to parse structured JSON response: %s", e)
            return None, None
        except Exception as e:
            logger.error("Failed to structure response: %s", e, exc_info=True)
            return None, None

    async def chat_followup(
        self,
        system_prompt: str,
        history: list[dict],
        user_message: str,
        model: str = "gemini-2.5-flash",
        temperature: float = 1.0,
    ) -> dict:
        """Send a follow-up chat message with full conversation history."""
        contents = []
        for msg in history:
            contents.append(
                types.Content(
                    role=msg["role"],
                    parts=[types.Part.from_text(text=msg["content"])],
                )
            )
        contents.append(
            types.Content(
                role="user", parts=[types.Part.from_text(text=user_message)]
            )
        )

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
        )
        response = self.client.models.generate_content(
            model=model, contents=contents, config=config
        )

        usage = self._extract_usage(response)
        return {"content": response.text or "", "usage": usage}

    async def generate_expert_prompts(
        self,
        expert_name: str,
        expert_description: str,
        system_template: str,
        user_template: str,
        category: str = "grounded",
    ) -> dict[str, str]:
        """Use the LLM to generate tailored system and user prompts for a new expert.

        Takes the global templates as a structural reference and rewrites them
        to be domain-specific based on the expert name and description.
        The `category` parameter ("grounded" or "file_search") controls the
        emphasis of the generated prompts.
        Returns {"system_prompt": ..., "user_prompt": ...}.
        """
        if category == "file_search":
            emphasis = """## CRITICAL: Document-Driven Analysis
This expert will have access to UPLOADED INTERNAL DOCUMENTATION via file search (RAG).
The generated prompts MUST:
- Instruct the AI to PRIORITIZE information from the file search results / uploaded documents above all else.
- Emphasize citing specific internal documents, sections, and procedures.
- Make clear that internal documentation is the PRIMARY source of truth.
- Reference organization-specific configurations, runbooks, and known issues.
- Only fall back to general model knowledge when the uploaded documents do not cover the topic.
- Include instructions to search the uploaded documentation for relevant procedures."""
        else:
            emphasis = """## CRITICAL: Model Knowledge & Web Grounding
This expert will use the LLM's built-in knowledge and optional web grounding search.
The generated prompts MUST:
- Instruct the AI to leverage its deep domain knowledge and training data as the PRIMARY source.
- When grounding/web search results are available, incorporate them for up-to-date information.
- Focus on industry best practices, official documentation references, and well-known solutions.
- Provide vendor-recommended approaches and community-proven fixes.
- Do NOT mention file search, uploaded documents, or internal documentation — those are NOT available in this mode.
- Emphasize the model's expertise and general knowledge of the technology domain."""

        meta_prompt = f"""You are a prompt engineer. Your job is to create two prompts for a specialised diagnostic AI expert.

## Expert Profile
- **Name**: {expert_name}
- **Description**: {expert_description}

{emphasis}

## Instructions
1. You will be given two template prompts (a system prompt and a user prompt) that serve as structural references.
2. Rewrite BOTH prompts so they are specifically tailored for the expert described above.
3. Keep the same overall structure and formatting (markdown headers, numbered lists, etc.).
4. Make the system prompt deeply specific to the domain: mention the exact technologies, common error patterns, terminology, best practices, and diagnostic approaches relevant to this expert's specialty.
5. The user prompt template must keep the {{{{error_text}}}} placeholder exactly as-is — it will be substituted at runtime.
6. Do NOT add generic filler — every sentence should be relevant to the expert's domain.
7. Ensure the prompts align with the emphasis described above ({'document-driven RAG' if category == 'file_search' else 'model knowledge + web grounding'}).

## Template: System Prompt
```
{system_template}
```

## Template: User Prompt
```
{user_template}
```

## Output Format
Return your response as valid JSON with exactly two keys:
- "system_prompt": the full rewritten system prompt (string)
- "user_prompt": the full rewritten user prompt (string)

Return ONLY the JSON object, no markdown code fences, no explanation."""

        response = self.client.models.generate_content(
            model="gemini-3-pro-preview",
            contents=[types.Content(
                role="user",
                parts=[types.Part.from_text(text=meta_prompt)],
            )],
            config=types.GenerateContentConfig(
                temperature=0.7,
                response_mime_type="application/json",
            ),
        )

        import json
        result = json.loads(response.text)
        return {
            "system_prompt": result["system_prompt"],
            "user_prompt": result["user_prompt"],
        }

    async def generate_expert_description(self, system_name: str) -> str:
        """Generate an expert description/system prompt from a system name.

        Uses the standard elite-expert prompt template to produce a detailed,
        domain-specific system prompt for the given technology/system.
        """
        prompt = f"""Generate a system prompt that configures an AI to act as an elite, veteran expert in {system_name}.

Write the prompt using the exact structure, tone, and headings outlined below. You must extrapolate and fill in the deep, highly technical details, utilities, architecture components, and best practices specific to {system_name}.

Follow this exact structure:

[Paragraph 1: Persona and Role]
Write a paragraph stating that the AI is an elite, Level 3 Senior Technical Architect and [appropriate job title] for the system. Define its role: diagnosing complex issues, providing strategic guidance, writing precise code, and resolving critical enterprise incidents.

[Paragraph 2: Tone and Behavior]
Write a paragraph stating the AI communicates with the precise, calm, and authoritative tone of a veteran who has survived hundreds of critical P1 outages. Instruct it never to guess and to always ask for specific logs or diagnostic tests if unsure.

CORE DOMAIN KNOWLEDGE:
List exactly 5 bullet points. Each bullet point must cover a specific, highly technical sub-domain of the system. Include actual terminology, core architectures, specific command-line utilities, key troubleshooting areas, and performance tuning concepts unique to this technology.

OPERATIONAL DIRECTIVES:

    Safety First: Define what constitutes a destructive action in this specific system and instruct the AI to explicitly state risks and require backups/snapshots.

    Exact Paths and Commands: Instruct the AI to use standard environment variables, configuration paths, or best-practice syntax specific to this system rather than hardcoding. Provide 2-3 examples of these variables/paths.

    Version Specificity: Instruct the AI to assume a specific, modern, enterprise-standard version of this system unless the user specifies otherwise.

    No Filler: Instruct the AI not to use conversational filler like "I'd be happy to help" and to get straight to the technical diagnosis and resolution.

Do not include any instructions regarding output formatting, JSON, or markdown. Output only the generated prompt text."""

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)],
                )],
                config=types.GenerateContentConfig(
                    temperature=0.7,
                ),
            ),
        )
        return response.text or ""

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate vector embedding using gemini-embedding-001."""
        result = self.client.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=768,
            ),
        )
        return list(result.embeddings[0].values)

    async def generate_query_embedding(self, text: str) -> list[float]:
        """Generate vector embedding optimized for queries."""
        result = self.client.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=768,
            ),
        )
        return list(result.embeddings[0].values)

    # --- File Search Store ---
    async def create_file_search_store(self, name: str) -> str:
        """Create a new file search store and return its resource name."""
        loop = asyncio.get_event_loop()
        store = await loop.run_in_executor(
            None,
            lambda: self.client.file_search_stores.create(
                config={"display_name": name}
            ),
        )
        return store.name

    async def get_file_search_store(self, store_name: str) -> dict:
        """Get details of a file search store by resource name."""
        loop = asyncio.get_event_loop()
        store = await loop.run_in_executor(
            None,
            lambda: self.client.file_search_stores.get(name=store_name),
        )
        return {
            "name": store.name,
            "display_name": getattr(store, "display_name", ""),
            "create_time": str(getattr(store, "create_time", "")),
            "update_time": str(getattr(store, "update_time", "")),
            "active_documents_count": int(
                getattr(store, "active_documents_count", 0) or 0
            ),
            "pending_documents_count": int(
                getattr(store, "pending_documents_count", 0) or 0
            ),
            "failed_documents_count": int(
                getattr(store, "failed_documents_count", 0) or 0
            ),
            "size_bytes": int(getattr(store, "size_bytes", 0) or 0),
        }

    async def list_file_search_stores(self) -> list[dict]:
        """List all file search stores owned by the user."""
        loop = asyncio.get_event_loop()
        stores = await loop.run_in_executor(
            None,
            lambda: list(self.client.file_search_stores.list()),
        )
        results = []
        for store in stores:
            results.append(
                {
                    "name": store.name,
                    "display_name": getattr(store, "display_name", ""),
                    "create_time": str(getattr(store, "create_time", "")),
                    "update_time": str(getattr(store, "update_time", "")),
                    "active_documents_count": int(
                        getattr(store, "active_documents_count", 0) or 0
                    ),
                    "pending_documents_count": int(
                        getattr(store, "pending_documents_count", 0) or 0
                    ),
                    "failed_documents_count": int(
                        getattr(store, "failed_documents_count", 0) or 0
                    ),
                    "size_bytes": int(getattr(store, "size_bytes", 0) or 0),
                }
            )
        return results

    async def delete_file_search_store(self, store_name: str):
        """Delete a file search store by resource name."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.client.file_search_stores.delete(
                name=store_name, config={"force": True}
            ),
        )

    async def list_store_documents(self, store_name: str) -> list[dict]:
        """List all documents in a file search store."""
        loop = asyncio.get_event_loop()
        docs = await loop.run_in_executor(
            None,
            lambda: list(
                self.client.file_search_stores.documents.list(parent=store_name)
            ),
        )
        results = []
        for doc in docs:
            results.append(
                {
                    "name": getattr(doc, "name", ""),
                    "display_name": getattr(doc, "display_name", ""),
                    "state": str(getattr(doc, "state", "STATE_UNSPECIFIED")),
                    "size_bytes": int(getattr(doc, "size_bytes", 0) or 0),
                    "mime_type": getattr(doc, "mime_type", ""),
                    "create_time": str(getattr(doc, "create_time", "")),
                    "update_time": str(getattr(doc, "update_time", "")),
                }
            )
        return results

    async def get_store_document(self, document_name: str) -> dict:
        """Get details of a specific document in a file search store."""
        loop = asyncio.get_event_loop()
        doc = await loop.run_in_executor(
            None,
            lambda: self.client.file_search_stores.documents.get(
                name=document_name
            ),
        )
        return {
            "name": getattr(doc, "name", ""),
            "display_name": getattr(doc, "display_name", ""),
            "state": str(getattr(doc, "state", "STATE_UNSPECIFIED")),
            "size_bytes": int(getattr(doc, "size_bytes", 0) or 0),
            "mime_type": getattr(doc, "mime_type", ""),
            "create_time": str(getattr(doc, "create_time", "")),
            "update_time": str(getattr(doc, "update_time", "")),
        }

    async def start_file_upload(
        self,
        store_name: str,
        file_bytes: bytes,
        file_name: str,
    ) -> dict:
        """Start uploading a file to a file search store (non-blocking).

        Returns operation info immediately without polling.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._sync_start_upload,
            store_name,
            file_bytes,
            file_name,
        )

    def _sync_start_upload(
        self, store_name: str, file_bytes: bytes, file_name: str
    ) -> dict:
        """Synchronous helper: starts upload and returns operation info."""
        suffix = os.path.splitext(file_name)[1] or ".txt"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            op = self.client.file_search_stores.upload_to_file_search_store(
                file=tmp_path,
                file_search_store_name=store_name,
                config={"display_name": file_name},
            )
            result = {
                "operation_name": getattr(op, "name", ""),
                "done": bool(getattr(op, "done", False)),
                "document_name": None,
                "error": None,
            }
            if op.done:
                if hasattr(op, "result") and op.result:
                    result["document_name"] = getattr(op.result, "name", "")
                if hasattr(op, "error") and op.error:
                    result["error"] = str(op.error)
            return result
        finally:
            os.unlink(tmp_path)

    async def poll_upload_operation(self, operation_name: str) -> dict:
        """Check the status of an upload operation by name."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._sync_poll_operation, operation_name
        )

    def _sync_poll_operation(self, operation_name: str) -> dict:
        """Synchronous helper: polls an operation by name."""
        try:
            # operations.get() expects a typed operation object with from_api_response
            op_ref = types.UploadToFileSearchStoreOperation(name=operation_name)
            op = self.client.operations.get(operation=op_ref)
            result = {
                "operation_name": getattr(op, "name", operation_name),
                "done": bool(getattr(op, "done", False)),
                "document_name": None,
                "error": None,
            }
            if op.done:
                if hasattr(op, "result") and op.result:
                    result["document_name"] = getattr(op.result, "name", "")
                if hasattr(op, "error") and op.error:
                    result["error"] = str(op.error)
            return result
        except Exception as exc:
            logger.warning("Could not poll operation %s: %s", operation_name, exc)
            return {
                "operation_name": operation_name,
                "done": True,
                "document_name": None,
                "error": str(exc),
            }

    async def delete_file_search_document(
        self, store_name: str, document_name: str
    ):
        """Delete a document from a file search store."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.client.file_search_stores.documents.delete(
                name=document_name,
                config=types.DeleteDocumentConfig(force=True),
            ),
        )

    async def generate_infographic(
        self, prompt: str, aspect_ratio: str = "4:3", model: str = "gemini-2.5-flash-image", image_size: str = "1K"
    ) -> tuple[bytes, str]:
        """Generate an infographic using Gemini's image generation API.

        Returns (image_bytes, enhanced_prompt).
        """
        # Enhance the prompt for technical infographics
        enhanced_prompt = f"""Technical infographic style with clean, professional design.
{prompt}

Style guidelines:
- Use a clean, modern design aesthetic
- Include clear labels and annotations
- Use professional color scheme
- Ensure text is readable and well-sized
- Make it suitable for technical documentation"""

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.models.generate_content(
                model=model,
                contents=enhanced_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=['IMAGE'],
                    image_config=types.ImageConfig(
                        aspect_ratio=aspect_ratio,
                        image_size=image_size,
                    )
                )
            )
        )

        # Extract image from response parts
        image_bytes = None
        for part in response.parts:
            if part.inline_data is not None:
                image_bytes = part.inline_data.data
                break

        if not image_bytes:
            raise ValueError("No image generated in response")

        return image_bytes, enhanced_prompt

    # --- Internal helpers ---
    def _get_thinking_config(self, model: str, level: str) -> types.ThinkingConfig | None:
        """Get the appropriate thinking config for the model.

        Gemini 3 models use thinking_level (qualitative: minimal, low, medium, high).
        Gemini 2.5 models use thinking_budget (quantitative: token count).
        """
        # Detect model version
        is_gemini_3 = "gemini-3" in model.lower()
        is_flash = "flash" in model.lower()
        is_pro = "pro" in model.lower()

        if is_gemini_3:
            # Gemini 3 uses thinking_level
            # Validate supported levels per model
            if is_pro:
                # Gemini 3 Pro: supports low, high (NOT minimal or medium)
                if level in ["minimal", "medium"]:
                    logger.warning(f"Gemini 3 Pro does not support '{level}' thinking level, using 'high' instead")
                    level = "high"
                elif level not in ["low", "high"]:
                    level = "high"  # default
            elif is_flash:
                # Gemini 3 Flash: supports minimal, low, medium, high
                if level not in ["minimal", "low", "medium", "high"]:
                    level = "high"  # default

            return types.ThinkingConfig(
                thinking_level=level,
                include_thoughts=True,
            )
        else:
            # Gemini 2.5 uses thinking_budget (numeric token count)
            budget_map = {"low": 1024, "medium": 8192, "high": 24576}
            budget = budget_map.get(level, 8192)
            return types.ThinkingConfig(
                thinking_budget=budget,
                include_thoughts=True,
            )

    def _parse_response(self, response, output_schema: dict | None) -> dict:
        raw_json = {}
        text = response.text or ""

        if output_schema:
            try:
                raw_json = json.loads(text)
            except json.JSONDecodeError:
                raw_json = {"response": text}
        else:
            raw_json = {"response": text}

        sources = self._extract_sources(response)
        file_search_results = self._extract_file_search(response)
        usage = self._extract_usage(response)

        return {
            "raw_json": raw_json,
            "sources": sources,
            "file_search_results": file_search_results,
            "usage": usage,
        }

    def _extract_sources(self, response) -> list[dict]:
        """Extract web grounding sources with detailed citation information.

        Returns sources with citation details similar to file search results,
        including which parts of the response text cite each source.
        """
        sources = []
        if not response.candidates:
            logger.error("DEBUG: No candidates in response")
            return sources
        candidate = response.candidates[0]
        meta = getattr(candidate, "grounding_metadata", None)
        if not meta:
            logger.error("DEBUG: No grounding_metadata - Gemini chose not to use grounding for this query")
            return sources

        # Build chunk list with web source data
        chunks = getattr(meta, "grounding_chunks", None) or []
        logger.info(f"Found {len(chunks)} grounding_chunks")
        chunk_data: list[dict] = []
        for chunk in chunks:
            web = getattr(chunk, "web", None)
            if web:
                chunk_data.append({
                    "uri": getattr(web, "uri", ""),
                    "title": getattr(web, "title", "Source"),
                })

        if not chunk_data:
            logger.info("No web chunks found in grounding_chunks")
            return sources

        logger.info(f"Extracted {len(chunk_data)} web sources")

        # Build per-chunk citations with grounding_supports for inline references
        supports = getattr(meta, "grounding_supports", None) or []
        chunk_citations: dict[int, list[dict]] = {}

        for support in supports:
            segment = getattr(support, "segment", None)
            indices = getattr(support, "grounding_chunk_indices", None) or []
            scores = getattr(support, "confidence_scores", None) or []
            segment_text = getattr(segment, "text", "") if segment else ""

            for i, idx in enumerate(indices):
                if idx < len(chunk_data):
                    confidence = scores[i] if i < len(scores) else 0.0
                    if idx not in chunk_citations:
                        chunk_citations[idx] = []
                    chunk_citations[idx].append({
                        "cited_text": segment_text,
                        "confidence": round(confidence, 3),
                    })

        # Build final source list with citation details
        for idx, cd in enumerate(chunk_data):
            entry = {
                "uri": cd["uri"],
                "title": cd["title"],
                "citations": chunk_citations.get(idx, []),
            }
            sources.append(entry)

        return sources

    def _extract_file_search(self, response) -> list[dict]:
        """Extract file search citations with text snippets and confidence."""
        results = []
        if not response.candidates:
            return results
        candidate = response.candidates[0]
        meta = getattr(candidate, "grounding_metadata", None)
        if not meta:
            return results

        # Build chunk list with retrieved_context data
        chunks = getattr(meta, "grounding_chunks", None) or []
        chunk_data: list[dict] = []
        for chunk in chunks:
            retrieved = getattr(chunk, "retrieved_context", None)
            if retrieved:
                # Extract page span from rag_chunk
                rag_chunk = getattr(retrieved, "rag_chunk", None)
                page_start = None
                page_end = None
                chunk_text = getattr(retrieved, "text", "") or ""
                if rag_chunk:
                    page_span = getattr(rag_chunk, "page_span", None)
                    if page_span:
                        page_start = getattr(page_span, "first_page", None)
                        page_end = getattr(page_span, "last_page", None)
                    # rag_chunk.text may have more specific chunk text
                    rt = getattr(rag_chunk, "text", None)
                    if rt:
                        chunk_text = rt
                chunk_data.append({
                    "uri": getattr(retrieved, "uri", ""),
                    "title": getattr(retrieved, "title", ""),
                    "document_name": getattr(retrieved, "document_name", ""),
                    "text": chunk_text,
                    "first_page": page_start,
                    "last_page": page_end,
                })

        if not chunk_data:
            return results

        # Build per-chunk citations with grounding_supports for inline references
        supports = getattr(meta, "grounding_supports", None) or []
        # Track which chunks have been cited and their best confidence
        chunk_citations: dict[int, list[dict]] = {}
        for support in supports:
            segment = getattr(support, "segment", None)
            indices = getattr(support, "grounding_chunk_indices", None) or []
            scores = getattr(support, "confidence_scores", None) or []
            segment_text = getattr(segment, "text", "") if segment else ""
            for i, idx in enumerate(indices):
                if idx < len(chunk_data):
                    confidence = scores[i] if i < len(scores) else 0.0
                    if idx not in chunk_citations:
                        chunk_citations[idx] = []
                    chunk_citations[idx].append({
                        "cited_text": segment_text,
                        "confidence": round(confidence, 3),
                    })

        # Keep each chunk as a separate entry — different passages from the same
        # document should be listed individually so the displayed excerpt matches
        # the citations that reference it.
        for idx, cd in enumerate(chunk_data):
            entry = {
                "uri": cd["uri"],
                "title": cd["title"],
                "document_name": cd["document_name"],
                "text": cd["text"],
                "first_page": cd["first_page"],
                "last_page": cd["last_page"],
                "citations": chunk_citations.get(idx, []),
            }
            results.append(entry)

        return results

    def _extract_usage(self, response) -> dict:
        usage = {
            "prompt_token_count": 0,
            "candidates_token_count": 0,
            "total_token_count": 0,
            "cached_content_token_count": 0,
            "thoughts_token_count": 0,
        }
        meta = getattr(response, "usage_metadata", None)
        if not meta:
            return usage
        for key in usage:
            val = getattr(meta, key, None)
            if val is not None:
                usage[key] = val
        return usage


gemini_service = GeminiService()
