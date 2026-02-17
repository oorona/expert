export interface TokenUsage {
  prompt_token_count: number;
  candidates_token_count: number;
  total_token_count: number;
  cached_content_token_count: number;
  thoughts_token_count: number;
}

export interface Citation {
  cited_text: string;
  confidence: number;
}

export interface Source {
  uri: string;
  title: string;
  citations: Citation[];
}

export interface FileSearchResult {
  uri: string;
  title: string;
  document_name: string;
  text: string;
  first_page: number | null;
  last_page: number | null;
  citations: Citation[];
}

export interface SimilarIncident {
  id: number;
  session_id: string;
  error_text: string | null;
  title?: string | null;
  markdown_content: string;
  similarity: number;
}

export interface DiagnosisResponse {
  incident_id: number;
  session_id: string;
  raw_json: Record<string, unknown>;
  markdown_content: string;
  sources: Source[];
  file_search_results: FileSearchResult[];
  usage: TokenUsage;
  similar_incidents: SimilarIncident[];
  duplicate_of?: SimilarIncident;
  model_used?: string;
  classification?: ClassificationResult;
  schema_used?: {
    id: number;
    name: string;
  };
}

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  diff_content?: string | null;
  token_usage: TokenUsage;
  created_at?: string;
}

export interface SessionListItem {
  id: number;
  session_id: string;
  error_text: string | null;
  title?: string | null;
  error_summary?: string | null;
  expert_id?: number | null;
  source?: string;
  status?: string;
  categories?: IncidentCategory[];
  schema_id?: number | null;
  classification_reasoning?: string | null;
  created_at: string;
}

export interface SessionDetail {
  id: number;
  session_id: string;
  error_text: string | null;
  title?: string | null;
  raw_json: Record<string, unknown>;
  markdown_content: string;
  model_used: string | null;
  temperature: number | null;
  thinking_level: string | null;
  token_usage: TokenUsage;
  grounding_sources: Source[];
  file_search_results: FileSearchResult[];
  infographic_data: string | null;
  infographic_prompt: string | null;
  notes: string | null;
  expert_id?: number | null;
  source?: string;
  status?: string;
  categories?: IncidentCategory[];
  schema_id?: number | null;
  classification_reasoning?: string | null;
  created_at: string;
  related_articles: RelatedArticle[];
  chat_messages: ChatMessage[];
}

export interface RelatedArticle {
  id: number;
  session_id: string;
  error_text: string | null;
  title?: string | null;
  error_summary?: string | null;
  relation_type: string;
  created_at: string;
}

export interface DocumentItem {
  id: number;
  slug: string;
  title: string;
  markdown_content: string;
  created_at: string;
  updated_at: string;
}

export interface PromptItem {
  id: number;
  name: string;
  prompt_type: string;
  prompt_category: string;
  content: string;
  is_active: boolean;
  expert_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface SchemaItem {
  id: number;
  name: string;
  description?: string;
  json_schema?: Record<string, unknown>; // New schemas table
  schema_json?: Record<string, unknown>; // Legacy OutputSchema table
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Category {
  name: string;
  display_name: string;
  description: string;
  intent_description: string;
  example_inputs: string[];
  key_outputs: string[];
}

export interface IncidentCategory {
  category: string;
  confidence: number;
  primary: boolean;
}

export interface ClassificationResult {
  primary_intent: string;
  categories: Array<{
    category: string;
    confidence: number;
    reasoning: string;
  }>;
  extracted_entities?: {
    error_codes?: string[];
    system_components?: string[];
    technologies?: string[];
    action_verbs?: string[];
  };
  recommended_schema?: {
    id: number;
    name: string;
  };
}

export interface SearchResult {
  id: number;
  session_id?: string;
  entity_type: string;
  title?: string;
  error_text?: string;
  error_summary?: string;
  markdown_content: string;
  score?: number;
}

export interface ExpertItem {
  id: number;
  name: string;
  description: string;
  file_search_store_name: string | null;
  is_active: boolean;
  document_count: number;
  store_document_count: number;
  created_at: string;
  updated_at: string;
}

export interface ExpertDocument {
  id: number;
  file_name: string;
  gemini_file_name: string | null;
  operation_name: string | null;
  file_size: number;
  status: string;
  created_at: string;
}

export interface FileSearchStore {
  name: string;
  display_name: string;
  create_time: string;
  update_time: string;
  active_documents_count: number;
  pending_documents_count: number;
  failed_documents_count: number;
  size_bytes: number;
}

export interface StoreDocument {
  name: string;
  display_name: string;
  state: string;
  size_bytes: number;
  mime_type: string;
  create_time: string;
  update_time: string;
}

export interface ModelInfo {
  id: string;
  label: string;
  inputCost: number;
  outputCost: number;
  supportsFileSearch: boolean;
  supportsGrounding: boolean;
}

export interface IncomingError {
  id: number;
  session_id: string;
  error_text: string | null;
  title?: string | null;
  error_summary?: string | null;
  source_system?: string | null;
  client_name?: string | null;
  expert_id?: number | null;
  source: string;
  status: string;
  created_at: string;
}

export interface ApiKeyItem {
  id: number;
  name: string;
  description: string;
  is_active: boolean;
  last_used_at: string | null;
  created_at: string;
  key_preview: string;
  raw_key?: string; // Only present on creation
}
