import type {
  ApiKeyItem,
  Category,
  ChatMessage,
  ClassificationResult,
  DiagnosisResponse,
  DocumentItem,
  ExpertDocument,
  ExpertItem,
  FileSearchStore,
  IncomingError,
  PromptItem,
  SchemaItem,
  SearchResult,
  SessionDetail,
  SessionListItem,
  StoreDocument,
} from "@/types";

const API_BASE = "/api";

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const text = await res.text();
    let message = text || res.statusText;
    try {
      const json = JSON.parse(text);
      if (json.detail) message = json.detail;
      else if (json.error) message = json.error;
    } catch {
      // keep raw text
    }
    throw new Error(message);
  }
  return res.json();
}

// --- Diagnose ---

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function diagnoseError(
  formData: FormData,
  onProgress?: (step: number, total: number, message: string) => void,
  onThought?: (text: string) => void
): Promise<DiagnosisResponse & { duplicate_of?: any }> {
  const res = await fetch(`${API_BASE}/diagnose`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const text = await res.text();
    let message = text || res.statusText;
    try {
      const json = JSON.parse(text);
      if (json.detail) message = json.detail;
    } catch { /* keep raw */ }
    throw new Error(message);
  }

  // If SSE stream, parse events
  if (res.headers.get("content-type")?.includes("text/event-stream") && res.body) {
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let result: any = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";

      for (const part of parts) {
        let eventType = "";
        let eventData = "";
        for (const line of part.split("\n")) {
          if (line.startsWith("event: ")) eventType = line.slice(7);
          else if (line.startsWith("data: ")) eventData = line.slice(6);
        }
        if (!eventData) continue;
        const parsed = JSON.parse(eventData);
        if (eventType === "progress" && onProgress) {
          onProgress(parsed.step, parsed.total, parsed.message);
        } else if (eventType === "thought" && onThought) {
          onThought(parsed.text);
        } else if (eventType === "done") {
          result = parsed;
        } else if (eventType === "error") {
          throw new Error(parsed.message || "Diagnosis failed");
        }
      }
    }

    if (result) return result;
    throw new Error("Stream ended without result");
  }

  // Fallback: plain JSON
  return res.json();
}

// --- Chat ---

export async function sendChatMessage(
  incidentId: number,
  message: string,
  requestUpdate: boolean = false,
  model: string = "gemini-2.5-flash",
  temperature: number = 1.0
): Promise<ChatMessage> {
  return fetchJSON(`${API_BASE}/chat/${incidentId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      model,
      temperature,
      request_update: requestUpdate,
    }),
  });
}

// --- Sessions / Incidents ---

export async function listSessions(): Promise<SessionListItem[]> {
  return fetchJSON(`${API_BASE}/incidents`);
}

export async function getSession(sessionId: string): Promise<SessionDetail> {
  return fetchJSON(`${API_BASE}/incidents/${sessionId}`);
}

export async function deleteSession(incidentId: number): Promise<void> {
  await fetch(`${API_BASE}/incidents/${incidentId}`, { method: "DELETE" });
}

export async function deleteAllSessions(): Promise<{ count: number }> {
  const res = await fetch(`${API_BASE}/incidents`, { method: "DELETE" });
  return res.json();
}

export async function updateNotes(
  incidentId: number,
  notes: string | null
): Promise<void> {
  await fetch(`${API_BASE}/incidents/${incidentId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ notes }),
  });
}

export async function saveInfographic(
  incidentId: number,
  infographicData: string,
  infographicPrompt: string
): Promise<void> {
  await fetchJSON(`${API_BASE}/incidents/${incidentId}/infographic`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      infographic_data: infographicData,
      infographic_prompt: infographicPrompt,
    }),
  });
}

export async function linkArticles(
  sessionIdA: string,
  sessionIdB: string,
  relationType: string = "related"
): Promise<void> {
  await fetchJSON(`${API_BASE}/incidents/link`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id_a: sessionIdA,
      session_id_b: sessionIdB,
      relation_type: relationType,
    }),
  });
}

// --- Documents ---

export async function listDocuments(): Promise<DocumentItem[]> {
  return fetchJSON(`${API_BASE}/documents`);
}

export async function getDocument(slug: string): Promise<DocumentItem> {
  return fetchJSON(`${API_BASE}/documents/${slug}`);
}

