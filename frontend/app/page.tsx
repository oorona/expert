"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { diagnoseError, deleteSession, getSession, listExperts, listIncomingErrors, updateNotes, updateIncidentStatus } from "@/lib/api";
import { ErrorInput } from "@/components/diagnosis/ErrorInput";
import { ModelControls } from "@/components/diagnosis/ModelControls";
import { ResultTabs } from "@/components/diagnosis/ResultTabs";
import { DynamicJsonRenderer } from "@/components/diagnosis/DynamicJsonRenderer";
import { SimilarIncidentBanner } from "@/components/diagnosis/SimilarIncidentBanner";
import { SourcesList } from "@/components/diagnosis/SourcesList";
import { InfographicGenerator } from "@/components/diagnosis/InfographicGenerator";
import { ChatArea } from "@/components/chat/ChatArea";
import { RelatedArticles } from "@/components/articles/RelatedArticles";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import type { DiagnosisResponse, TokenUsage, ExpertItem, ModelInfo, RelatedArticle, IncomingError } from "@/types";
import { useToast } from "@/components/ui/Toast";
import { formatDate } from "@/lib/utils";

const MODELS: ModelInfo[] = [
  { id: "gemini-2.5-flash-lite-preview-06-17", label: "2.5 Flash-Lite", inputCost: 0.10, outputCost: 0.40, supportsFileSearch: true, supportsGrounding: true },
  { id: "gemini-2.5-flash", label: "2.5 Flash", inputCost: 0.15, outputCost: 3.50, supportsFileSearch: false, supportsGrounding: true },
  { id: "gemini-2.5-pro", label: "2.5 Pro", inputCost: 1.25, outputCost: 10.00, supportsFileSearch: true, supportsGrounding: true },
  { id: "gemini-3-flash-preview", label: "3 Flash", inputCost: 0.50, outputCost: 3.00, supportsFileSearch: true, supportsGrounding: true },
  { id: "gemini-3-pro-preview", label: "3 Pro", inputCost: 2.00, outputCost: 12.00, supportsFileSearch: true, supportsGrounding: true },
];

function calcCost(usage: TokenUsage | null | undefined, modelId: string): number {
  if (!usage) return 0;
  const m = MODELS.find((x) => x.id === modelId);
  if (!m) return 0;
  return (
    ((usage.prompt_token_count || 0) / 1_000_000) * m.inputCost +
    ((usage.candidates_token_count || 0) / 1_000_000) * m.outputCost
  );
}

export default function Page() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-64 text-gray-400 dark:text-gray-500">Loading…</div>}>
      <Dashboard />
    </Suspense>
  );
}

