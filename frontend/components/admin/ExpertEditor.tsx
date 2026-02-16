"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import type { ExpertDocument, ExpertItem, StoreDocument } from "@/types";
import {
  listExpertDocuments,
  uploadExpertDocument,
  deleteExpertDocument,
  syncExpertDocument,
  updateExpert,
  deleteExpert,
  listStoreDocuments,
  deleteStoreDocument,
  regenerateExpertPrompts,
} from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import { InlineConfirm } from "@/components/ui/InlineConfirm";

interface Props {
  expert: ExpertItem;
  onUpdate: () => void;
}

type ConfirmAction =
  | { kind: "delete-expert" }
  | { kind: "delete-doc"; docId: number; fileName: string }
  | { kind: "delete-store-doc"; docName: string; displayName: string };

export function ExpertEditor({ expert, onUpdate }: Props) {
  const [name, setName] = useState(expert.name);
  const [description, setDescription] = useState(expert.description);
  const [docs, setDocs] = useState<ExpertDocument[]>([]);
  const [storeDocs, setStoreDocs] = useState<StoreDocument[]>([]);
  const [expanded, setExpanded] = useState(false);
  const [showStoreDocs, setShowStoreDocs] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [syncing, setSyncing] = useState<number | null>(null);
  const [dirty, setDirty] = useState(false);
  const [loadingStore, setLoadingStore] = useState(false);
  const [pendingConfirm, setPendingConfirm] = useState<ConfirmAction | null>(null);
  const [uploadStartTimes, setUploadStartTimes] = useState<Record<number, number>>({});
  const [elapsedTick, setElapsedTick] = useState(0);
  const [regenerating, setRegenerating] = useState(false);
  const [regenProgress, setRegenProgress] = useState<{ step: number; total: number; message: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const toast = useToast();

  const cancelConfirm = useCallback(() => setPendingConfirm(null), []);

  useEffect(() => {
    if (expanded) {
      loadDocs();
      if (expert.file_search_store_name) loadStoreDocs();
    } else {
      cancelConfirm();
    }
  }, [expanded, cancelConfirm]);

  // Auto-poll for uploading documents
  useEffect(() => {
    const pendingDocs = docs.filter(
      (d) => d.status === "uploading" || d.status === "pending"
    );
    if (pendingDocs.length === 0) return;

    // Track start times for newly pending docs
    setUploadStartTimes((prev) => {
      const next = { ...prev };
      for (const d of pendingDocs) {
        if (!next[d.id]) next[d.id] = Date.now();
      }
      return next;
    });

    let justFinished = false;

    const interval = setInterval(async () => {
      for (const doc of pendingDocs) {
        try {
          const updated = await syncExpertDocument(expert.id, doc.id);
          setDocs((prev) =>
            prev.map((d) => (d.id === updated.id ? updated : d))
          );
          if (
            updated.status === "indexed" &&
            (doc.status === "uploading" || doc.status === "pending")
          ) {
            toast.success(`"${doc.file_name}" indexed successfully`);
            setUploadStartTimes((prev) => {
              const next = { ...prev };
              delete next[doc.id];
              return next;
            });
            justFinished = true;
          } else if (
            updated.status === "error" &&
            (doc.status === "uploading" || doc.status === "pending")
          ) {
            toast.error(`"${doc.file_name}" failed to index`);
            setUploadStartTimes((prev) => {
              const next = { ...prev };
              delete next[doc.id];
              return next;
            });
            justFinished = true;
          }
        } catch {
          // ignore polling errors
        }
      }
      // Auto-refresh store documents when an upload finishes
      if (justFinished && expert.file_search_store_name) {
        loadStoreDocs();
        onUpdate();
        justFinished = false;
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [docs, expert.id, toast]);

  // Tick every second for elapsed time display
  useEffect(() => {
    const pendingDocs = docs.filter(
      (d) => d.status === "uploading" || d.status === "pending"
    );
    if (pendingDocs.length === 0) return;
    const timer = setInterval(() => setElapsedTick((t) => t + 1), 1000);
    return () => clearInterval(timer);
  }, [docs]);

  function formatElapsed(startTime: number): string {
    void elapsedTick; // force re-render via tick state
    const sec = Math.floor((Date.now() - startTime) / 1000);
    if (sec < 60) return `${sec}s`;
    const min = Math.floor(sec / 60);
    const rem = sec % 60;
    return `${min}m ${rem}s`;
  }

  async function loadDocs() {
    try {
      const data = await listExpertDocuments(expert.id);
      setDocs(data);
    } catch {
      // ignore
    }
  }

  async function loadStoreDocs() {
    setLoadingStore(true);
    try {
      const data = await listStoreDocuments(expert.id);
      if (Array.isArray(data)) {
        setStoreDocs(data);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load store documents");
    } finally {
      setLoadingStore(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    try {
      await updateExpert(expert.id, { name, description });
      setDirty(false);
      toast.success("Expert saved");
      onUpdate();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleToggle(active: boolean) {
    try {
      await updateExpert(expert.id, { is_active: active });
      toast.info(active ? "Expert activated" : "Expert deactivated");
      onUpdate();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Toggle failed");
    }
  }

  async function confirmDeleteExpert() {
    try {
      await deleteExpert(expert.id);
      toast.success(`"${expert.name}" deleted`);
      cancelConfirm();
      onUpdate();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed");
      cancelConfirm();
    }
  }

  async function handleUpload(file: File) {
    setUploading(true);
    try {
      await uploadExpertDocument(expert.id, file);
      toast.info(`"${file.name}" upload started`);
      await loadDocs();
      onUpdate();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function confirmDeleteDoc(docId: number) {
    const doc = docs.find((d) => d.id === docId);
    try {
      await deleteExpertDocument(expert.id, docId);
      toast.success(`"${doc?.file_name ?? "Document"}" deleted`);
      cancelConfirm();
      await loadDocs();
      onUpdate();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed");
      cancelConfirm();
    }
  }

  async function handleSyncDoc(docId: number) {
    setSyncing(docId);
    try {
      const updated = await syncExpertDocument(expert.id, docId);
      setDocs((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
      toast.info(`Status: ${updated.status}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setSyncing(null);
    }
  }

  async function confirmDeleteStoreDoc(docName: string) {
    const displayName =
      storeDocs.find((sd) => sd.name === docName)?.display_name ||
      docName.split("/").pop() ||
      docName;
    try {
      await deleteStoreDocument(expert.id, docName);
      toast.success(`"${displayName}" removed from store`);
      cancelConfirm();
      await loadStoreDocs();
      await loadDocs();
      onUpdate();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed");
      cancelConfirm();
    }
  }

  async function handleRegeneratePrompts() {
    setRegenerating(true);
    setRegenProgress(null);
    try {
      await regenerateExpertPrompts(expert.id, (step, total, message) => {
        setRegenProgress({ step, total, message });
      });
      toast.success("Prompts regenerated successfully");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Regeneration failed");
    } finally {
      setRegenerating(false);
      setRegenProgress(null);
    }
  }

  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function statusBadge(status: string) {
    const colors: Record<string, string> = {
      indexed:
        "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400",
      error:
        "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400",
      uploading:
        "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400",
      pending:
        "bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400",
    };
    return (
      <span
        className={`text-xs ml-2 px-1.5 py-0.5 rounded-full ${
          colors[status] || colors.pending
        }`}
      >
        {status}
      </span>
    );
  }

  function storeStateBadge(state: string) {
    if (state.includes("ACTIVE"))
      return (
        <span className="text-xs px-1.5 py-0.5 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400">
          active
        </span>
      );
    if (state.includes("PENDING"))
      return (
        <span className="text-xs px-1.5 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400">
          pending
        </span>
      );
    if (state.includes("FAILED"))
      return (
        <span className="text-xs px-1.5 py-0.5 rounded-full bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400">
          failed
        </span>
      );
    return (
      <span className="text-xs px-1.5 py-0.5 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400">
        {state}
      </span>
    );
  }

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 text-sm"
          >
            {expanded ? "▼" : "▶"}
          </button>
          <div>
            <h3 className="font-semibold text-gray-800 dark:text-gray-200">
              {expert.name}
            </h3>
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {(storeDocs.length || expert.store_document_count || expert.document_count)}
              {" "}document{(storeDocs.length || expert.store_document_count || expert.document_count) !== 1 ? "s" : ""}
              {expert.file_search_store_name && " · Store configured"}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-sm text-gray-700 dark:text-gray-300">
            <input
              type="checkbox"
              checked={expert.is_active}
              onChange={(e) => handleToggle(e.target.checked)}
              className="rounded"
            />
            Active
          </label>
          <button
            onClick={() => setPendingConfirm({ kind: "delete-expert" })}
            className="px-2 py-1 text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"
          >
            Delete
          </button>
        </div>
      </div>

      {/* Inline confirm: delete expert */}
      {pendingConfirm?.kind === "delete-expert" && (
        <div className="mb-3">
          <InlineConfirm
            message={`Delete "${expert.name}" and all its documents?`}
            confirmLabel="Delete Expert"
            variant="danger"
            onConfirm={confirmDeleteExpert}
            onCancel={cancelConfirm}
          />
        </div>
      )}

      {/* Upload progress banner — visible even when collapsed */}
      {docs.filter((d) => d.status === "uploading" || d.status === "pending").length > 0 && (
        <div className="mb-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3 space-y-2">
          <div className="flex items-center gap-2 text-sm font-medium text-blue-700 dark:text-blue-300">
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Indexing documents…
          </div>
          {docs
            .filter((d) => d.status === "uploading" || d.status === "pending")
            .map((doc) => (
              <div key={doc.id} className="flex items-center justify-between text-xs text-blue-600 dark:text-blue-400 pl-6">
                <span className="truncate">{doc.file_name}</span>
                <span className="ml-2 tabular-nums text-blue-500 dark:text-blue-500 whitespace-nowrap">
                  {uploadStartTimes[doc.id] ? formatElapsed(uploadStartTimes[doc.id]) : "starting…"}
                </span>
              </div>
            ))}
          <p className="text-xs text-blue-500 dark:text-blue-500 pl-6">
            Polling every 5s — you&apos;ll be notified when complete
          </p>
        </div>
      )}

      {expanded && (
        <div className="space-y-4 mt-4">
          {/* Edit name / description */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  setDirty(true);
                }}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 dark:text-gray-100"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                Description
              </label>
              <input
                type="text"
                value={description}
                onChange={(e) => {
                  setDescription(e.target.value);
                  setDirty(true);
                }}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 dark:text-gray-100"
              />
            </div>
          </div>

          {dirty && (
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-3 py-1 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700 disabled:bg-gray-400"
            >
              {saving ? "Saving..." : "Save Changes"}
            </button>
          )}

          {/* Regenerate Prompts */}
          <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
            <div className="flex items-center justify-between mb-2">
              <div>
                <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                  Regenerate Prompts
                </h4>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  Re-run AI prompt generation using the current description. This replaces all existing prompts for this expert.
                </p>
              </div>
              <button
                onClick={handleRegeneratePrompts}
                disabled={regenerating || !expert.description?.trim()}
                className="px-3 py-1.5 bg-amber-600 text-white rounded text-xs font-medium hover:bg-amber-700 disabled:bg-gray-400 disabled:cursor-not-allowed whitespace-nowrap ml-4"
              >
                {regenerating ? "Regenerating…" : "⟳ Regenerate"}
              </button>
            </div>
            {regenerating && regenProgress && (
              <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-3 space-y-2">
                <div className="flex items-center gap-2 text-sm font-medium text-amber-700 dark:text-amber-300">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  <span>Step {regenProgress.step} of {regenProgress.total}: {regenProgress.message}</span>
                </div>
                <div className="w-full bg-amber-200 dark:bg-amber-800 rounded-full h-1.5">
                  <div
                    className="bg-amber-600 h-1.5 rounded-full transition-all duration-300"
                    style={{ width: `${(regenProgress.step / regenProgress.total) * 100}%` }}
                  />
                </div>
              </div>
            )}
          </div>

          {/* Upload Jobs (local DB records) */}
          <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                Upload Jobs
              </h4>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => fileRef.current?.click()}
                  disabled={uploading}
                  className="px-3 py-1 bg-green-600 text-white rounded text-xs font-medium hover:bg-green-700 disabled:bg-gray-400"
                >
                  {uploading ? "Uploading..." : "+ Upload File"}
                </button>
                <input
                  ref={fileRef}
                  type="file"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) handleUpload(f);
                    e.target.value = "";
                  }}
                />
              </div>
            </div>

            {/* Inline confirm: delete document */}
            {pendingConfirm?.kind === "delete-doc" && (
              <div className="mb-2">
                <InlineConfirm
                  message={`Delete "${pendingConfirm.fileName}" from DB and file store?`}
                  confirmLabel="Delete"
                  variant="danger"
                  onConfirm={() => confirmDeleteDoc(pendingConfirm.docId)}
                  onCancel={cancelConfirm}
                />
              </div>
            )}

            {docs.length === 0 ? (
              <p className="text-xs text-gray-500 dark:text-gray-400 text-center py-4">
                No upload jobs
              </p>
            ) : (
              <ul className="space-y-2">
                {docs.map((doc) => (
                  <li
                    key={doc.id}
                    className="flex items-center justify-between p-2 bg-gray-50 dark:bg-gray-800 rounded text-sm"
                  >
                    <div className="flex-1 min-w-0">
                      <span className="font-medium text-gray-700 dark:text-gray-300">
                        {doc.file_name}
                      </span>
                      <span className="text-xs text-gray-400 ml-2">
                        {formatSize(doc.file_size)}
                      </span>
                      {statusBadge(doc.status)}
                      {(doc.status === "uploading" ||
                        doc.status === "pending") && (
                        <span className="text-xs text-blue-500 ml-1 animate-pulse">
                          ●
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 ml-2">
                      {(doc.status === "uploading" ||
                        doc.status === "pending" ||
                        doc.status === "error") && (
                        <button
                          onClick={() => handleSyncDoc(doc.id)}
                          disabled={syncing === doc.id}
                          className="text-xs text-blue-500 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
                          title="Refresh status from Gemini"
                        >
                          {syncing === doc.id ? "..." : "↻ Sync"}
                        </button>
                      )}
                      <button
                        onClick={() =>
                          setPendingConfirm({
                            kind: "delete-doc",
                            docId: doc.id,
                            fileName: doc.file_name,
                          })
                        }
                        className="text-xs text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                      >
                        Delete
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* File Store Documents (from Gemini API) */}
          <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                File Store Documents
              </h4>
              <button
                onClick={() => {
                  if (showStoreDocs) {
                    setShowStoreDocs(false);
                  } else {
                    setShowStoreDocs(true);
                    loadStoreDocs();
                  }
                }}
                className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 font-medium"
              >
                {showStoreDocs ? "Hide" : "Show"}
              </button>
            </div>

            {/* Inline confirm: delete store document */}
            {pendingConfirm?.kind === "delete-store-doc" && (
              <div className="mb-2">
                <InlineConfirm
                  message={`Delete "${pendingConfirm.displayName}" from Gemini file store?`}
                  confirmLabel="Delete"
                  variant="danger"
                  onConfirm={() => confirmDeleteStoreDoc(pendingConfirm.docName)}
                  onCancel={cancelConfirm}
                />
              </div>
            )}

            {showStoreDocs && (
              <div>
                {loadingStore ? (
                  <p className="text-xs text-gray-500 dark:text-gray-400 text-center py-4">
                    Loading from Gemini...
                  </p>
                ) : storeDocs.length === 0 ? (
                  <p className="text-xs text-gray-500 dark:text-gray-400 text-center py-4">
                    No documents in the Gemini file store
                  </p>
                ) : (
                  <>
                    <div className="flex items-center justify-end mb-2">
                      <button
                        onClick={loadStoreDocs}
                        className="text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
                      >
                        ↻ Refresh
                      </button>
                    </div>
                    <ul className="space-y-2">
                      {storeDocs.map((sd) => (
                        <li
                          key={sd.name}
                          className="flex items-center justify-between p-2 bg-blue-50 dark:bg-blue-900/10 rounded text-sm"
                        >
                          <div className="flex-1 min-w-0">
                            <span className="font-medium text-gray-700 dark:text-gray-300">
                              {sd.display_name || sd.name.split("/").pop()}
                            </span>
                            <span className="text-xs text-gray-400 ml-2">
                              {formatSize(sd.size_bytes)}
                            </span>
                            <span className="text-xs text-gray-400 ml-2">
                              {sd.mime_type}
                            </span>
                            <span className="ml-2">
                              {storeStateBadge(sd.state)}
                            </span>
                          </div>
                          <button
                            onClick={() =>
                              setPendingConfirm({
                                kind: "delete-store-doc",
                                docName: sd.name,
                                displayName:
                                  sd.display_name ||
                                  sd.name.split("/").pop() ||
                                  sd.name,
                              })
                            }
                            className="text-xs text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 ml-2"
                          >
                            Delete
                          </button>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            )}

            {expert.file_search_store_name && (
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-2 break-all">
                Store: {expert.file_search_store_name}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