export async function createDocument(
  data: Omit<DocumentItem, "id" | "created_at" | "updated_at">
): Promise<DocumentItem> {
  return fetchJSON(`${API_BASE}/documents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function updateDocument(
  docId: number,
  data: { title?: string; markdown_content?: string }
): Promise<DocumentItem> {
  return fetchJSON(`${API_BASE}/documents/${docId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function deleteDocument(docId: number): Promise<void> {
  await fetch(`${API_BASE}/documents/${docId}`, { method: "DELETE" });
}

// --- Search ---

export async function searchContent(
  query: string,
  searchType: "text" | "semantic" | "hybrid" = "text",
  entity: "all" | "incidents" | "documents" = "all"
): Promise<SearchResult[]> {
  const params = new URLSearchParams({
    q: query,
    search_type: searchType,
    entity,
  });
  return fetchJSON(`${API_BASE}/search?${params}`);
}

// --- Admin: Prompts ---

export async function listPrompts(
  expertId?: number | null,
  category?: string
): Promise<PromptItem[]> {
  const params = new URLSearchParams();
  if (expertId !== undefined && expertId !== null) {
    params.set("expert_id", String(expertId));
  }
  if (category) {
    params.set("category", category);
  }
  const qs = params.toString();
  return fetchJSON(`${API_BASE}/admin/prompts${qs ? `?${qs}` : ""}`);
}

export async function getPrompt(id: number): Promise<PromptItem> {
  return fetchJSON(`${API_BASE}/admin/prompts/${id}`);
}

export async function createPrompt(data: {
  name: string;
  prompt_type: string;
  prompt_category: string;
  content: string;
  expert_id?: number | null;
}): Promise<PromptItem> {
  return fetchJSON(`${API_BASE}/admin/prompts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function updatePrompt(
  id: number,
  data: { content?: string; is_active?: boolean }
): Promise<PromptItem> {
  return fetchJSON(`${API_BASE}/admin/prompts/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

// --- Admin: Schemas ---

export async function listSchemas(): Promise<SchemaItem[]> {
  return fetchJSON(`${API_BASE}/admin/schemas`);
}

export async function getSchema(id: number): Promise<SchemaItem> {
  return fetchJSON(`${API_BASE}/admin/schemas/${id}`);
}

export async function createSchema(data: {
  name: string;
  schema_json: Record<string, unknown>;
}): Promise<SchemaItem> {
  return fetchJSON(`${API_BASE}/admin/schemas`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function updateSchema(
  id: number,
  data: { schema_json?: Record<string, unknown>; is_active?: boolean }
): Promise<SchemaItem> {
  return fetchJSON(`${API_BASE}/admin/schemas/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function getSchemaCategoryMappings(
  schemaId: number
): Promise<Array<{ category_name: string; priority: number }>> {
  return fetchJSON(`${API_BASE}/admin/schemas/${schemaId}/categories`);
}

export async function updateSchemaCategoryMappings(
  schemaId: number,
  categories: Array<{ category_name: string; priority: number }>
): Promise<Array<{ category_name: string; priority: number }>> {
  return fetchJSON(`${API_BASE}/admin/schemas/${schemaId}/categories`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ categories }),
  });
}

// --- Experts ---

export async function listExperts(): Promise<ExpertItem[]> {
  return fetchJSON(`${API_BASE}/experts`);
}

export async function getExpert(id: number): Promise<ExpertItem> {
  return fetchJSON(`${API_BASE}/experts/${id}`);
}

export async function createExpert(
  data: { name: string; description?: string },
  onProgress?: (step: number, total: number, message: string) => void
): Promise<ExpertItem> {
  const res = await fetch(`${API_BASE}/experts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });

  if (!res.ok) {
    const text = await res.text();
    let message = text || res.statusText;
    try {
      const json = JSON.parse(text);
      if (json.detail) message = json.detail;
    } catch { /* keep raw */ }
    throw new Error(message);
  }

  // If SSE stream, parse events
  if (res.headers.get("content-type")?.includes("text/event-stream") && res.body) {
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let result: ExpertItem | null = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // Process complete SSE messages
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";

      for (const part of parts) {
        let eventType = "";
        let eventData = "";
        for (const line of part.split("\n")) {
          if (line.startsWith("event: ")) eventType = line.slice(7);
          else if (line.startsWith("data: ")) eventData = line.slice(6);
        }
        if (!eventData) continue;
        const parsed = JSON.parse(eventData);
        if (eventType === "progress" && onProgress) {
          onProgress(parsed.step, parsed.total, parsed.message);
        } else if (eventType === "done") {
          result = parsed as ExpertItem;
        }
      }
    }

    if (result) return result;
    throw new Error("Stream ended without result");
  }

  // Fallback: plain JSON
  return res.json();
}

export async function generateExpertDescription(
  systemName: string
): Promise<string> {
  const data = await fetchJSON<{ description: string }>(
    `${API_BASE}/experts/generate-description`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ system_name: systemName }),
    }
  );
  return data.description;
}

export async function updateExpert(
  id: number,
  data: { name?: string; description?: string; is_active?: boolean }
): Promise<ExpertItem> {
  return fetchJSON(`${API_BASE}/experts/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function deleteExpert(id: number): Promise<void> {
  await fetch(`${API_BASE}/experts/${id}`, { method: "DELETE" });
}

export async function regenerateExpertPrompts(
  expertId: number,
  onProgress?: (step: number, total: number, message: string) => void
): Promise<{ status: string; categories: string[] }> {
  const res = await fetch(`${API_BASE}/experts/${expertId}/regenerate-prompts`, {
    method: "POST",
  });

  if (!res.ok) {
    const text = await res.text();
    let message = text || res.statusText;
    try {
      const json = JSON.parse(text);
      if (json.detail) message = json.detail;
    } catch { /* keep raw */ }
    throw new Error(message);
  }

  if (res.headers.get("content-type")?.includes("text/event-stream") && res.body) {
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let result: { status: string; categories: string[] } | null = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";

      for (const part of parts) {
        let eventType = "";
        let eventData = "";
        for (const line of part.split("\n")) {
          if (line.startsWith("event: ")) eventType = line.slice(7);
          else if (line.startsWith("data: ")) eventData = line.slice(6);
        }
        if (!eventData) continue;
        const parsed = JSON.parse(eventData);
        if (eventType === "progress" && onProgress) {
          onProgress(parsed.step, parsed.total, parsed.message);
        } else if (eventType === "done") {
          result = parsed;
        } else if (eventType === "error") {
          throw new Error(parsed.message || "Regeneration failed");
        }
      }
    }

    if (result) return result;
    throw new Error("Stream ended without result");
  }

  return res.json();
}

export async function listExpertDocuments(
  expertId: number
): Promise<ExpertDocument[]> {
  return fetchJSON(`${API_BASE}/experts/${expertId}/documents`);
}

export async function uploadExpertDocument(
  expertId: number,
  file: File
): Promise<ExpertDocument> {
  const formData = new FormData();
  formData.append("file", file);
  return fetchJSON(`${API_BASE}/experts/${expertId}/documents`, {
    method: "POST",
    body: formData,
  });
}

export async function deleteExpertDocument(
  expertId: number,
  docId: number
): Promise<void> {
  await fetch(`${API_BASE}/experts/${expertId}/documents/${docId}`, {
    method: "DELETE",
  });
}

export async function syncExpertDocument(
  expertId: number,
  docId: number
): Promise<ExpertDocument> {
  return fetchJSON(`${API_BASE}/experts/${expertId}/documents/${docId}/sync`, {
    method: "POST",
  });
}

// --- File Search Stores ---

export async function listFileSearchStores(): Promise<FileSearchStore[]> {
  return fetchJSON(`${API_BASE}/experts/file-stores`);
}

export async function getStoreInfo(
  expertId: number
): Promise<FileSearchStore> {
  return fetchJSON(`${API_BASE}/experts/${expertId}/store-info`);
}

export async function listStoreDocuments(
  expertId: number
): Promise<StoreDocument[]> {
  return fetchJSON(`${API_BASE}/experts/${expertId}/store-documents`);
}

export async function deleteStoreDocument(
  expertId: number,
  documentName: string
): Promise<void> {
  await fetch(`${API_BASE}/experts/${expertId}/store-documents`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_name: documentName }),
  });
}

// --- Incoming Errors ---

export async function listIncomingErrors(): Promise<IncomingError[]> {
  return fetchJSON(`${API_BASE}/incidents?incoming=true`);
}

export async function updateIncidentStatus(
  incidentId: number,
  status: string
): Promise<void> {
  await fetchJSON(`${API_BASE}/incidents?id=${incidentId}&action=status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
}

// --- Image Generation ---

export async function generateInfographic(
  prompt: string,
  aspectRatio: string = "4:3",
  model: string = "gemini-2.5-flash-image",
  imageSize: string = "1K"
): Promise<{ image_data: string; prompt_used: string }> {
  return fetchJSON(`${API_BASE}/generate-infographic`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, aspect_ratio: aspectRatio, model, image_size: imageSize }),
  });
}

// --- Client API Keys ---

export async function listApiKeys(): Promise<ApiKeyItem[]> {
  return fetchJSON(`${API_BASE}/admin/api-keys`);
}

export async function createApiKey(data: {
  name: string;
  description?: string;
}): Promise<ApiKeyItem> {
  return fetchJSON(`${API_BASE}/admin/api-keys`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function updateApiKey(
  id: number,
  data: { name?: string; description?: string; is_active?: boolean }
): Promise<ApiKeyItem> {
  return fetchJSON(`${API_BASE}/admin/api-keys/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function deleteApiKey(id: number): Promise<void> {
  await fetch(`${API_BASE}/admin/api-keys/${id}`, { method: "DELETE" });
}

// --- Categories & Classification ---

export async function listCategories(): Promise<Category[]> {
  return fetchJSON(`${API_BASE}/admin/categories`);
}

export async function classifyInput(
  userInput: string,
  model: string = "gemini-2.5-flash"
): Promise<ClassificationResult> {
  return fetchJSON(`${API_BASE}/classify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_input: userInput, model }),
  });
}
