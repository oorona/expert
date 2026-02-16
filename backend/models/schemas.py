from pydantic import BaseModel, ConfigDict, Field
from typing import Literal, Optional


class TokenUsage(BaseModel):
    prompt_token_count: int = 0
    candidates_token_count: int = 0
    total_token_count: int = 0
    cached_content_token_count: int = 0


class Source(BaseModel):
    uri: str
    title: str = "Source"


class SimilarIncident(BaseModel):
    id: int
    session_id: str
    error_text: Optional[str] = None
    markdown_content: str = ""
    similarity: float = 0.0


class DiagnosisResponse(BaseModel):
    incident_id: int
    session_id: str
    raw_json: dict
    markdown_content: str
    sources: list[Source]
    usage: TokenUsage
    similar_incidents: list[SimilarIncident]
    file_search_results: list[dict] = []


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    diff_content: Optional[str] = None
    token_usage: TokenUsage


class SessionListItem(BaseModel):
    id: int
    session_id: str
    error_text: Optional[str] = None
    created_at: str


class SessionDetail(BaseModel):
    id: int
    session_id: str
    error_text: Optional[str] = None
    raw_json: dict
    markdown_content: str
    model_used: Optional[str] = None
    temperature: Optional[float] = None
    thinking_level: Optional[str] = None
    token_usage: dict
    grounding_sources: list
    file_search_results: list
    created_at: str
    chat_messages: list[ChatMessageResponse]


class DocumentCreate(BaseModel):
    slug: str = Field(..., pattern=r"^[a-z0-9][a-z0-9\-]*$", max_length=200)
    title: str = Field(..., max_length=500)
    markdown_content: str = Field(..., max_length=500_000)


class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    markdown_content: Optional[str] = Field(None, max_length=500_000)


class DocumentResponse(BaseModel):
    id: int
    slug: str
    title: str
    markdown_content: str
    created_at: str
    updated_at: str


class PromptCreate(BaseModel):
    name: str = Field(..., max_length=200)
    prompt_type: Literal["system", "user"]
    prompt_category: Literal["grounded", "file_search"] = "grounded"
    content: str = Field(..., max_length=100_000)
    expert_id: Optional[int] = None


class PromptUpdate(BaseModel):
    content: Optional[str] = Field(None, max_length=100_000)
    is_active: Optional[bool] = None


class PromptResponse(BaseModel):
    id: int
    name: str
    prompt_type: str
    prompt_category: str
    content: str
    is_active: bool
    expert_id: Optional[int] = None
    created_at: str
    updated_at: str


class SchemaCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    name: str = Field(..., max_length=200)
    schema_json: dict


class SchemaUpdate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    schema_json: Optional[dict] = None
    is_active: Optional[bool] = None


class SchemaResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: int
    name: str
    schema_json: dict
    is_active: bool
    created_at: str
    updated_at: str


class SearchResult(BaseModel):
    id: int
    entity_type: str
    title: Optional[str] = None
    error_text: Optional[str] = None
    markdown_content: str
    score: Optional[float] = None


# --- Experts ---


class ExpertCreate(BaseModel):
    name: str = Field(..., max_length=200)
    description: str = Field("", max_length=2000)


class ExpertUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    is_active: Optional[bool] = None


class ExpertDocumentResponse(BaseModel):
    id: int
    file_name: str
    gemini_file_name: Optional[str] = None
    operation_name: Optional[str] = None
    file_size: int
    status: str
    created_at: str


class ExpertResponse(BaseModel):
    id: int
    name: str
    description: str
    file_search_store_name: Optional[str] = None
    is_active: bool
    document_count: int = 0
    created_at: str
    updated_at: str