function Dashboard() {
  const searchParams = useSearchParams();

  const [model, setModel] = useState("gemini-3-flash-preview");
  const [temperature, setTemperature] = useState(1.0);
  const [thinkingLevel, setThinkingLevel] = useState("medium");
  const [useGrounding, setUseGrounding] = useState(true);
  const [useFileSearch, setUseFileSearch] = useState(false);
  const [expertId, setExpertId] = useState<number | null>(null);
  const [experts, setExperts] = useState<ExpertItem[]>([]);

  const [loading, setLoading] = useState(false);
  const [diagProgress, setDiagProgress] = useState<{step: number; total: number; message: string} | null>(null);
  const [diagStartTime, setDiagStartTime] = useState<number | null>(null);
  const [diagTick, setDiagTick] = useState(0);
  const [thoughtText, setThoughtText] = useState("");
  const [preservedThoughts, setPreservedThoughts] = useState("");
  const [result, setResult] = useState<DiagnosisResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [duplicateOf, setDuplicateOf] = useState<import("@/types").SimilarIncident | null>(null);
  const [pendingFormData, setPendingFormData] = useState<FormData | null>(null);
  const [relatedArticles, setRelatedArticles] = useState<RelatedArticle[]>([]);

  const [controlsOpen, setControlsOpen] = useState(false);
  const [showThoughts, setShowThoughts] = useState(true);
  const [inputOpen, setInputOpen] = useState(true);
  const [inputResetKey, setInputResetKey] = useState(0);
  const [footerOpen, setFooterOpen] = useState(false);
  const [notes, setNotes] = useState("");
  const [notesSaved, setNotesSaved] = useState(true);
  const saveTimerRef = useRef<NodeJS.Timeout | null>(null);
  const thoughtEndRef = useRef<HTMLSpanElement>(null);

  // Review mode: when user clicks an incoming API error
  const [reviewMode, setReviewMode] = useState(false);
  const [reviewIncidentId, setReviewIncidentId] = useState<number | null>(null);
  const [incidentStatus, setIncidentStatus] = useState<string | null>(null);
  const [reviewErrorText, setReviewErrorText] = useState<string | null>(null);

  // Button loading states
  const [statusLoading, setStatusLoading] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);

  // Confirm dialog state
  const [confirmDialog, setConfirmDialog] = useState<{
    title: string;
    message: string;
    onConfirm: () => void | Promise<void>;
  } | null>(null);

  // Incoming tab
  const [activeTab, setActiveTab] = useState<"dashboard" | "incoming">("dashboard");
  const [incomingErrors, setIncomingErrors] = useState<IncomingError[]>([]);

  // Token accumulation across calls in this session
  const [sessionUsage, setSessionUsage] = useState<TokenUsage>({
    prompt_token_count: 0,
    candidates_token_count: 0,
    total_token_count: 0,
    cached_content_token_count: 0,
    thoughts_token_count: 0,
  });

  const toast = useToast();

  // Auto-scroll thought panel as new text arrives
  useEffect(() => {
    thoughtEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [thoughtText]);

  useEffect(() => {
    listExperts().then((list) => {
      setExperts(list);
      // Auto-select first active expert if none selected AND not loading a session
      const sessionId = searchParams.get("session");
      if (!expertId && !sessionId) {
        const active = list.filter((e: ExpertItem) => e.is_active);
        if (active.length > 0) setExpertId(active[0].id);
      }
    }).catch(() => {});
    // Load incoming errors and poll every 30s
    loadIncoming();
    const interval = setInterval(loadIncoming, 30_000);
    return () => clearInterval(interval);
  }, [searchParams]);

  async function loadIncoming() {
    try {
      const data = await listIncomingErrors();
      setIncomingErrors(data);
    } catch {
      // Backend may not be ready yet
    }
  }

  // Load session from URL if present
  useEffect(() => {
    const sessionId = searchParams.get("session");
    const isReview = searchParams.get("review") === "true";
    if (sessionId) {
      loadSession(sessionId, isReview);
    }
  }, [searchParams]);

  function addUsage(u: TokenUsage | null | undefined) {
    if (!u) return;
    setSessionUsage((prev) => ({
      prompt_token_count: prev.prompt_token_count + (u.prompt_token_count || 0),
      candidates_token_count: prev.candidates_token_count + (u.candidates_token_count || 0),
      total_token_count: prev.total_token_count + (u.total_token_count || 0),
      cached_content_token_count: prev.cached_content_token_count + (u.cached_content_token_count || 0),
      thoughts_token_count: prev.thoughts_token_count + (u.thoughts_token_count || 0),
    }));
  }

  // Tick every second while diagnosis is running for elapsed time display
  useEffect(() => {
    if (!diagStartTime) return;
    const timer = setInterval(() => setDiagTick((t) => t + 1), 1000);
    return () => clearInterval(timer);
  }, [diagStartTime]);

  function formatElapsed(start: number): string {
    void diagTick;
    const sec = Math.floor((Date.now() - start) / 1000);
    if (sec < 60) return `${sec}s`;
    const min = Math.floor(sec / 60);
    const rem = sec % 60;
    return `${min}m ${rem}s`;
  }

  function handleNewDiagnosis() {
    setResult(null);
    setError(null);
    setDuplicateOf(null);
    setPendingFormData(null);
    setRelatedArticles([]);
    setNotes("");
    setNotesSaved(true);
    setReviewMode(false);
    setReviewIncidentId(null);
    setReviewErrorText(null);
    setIncidentStatus(null);
    setDiagProgress(null);
    setDiagStartTime(null);
    setSessionUsage({ prompt_token_count: 0, candidates_token_count: 0, total_token_count: 0, cached_content_token_count: 0, thoughts_token_count: 0 });
    setInputOpen(true);
    setInputResetKey((k) => k + 1);
    // Clear session from URL without reload
    window.history.replaceState({}, "", "/");
  }

  async function loadSession(sessionId: string, isReview: boolean = false) {
    try {
      setLoading(true);
      const data = await getSession(sessionId);
      const usage = (data.token_usage ?? {
        prompt_token_count: 0,
        candidates_token_count: 0,
        total_token_count: 0,
        cached_content_token_count: 0,
        thoughts_token_count: 0,
      }) as TokenUsage;

      setIncidentStatus(data.status || null);

      // Review mode: API-ingested error that hasn't been diagnosed yet
      if (isReview && data.source === "api" && !data.markdown_content) {
        setReviewMode(true);
        setReviewIncidentId(data.id);
        setReviewErrorText(data.error_text || null);
        setInputOpen(true);
        setActiveTab("dashboard");
        // Pre-select the expert that was specified during ingestion
        const ingestedExpertId = (data.raw_json as Record<string, unknown>)?.expert_id;
        if (typeof ingestedExpertId === "number") {
          setExpertId(ingestedExpertId);
        }
        // Update status to in_review
        if (data.status === "created" || data.status === "pending_review") {
          try {
            await updateIncidentStatus(data.id, "in_review");
            setIncidentStatus("in_review");
            window.dispatchEvent(new Event("sessions-changed"));
          } catch { /* ignore */ }
        }
        // Don't set result yet — let the user diagnose it
        return;
      }

      setReviewMode(false);
      setReviewErrorText(data.error_text || null);
      setResult({
        incident_id: data.id,
        session_id: data.session_id,
        raw_json: data.raw_json,
        markdown_content: data.markdown_content,
        sources: data.grounding_sources,
        file_search_results: data.file_search_results,
        usage,
        similar_incidents: [],
        model_used: data.model_used || undefined,
      });
      // chat_messages loaded but not used in current UI
      setRelatedArticles(data.related_articles || []);
      setNotes(data.notes || "");
      setNotesSaved(true);
      if (data.model_used) setModel(data.model_used);
      if (data.temperature !== null) setTemperature(data.temperature);
      if (data.thinking_level) setThinkingLevel(data.thinking_level);
      // Set expert from incident's raw_json
      const incidentExpertId = (data.raw_json as Record<string, unknown>)?.expert_id;
      if (typeof incidentExpertId === "number") {
        setExpertId(incidentExpertId);
      }
      setInputOpen(false);
      // Sum incident usage + all chat message usages into session total
      setSessionUsage({
        prompt_token_count: (usage.prompt_token_count || 0) +
          data.chat_messages.reduce((s: number, m: any) => s + (m.token_usage?.prompt_token_count || 0), 0),
        candidates_token_count: (usage.candidates_token_count || 0) +
          data.chat_messages.reduce((s: number, m: any) => s + (m.token_usage?.candidates_token_count || 0), 0),
        total_token_count: (usage.total_token_count || 0) +
          data.chat_messages.reduce((s: number, m: any) => s + (m.token_usage?.total_token_count || 0), 0),
        cached_content_token_count: (usage.cached_content_token_count || 0) +
          data.chat_messages.reduce((s: number, m: any) => s + (m.token_usage?.cached_content_token_count || 0), 0),
        thoughts_token_count: (usage.thoughts_token_count || 0) +
          data.chat_messages.reduce((s: number, m: any) => s + (m.token_usage?.thoughts_token_count || 0), 0),
      });
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleDiagnose(formData: FormData) {
    setLoading(true);
    setError(null);
    setResult(null);
    setRelatedArticles([]);
    setDuplicateOf(null);
    setPendingFormData(null);
    setDiagProgress(null);
    setThoughtText("");
    setPreservedThoughts("");
    setDiagStartTime(Date.now());

    // In review mode, attach the existing incident_id so the backend
    // updates that incident instead of creating a new one
    if (reviewMode && reviewIncidentId) {
      formData.set("incident_id", String(reviewIncidentId));
    }

    try {
      const data = await diagnoseError(formData, (step, total, message) => {
        setDiagProgress({ step, total, message });
      }, (text) => {
        setThoughtText(prev => prev + text);
      });

      // Backend detected a near-duplicate — ask user what to do
      if (data.duplicate_of && !data.incident_id) {
        setDuplicateOf(data.duplicate_of);
        setPendingFormData(formData);
        setLoading(false);
        return;
      }

      // Attach the model used so cost calculation is always correct
      data.model_used = (formData.get("model") as string) || model;
      // Preserve thought text before it gets cleared
      setPreservedThoughts(thoughtText);
      setResult(data);
      setInputOpen(false);
      setNotes("");
      setNotesSaved(true);
      // If this was a review mode diagnosis, update status and clear review state
      if (reviewMode && reviewIncidentId) {
        setIncidentStatus("analyzed");
        setReviewMode(false);
        setReviewIncidentId(null);
        setReviewErrorText(null);
        loadIncoming(); // Refresh incoming list
      }
      window.dispatchEvent(new Event("sessions-changed"));
      // Accumulate session tokens
      addUsage(data.usage);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
      setDiagProgress(null);
      setDiagStartTime(null);
      setThoughtText("");
    }
  }

  async function handleForceCreate() {
    if (!pendingFormData) return;
    pendingFormData.set("force", "true");
    setDuplicateOf(null);
    setPendingFormData(null);
    await handleDiagnose(pendingFormData);
  }

  function handleViewDuplicate() {
    if (!duplicateOf) return;
    setDuplicateOf(null);
    setPendingFormData(null);
    window.location.href = `/?session=${duplicateOf.session_id}`;
  }

  function handleSelectSimilar(sessionId: string) {
    window.location.href = `/?session=${sessionId}`;
  }

  async function handleCreateArticle(question: string) {
    if (!result) return;
    const formData = new FormData();
    formData.set("error_text", question);
    formData.set("model", model);
    formData.set("temperature", temperature.toString());
    formData.set("thinking_level", thinkingLevel);
    formData.set("use_grounding", useGrounding.toString());
    formData.set("use_file_search", useFileSearch.toString());
    if (expertId) formData.set("expert_id", expertId.toString());
    formData.set("force", "true");
    formData.set("parent_session_id", result.session_id);

    setLoading(true);
    setDiagProgress(null);
    setThoughtText("");
    setDiagStartTime(Date.now());
    try {
      const data = await diagnoseError(formData, (step, total, message) => {
        setDiagProgress({ step, total, message });
      }, (text) => {
        setThoughtText(prev => prev + text);
      });
      if (data.duplicate_of && !data.incident_id) {
        toast.info("A similar article already exists");
        return;
      }
      window.dispatchEvent(new Event("sessions-changed"));
      toast.success("Follow-up article created");
      // Navigate to the new article
      window.location.href = `/?session=${data.session_id}`;
    } catch (err) {
      toast.error(String(err));
    } finally {
      setLoading(false);
      setDiagProgress(null);
      setDiagStartTime(null);
      setThoughtText("");
    }
  }

  const saveNotes = useCallback(
    (value: string) => {
      if (!result) return;
      updateNotes(result.incident_id, value || null).then(() => setNotesSaved(true));
    },
    [result]
  );

  function handleNotesChange(value: string) {
    setNotes(value);
    setNotesSaved(false);
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => saveNotes(value), 1500);
  }

  // Use model_used from result when available (ensures correct pricing after page reload)
  const costModel = result?.model_used || model;
  const currentCost = result ? calcCost(result.usage, costModel) : 0;
  const sessionCost = calcCost(sessionUsage, costModel);

  return (
    <div className="max-w-7xl mx-auto space-y-4">
      {/* Tab Bar */}
      <div className="flex border-b border-gray-200 dark:border-gray-700">
        <button
          onClick={() => setActiveTab("dashboard")}
          className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "dashboard"
              ? "border-blue-500 text-blue-600 dark:text-blue-400"
              : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
          }`}
        >
          Dashboard
        </button>
        <button
          onClick={() => { setActiveTab("incoming"); loadIncoming(); }}
          className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
            activeTab === "incoming"
              ? "border-orange-500 text-orange-600 dark:text-orange-400"
              : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
          }`}
        >
          Incoming
          {incomingErrors.length > 0 && (
            <span className="bg-orange-500 text-white text-xs font-bold rounded-full px-1.5 py-0.5 min-w-[20px] text-center">
              {incomingErrors.length}
            </span>
          )}
        </button>
      </div>

      {/* Incoming Tab */}
      {activeTab === "incoming" && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200">
              Incoming Errors
              {incomingErrors.length > 0 && (
                <span className="ml-2 text-sm font-normal text-gray-500 dark:text-gray-400">
                  ({incomingErrors.length})
                </span>
              )}
            </h2>
            <button
              onClick={loadIncoming}
              className="text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
            >
              ↻ Refresh
            </button>
          </div>
          {incomingErrors.length === 0 ? (
            <div className="px-6 py-12 text-center text-gray-400 dark:text-gray-500">
              <p className="text-lg mb-1">📭</p>
              <p className="text-sm">No incoming errors</p>
            </div>
          ) : (
            <ul className="divide-y divide-gray-100 dark:divide-gray-700">
              {incomingErrors.map((e) => {
                const statusColor =
                  e.status === "analyzed" ? "bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300" :
                  e.status === "in_review" ? "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300" :
                  "bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300";
                const statusLabel =
                  e.status === "analyzed" ? "Analyzed" :
                  e.status === "in_review" ? "In Review" :
                  "New";
                const displayText = e.status === "analyzed" && e.error_summary
                  ? e.error_summary
                  : e.error_text
                  ? e.error_text.length > 200 ? e.error_text.slice(0, 200) + "…" : e.error_text
                  : "No error text";
                return (
                  <li key={e.session_id}>
                    <a
                      href={e.status === "analyzed"
                        ? `/?session=${e.session_id}`
                        : `/?session=${e.session_id}&review=true`}
                      className="block px-6 py-4 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-gray-800 dark:text-gray-200 break-words whitespace-normal font-medium">
                            {e.title || displayText}
                          </p>
                          {e.title && (
                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 break-words whitespace-normal">
                              {displayText}
                            </p>
                          )}
                          <div className="flex items-center gap-2 mt-2 flex-wrap">
                            {e.expert_id && (() => {
                              const expert = experts.find(ex => ex.id === e.expert_id);
                              return expert ? (
                                <span className="text-[10px] px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded font-medium">
                                  {expert.name}
                                </span>
                              ) : null;
                            })()}
                            <span className="text-xs text-gray-400 dark:text-gray-500">
                              {formatDate(e.created_at)}
                            </span>
                          </div>
                        </div>
                        <div className="flex flex-col items-end gap-1.5 shrink-0">
                          <span className={`px-2 py-0.5 text-[11px] font-medium rounded-full ${statusColor}`}>
                            {statusLabel}
                          </span>
                          {e.status === "analyzed" && (
                            <button
                              onClick={async (ev) => {
                                ev.preventDefault();
                                ev.stopPropagation();
                                try {
                                  await updateIncidentStatus(e.id, "closed");
                                  toast.success("Incident closed");
                                  loadIncoming();
                                  window.dispatchEvent(new Event("sessions-changed"));
                                } catch (err) {
                                  toast.error(String(err));
                                }
                              }}
                              className="text-[11px] text-gray-500 dark:text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-colors"
                            >
                              ✕ Close
                            </button>
                          )}
                          <button
                            onClick={(ev) => {
                              ev.preventDefault();
                              ev.stopPropagation();
                              setConfirmDialog({
                                title: "Delete Incident",
                                message: "Are you sure you want to delete this incident? This action cannot be undone.",
                                onConfirm: async () => {
                                  try {
                                    await deleteSession(e.id);
                                    toast.success("Incident deleted");
                                    loadIncoming();
                                    window.dispatchEvent(new Event("sessions-changed"));
                                  } catch (err) {
                                    toast.error(String(err));
                                  } finally {
                                    setConfirmDialog(null);
                                  }
                                },
                              });
                            }}
                            className="text-[11px] text-gray-500 dark:text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-colors"
                          >
                            🗑 Delete
                          </button>
                        </div>
                      </div>
                    </a>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}

      {activeTab === "dashboard" && (<>
      {/* Model Controls — collapsed by default */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
        <button
          onClick={() => setControlsOpen(!controlsOpen)}
          className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors rounded-lg"
        >
          <div className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
            <span>⚙️</span>
            <span>Model & Settings</span>
            <span className="text-xs text-gray-400 dark:text-gray-500 font-normal ml-2">
              {MODELS.find((m) => m.id === model)?.label || model} · T={temperature.toFixed(1)} · Think={thinkingLevel}
              {useGrounding ? " · Grounded" : ""}
              {useFileSearch ? " · FileSearch" : ""}
            </span>
          </div>
          <span className="text-gray-400 dark:text-gray-500 text-xs">{controlsOpen ? "▼" : "▶"}</span>
        </button>
        {controlsOpen && (
          <div className="px-4 pb-4">
            <ModelControls
              model={model}
              setModel={setModel}
              temperature={temperature}
              setTemperature={setTemperature}
              thinkingLevel={thinkingLevel}
              setThinkingLevel={setThinkingLevel}
              useGrounding={useGrounding}
              setUseGrounding={setUseGrounding}
              useFileSearch={useFileSearch}
              setUseFileSearch={setUseFileSearch}
              showThoughts={showThoughts}
              setShowThoughts={setShowThoughts}
              expertId={expertId}
            />
          </div>
        )}
      </div>

      {/* Error Input — collapses after result */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
        <div className="flex items-center">
          <button
            onClick={() => setInputOpen(!inputOpen)}
            className="flex-1 flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors rounded-lg"
          >
            <div className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
              <span>🔍</span>
              <span>Error Input</span>
              {!inputOpen && result && (
                <>
                  <span className="text-xs text-green-500 dark:text-green-400 font-normal ml-2">✓ Saved</span>
                  <span className="text-xs text-gray-400 dark:text-gray-500 font-normal ml-1 truncate max-w-md">
                    {result.raw_json?.title
                      ? String(result.raw_json.title).slice(0, 80)
                      : result.raw_json?.error_summary
                      ? String(result.raw_json.error_summary).slice(0, 80)
                      : "Diagnosis complete"}
                  </span>
                </>
              )}
            </div>
            <span className="text-gray-400 dark:text-gray-500 text-xs">{inputOpen ? "▼" : "▶"}</span>
          </button>
          {result && (
            <button
              onClick={handleNewDiagnosis}
              className="mr-3 px-3 py-1.5 text-xs font-medium text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 hover:bg-blue-100 dark:hover:bg-blue-900/50 rounded-md transition-colors"
            >
              + New
            </button>
          )}
        </div>
        {inputOpen && (
          <div className="px-4 pb-4">
            <ErrorInput
              key={inputResetKey}
              onSubmit={handleDiagnose}
              loading={loading}
              model={model}
              temperature={temperature}
              thinkingLevel={thinkingLevel}
              useGrounding={useGrounding}
              useFileSearch={useFileSearch}
              expertId={expertId}
              setExpertId={setExpertId}
              experts={experts}
              initialErrorText={reviewErrorText}
            />
            {loading && diagProgress && diagStartTime && (
              <div className="mt-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg px-4 py-3 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm font-medium text-blue-700 dark:text-blue-300">
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    <span>Step {diagProgress.step} of {diagProgress.total}: {diagProgress.message}</span>
                  </div>
                  <span className="text-xs tabular-nums text-blue-500 dark:text-blue-500">{formatElapsed(diagStartTime)}</span>
                </div>
                <div className="w-full bg-blue-200 dark:bg-blue-800 rounded-full h-1.5">
                  <div
                    className="bg-blue-600 h-1.5 rounded-full transition-all duration-500"
                    style={{ width: `${(diagProgress.step / diagProgress.total) * 100}%` }}
                  />
                </div>
                {showThoughts && thoughtText && (
                  <div className="mt-2 max-h-48 overflow-y-auto rounded bg-gray-900 dark:bg-gray-950 p-3 font-mono text-xs text-gray-300 leading-relaxed whitespace-pre-wrap">
                    <div className="flex items-center gap-1.5 text-purple-400 font-semibold mb-1.5 text-[11px] uppercase tracking-wide">
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" /></svg>
                      Thinking
                    </div>
                    {thoughtText}
                    <span ref={thoughtEndRef} className="inline-block w-1.5 h-3.5 bg-purple-400 animate-pulse ml-0.5 align-text-bottom" />
                  </div>
                )}
              </div>
            )}
            {result && (
              <div className="mt-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg px-4 py-3 flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2 text-sm text-green-700 dark:text-green-300">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  <span className="font-medium">Saved</span>
                  <span className="text-green-600 dark:text-green-400 text-xs">Session {result.session_id.slice(0, 8)}</span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(JSON.stringify(result.raw_json, null, 2));
                      toast.success("JSON copied to clipboard");
                    }}
                    className="px-3 py-1.5 text-xs font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                  >
                    Copy JSON
                  </button>
                  <button
                    onClick={() => {
                      const blob = new Blob([result.markdown_content], { type: "text/markdown" });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = `diagnosis-${result.session_id.slice(0, 8)}.md`;
                      a.click();
                      URL.revokeObjectURL(url);
                      toast.success("Markdown exported");
                    }}
                    className="px-3 py-1.5 text-xs font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                  >
                    Export .md
                  </button>
                  <button
                    onClick={() => {
                      const url = `${window.location.origin}/?session=${result.session_id}`;
                      navigator.clipboard.writeText(url);
                      toast.success("Session link copied");
                    }}
                    className="px-3 py-1.5 text-xs font-medium text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-800 rounded hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors"
                  >
                    Share Link
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Progress banner visible when input is collapsed (e.g. follow-up article) */}
      {!inputOpen && loading && diagProgress && diagStartTime && (
        <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg px-4 py-3 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm font-medium text-blue-700 dark:text-blue-300">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <span>Step {diagProgress.step} of {diagProgress.total}: {diagProgress.message}</span>
            </div>
            <span className="text-xs tabular-nums text-blue-500 dark:text-blue-500">{formatElapsed(diagStartTime)}</span>
          </div>
          <div className="w-full bg-blue-200 dark:bg-blue-800 rounded-full h-1.5">
            <div
              className="bg-blue-600 h-1.5 rounded-full transition-all duration-500"
              style={{ width: `${(diagProgress.step / diagProgress.total) * 100}%` }}
            />
          </div>
          {showThoughts && thoughtText && (
            <div className="mt-2 max-h-48 overflow-y-auto rounded bg-gray-900 dark:bg-gray-950 p-3 font-mono text-xs text-gray-300 leading-relaxed whitespace-pre-wrap">
              <div className="flex items-center gap-1.5 text-purple-400 font-semibold mb-1.5 text-[11px] uppercase tracking-wide">
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" /></svg>
                Thinking
              </div>
              {thoughtText}
              <span ref={thoughtEndRef} className="inline-block w-1.5 h-3.5 bg-purple-400 animate-pulse ml-0.5 align-text-bottom" />
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-300 text-sm">
          {error}
        </div>
      )}

      {duplicateOf && (
        <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-5">
          <div className="flex items-start gap-3">
            <span className="text-2xl">📋</span>
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-semibold text-blue-900 dark:text-blue-200">
                Existing article found — {(duplicateOf.similarity * 100).toFixed(0)}% match
              </h3>
              <p className="mt-1 text-sm text-blue-800 dark:text-blue-300 truncate">
                {duplicateOf.title || duplicateOf.error_text || "Previous diagnosis"}
              </p>
              <div className="mt-3 flex items-center gap-3">
                <button
                  onClick={handleViewDuplicate}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
                >
                  View existing article
                </button>
                <button
                  onClick={handleForceCreate}
                  disabled={loading}
                  className="px-4 py-2 text-sm font-medium text-blue-700 dark:text-blue-300 bg-white dark:bg-gray-800 border border-blue-300 dark:border-blue-700 rounded-lg hover:bg-blue-50 dark:hover:bg-blue-900/30 transition-colors disabled:opacity-50"
                >
                  {loading ? "Creating..." : "Create new article anyway"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {result && (
        <div className="flex gap-6">
          {/* Main content column */}
          <div className="flex-1 min-w-0 space-y-4">
          <SimilarIncidentBanner
            incidents={result.similar_incidents}
            onSelect={handleSelectSimilar}
          />

          <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
            {/* Header with title and action buttons */}
            <div className="border-b border-gray-100 dark:border-gray-700 px-6 py-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <h2 className="text-lg font-bold text-gray-800 dark:text-gray-200">
                    {result.raw_json?.title
                      ? String(result.raw_json.title)
                      : result.raw_json?.error_summary
                      ? String(result.raw_json.error_summary)
                      : "Diagnosis Result"}
                  </h2>
                  <div className="flex items-center gap-3 mt-2 text-xs text-gray-400 dark:text-gray-500">
                    <span>Session {result.session_id.slice(0, 8)}</span>
                    {result.model_used && <span>Model: {result.model_used}</span>}
                    {incidentStatus && (
                      <span className={`px-2 py-0.5 rounded-full font-medium ${
                        incidentStatus === "closed" ? "bg-gray-50 dark:bg-gray-900/30 text-gray-600 dark:text-gray-400" :
                        incidentStatus === "analyzed" ? "bg-green-50 dark:bg-green-900/30 text-green-600 dark:text-green-400" :
                        incidentStatus === "in_review" ? "bg-purple-50 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400" :
                        "bg-yellow-50 dark:bg-yellow-900/30 text-yellow-600 dark:text-yellow-400"
                      }`}>
                        {incidentStatus.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {incidentStatus && incidentStatus !== "closed" && (
                    <button
                      onClick={async () => {
                        setStatusLoading(true);
                        const newStatus = "closed";
                        try {
                          await updateIncidentStatus(result.incident_id, newStatus);
                          setIncidentStatus("closed");
                          toast.success("Incident closed");
                          loadIncoming();
                          window.dispatchEvent(new Event("sessions-changed"));
                        } catch (err) {
                          toast.error(String(err));
                        } finally {
                          setStatusLoading(false);
                        }
                      }}
                      disabled={statusLoading || deleteLoading}
                      className="px-3 py-1.5 text-xs font-medium text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {statusLoading ? "Closing..." : "Close"}
                    </button>
                  )}
                  {incidentStatus === "closed" && (
                    <button
                      onClick={async () => {
                        setStatusLoading(true);
                        try {
                          await updateIncidentStatus(result.incident_id, "analyzed");
                          setIncidentStatus("analyzed");
                          toast.success("Incident reopened");
                          loadIncoming();
                          window.dispatchEvent(new Event("sessions-changed"));
                        } catch (err) {
                          toast.error(String(err));
                        } finally {
                          setStatusLoading(false);
                        }
                      }}
                      disabled={statusLoading || deleteLoading}
                      className="px-3 py-1.5 text-xs font-medium text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {statusLoading ? "Reopening..." : "Reopen"}
                    </button>
                  )}
                  <button
                    onClick={() => {
                      setConfirmDialog({
                        title: "Delete Diagnosis",
                        message: "Are you sure you want to permanently delete this diagnosis? This action cannot be undone.",
                        onConfirm: async () => {
                          setDeleteLoading(true);
                          try {
                            await deleteSession(result.incident_id);
                            toast.success("Diagnosis deleted");
                            window.dispatchEvent(new Event("sessions-changed"));
                            handleNewDiagnosis();
                          } catch (err) {
                            toast.error(String(err));
                          } finally {
                            setDeleteLoading(false);
                            setConfirmDialog(null);
                          }
                        },
                      });
                    }}
                    disabled={statusLoading || deleteLoading}
                    className="px-3 py-1.5 text-xs font-medium text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded hover:bg-red-100 dark:hover:bg-red-900/50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {deleteLoading ? "Deleting..." : "Delete"}
                  </button>
                </div>
              </div>
            </div>

            <div className="p-6">
            {/* Collapsible thought process */}
            {preservedThoughts && (
              <details className="mb-6 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
                <summary className="cursor-pointer px-4 py-3 bg-gray-50 dark:bg-gray-800/50 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
                  <svg className="w-4 h-4 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                  <span>Thought Process</span>
                  <span className="ml-auto text-xs text-gray-500 dark:text-gray-400">Click to expand</span>
                </summary>
                <div className="p-4 bg-gray-900 dark:bg-gray-950">
                  <pre className="font-mono text-xs text-gray-300 leading-relaxed whitespace-pre-wrap overflow-x-auto">
                    {preservedThoughts}
                  </pre>
                </div>
              </details>
            )}

            <ResultTabs
              diagnosisContent={
                <div className="space-y-6">
                  <DynamicJsonRenderer data={result.raw_json} />
                  {result.raw_json?.visual_aid_suggested === true && result.raw_json?.image_generation_prompt ? (
                    <InfographicGenerator
                      suggestedPrompt={String(result.raw_json.image_generation_prompt)}
                      incidentId={result.incident_id}
                    />
                  ) : null}
                </div>
              }
              webSourcesContent={
                result.sources.length > 0 ? (
                  <SourcesList sources={result.sources} />
                ) : null
              }
              fileSearchContent={
                result.file_search_results.length > 0 ? (
                  <div className="space-y-3">
                    <h3 className="font-semibold dark:text-gray-200">
                      📄 Document Citations ({result.file_search_results.length})
                    </h3>
                    {result.file_search_results.map((r, i) => (
                      <div
                        key={i}
                        className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden"
                      >
                        <div className="flex items-center gap-2 px-4 py-2.5 bg-gray-50 dark:bg-gray-800/50">
                          <span className="text-sm">📎</span>
                          <p className="text-sm font-medium dark:text-gray-200 flex-1">
                            {r.title || r.document_name || "Document"}
                          </p>
                          {r.first_page != null && (
                            <span className="px-2 py-0.5 text-xs font-medium bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 rounded">
                              {r.first_page === r.last_page || r.last_page == null
                                ? `p. ${r.first_page}`
                                : `pp. ${r.first_page}–${r.last_page}`}
                            </span>
                          )}
                          {r.uri && (
                            <a
                              href={r.uri}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                            >
                              Open
                            </a>
                          )}
                        </div>
                        {r.text && (
                          <div className="px-4 py-2.5 text-xs text-gray-700 dark:text-gray-300 bg-gray-50/50 dark:bg-gray-900/30 border-t border-gray-100 dark:border-gray-700">
                            <p className="font-medium text-gray-500 dark:text-gray-400 mb-1">Retrieved passage:</p>
                            <p className="whitespace-pre-wrap leading-relaxed line-clamp-6">{r.text}</p>
                          </div>
                        )}
                        {r.citations.length > 0 && (
                          <div className="px-4 py-2 space-y-1.5 border-t border-gray-100 dark:border-gray-700">
                            <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Model used this for:</p>
                            {r.citations.map((c, ci) => (
                              <div key={ci} className="flex items-start gap-2 text-xs">
                                <span className="shrink-0 mt-0.5 w-1.5 h-1.5 rounded-full bg-blue-400" />
                                <span className="text-gray-600 dark:text-gray-400 line-clamp-2">{c.cited_text}</span>
                                <span className="shrink-0 text-gray-400 dark:text-gray-500">
                                  {(c.confidence * 100).toFixed(0)}%
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : null
              }
            />
            </div>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <ChatArea
              incidentId={result.incident_id}
              sessionId={result.session_id}
              model={model}
              temperature={temperature}
              onTokenUsage={addUsage}
              onCreateArticle={handleCreateArticle}
            />
          </div>

          {/* Notes */}
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow px-6 py-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                📝 Notes
              </h3>
              <span className="text-xs text-gray-400 dark:text-gray-500">
                {notesSaved ? "✓ Saved" : "Saving..."}
              </span>
            </div>
            <textarea
              value={notes}
              onChange={(e) => handleNotesChange(e.target.value)}
              placeholder="Add your notes here... (auto-saved)"
              className="w-full h-28 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm resize-y focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-800 dark:text-gray-100"
            />
          </div>
          </div>{/* end main content column */}

          {/* Right sidebar — related articles */}
          {relatedArticles.length > 0 && (
            <aside className="w-72 shrink-0 hidden lg:block">
              <div className="sticky top-6">
                <RelatedArticles articles={relatedArticles} currentSessionId={result.session_id} />
              </div>
            </aside>
          )}
        </div>
      )}
      </>)}

      {/* Token Cost Footer */}
      <div className="fixed bottom-0 right-0 z-40">
        <button
          onClick={() => setFooterOpen(!footerOpen)}
          className="flex items-center gap-1.5 bg-gray-800 dark:bg-gray-700 text-gray-200 dark:text-gray-300 px-3 py-1.5 rounded-tl-lg text-xs font-medium shadow-lg hover:bg-gray-700 dark:hover:bg-gray-600 transition-colors"
        >
          <span>💰</span>
          {footerOpen ? "▶" : "◀"}
          {!footerOpen && (
            <span className="ml-1 tabular-nums">
              {(sessionUsage.total_token_count || 0).toLocaleString()} tokens · ${sessionCost > 0 ? sessionCost.toFixed(4) : "0.00"}
            </span>
          )}
        </button>
        {footerOpen && (
          <div className="bg-gray-800 dark:bg-gray-700 text-gray-200 dark:text-gray-300 px-4 py-3 rounded-tl-lg shadow-lg border-t border-l border-gray-600 dark:border-gray-500 min-w-[280px]">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-400 mb-2">Token Usage</h4>
            {result?.usage && (
              <div className="mb-2 pb-2 border-b border-gray-600 dark:border-gray-500">
                <p className="text-xs text-gray-400 mb-1">Last Call</p>
                <div className="flex flex-wrap gap-x-3 text-xs">
                  <span>In: {(result.usage.prompt_token_count || 0).toLocaleString()}</span>
                  <span>Out: {(result.usage.candidates_token_count || 0).toLocaleString()}</span>
                  {(result.usage.thoughts_token_count || 0) > 0 && (
                    <span className="text-purple-400">Think: {result.usage.thoughts_token_count.toLocaleString()}</span>
                  )}
                  <span className="font-medium text-green-400">${currentCost.toFixed(4)}</span>
                </div>
              </div>
            )}
            <div>
              <p className="text-xs text-gray-400 mb-1">Session Total</p>
              <div className="flex flex-wrap gap-x-3 text-xs">
                <span>In: {(sessionUsage.prompt_token_count || 0).toLocaleString()}</span>
                <span>Out: {(sessionUsage.candidates_token_count || 0).toLocaleString()}</span>
                {(sessionUsage.thoughts_token_count || 0) > 0 && (
                  <span className="text-purple-400">Think: {sessionUsage.thoughts_token_count.toLocaleString()}</span>
                )}
                <span className="font-medium text-green-400">${sessionCost.toFixed(4)}</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Confirm Dialog */}
      {confirmDialog && (
        <ConfirmDialog
          title={confirmDialog.title}
          message={confirmDialog.message}
          confirmLabel="Delete"
          variant="danger"
          onConfirm={confirmDialog.onConfirm}
          onCancel={() => setConfirmDialog(null)}
          loading={deleteLoading}
        />
      )}
    </div>
  );
}
