"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { deleteSession, getSession, updateNotes } from "@/lib/api";
import { DynamicJsonRenderer } from "@/components/diagnosis/DynamicJsonRenderer";
import { SourcesList } from "@/components/diagnosis/SourcesList";
import { InfographicGenerator } from "@/components/diagnosis/InfographicGenerator";
import { RelatedArticles } from "@/components/articles/RelatedArticles";
import { InlineConfirm } from "@/components/ui/InlineConfirm";
import { CategoryBadge } from "@/components/ui/CategoryBadge";
import { formatDate, truncate } from "@/lib/utils";
import type { SessionDetail } from "@/types";
import Link from "next/link";

export default function ArticlePage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.slug as string;
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [notesSaved, setNotesSaved] = useState(true);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const saveTimerRef = useRef<NodeJS.Timeout | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);

  useEffect(() => {
    if (sessionId) {
      getSession(sessionId)
        .then((data) => {
          setDetail(data);
          setNotes(data.notes || "");
        })
        .catch((err) => setError(String(err)));
    }
  }, [sessionId]);

  const saveNotes = useCallback(
    (value: string) => {
      if (!detail) return;
      updateNotes(detail.id, value || null).then(() => setNotesSaved(true));
    },
    [detail]
  );

  function handleNotesChange(value: string) {
    setNotes(value);
    setNotesSaved(false);
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => saveNotes(value), 1500);
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto">
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-300 text-sm">
          {error}
        </div>
        <Link href="/articles" className="text-blue-600 dark:text-blue-400 text-sm mt-3 inline-block hover:underline">
          &larr; Back to Knowledge Base
        </Link>
      </div>
    );
  }

  if (!detail) {
    return <p className="text-center text-gray-500 dark:text-gray-400 py-8">Loading...</p>;
  }

  return (
    <div className="max-w-7xl mx-auto">
      <Link
        href="/articles"
        className="text-sm text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 mb-4 inline-block"
      >
        &larr; Back to Knowledge Base
      </Link>

      <div className="flex gap-6">
        {/* Main article content */}
        <article className="flex-1 min-w-0 bg-white dark:bg-gray-800 rounded-lg shadow">
        {/* Header */}
        <div className="border-b border-gray-100 dark:border-gray-700 px-8 py-5">
          <div className="flex items-start justify-between gap-4 mb-3">
            <div className="flex-1 min-w-0">
              <h1 className="text-lg font-bold dark:text-gray-100">
                {detail.title || truncate(detail.error_text || "Image Diagnosis", 200)}
              </h1>
            </div>
            <div className="flex items-center gap-2">
              {detail.status && (
                <button
                  onClick={async () => {
                    setStatusLoading(true);
                    const newStatus = detail.status === "closed" ? "analyzed" : "closed";
                    try {
                      await fetch(`/api/incidents/${detail.id}/status`, {
                        method: "PATCH",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ status: newStatus }),
                      });
                      router.refresh();
                    } catch (err) {
                      console.error("Failed to update status:", err);
                    } finally {
                      setStatusLoading(false);
                    }
                  }}
                  disabled={statusLoading || confirmDelete}
                  className="px-3 py-1.5 text-xs font-medium text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {statusLoading
                    ? (detail.status === "closed" ? "Reopening..." : "Closing...")
                    : (detail.status === "closed" ? "Reopen" : "Close")
                  }
                </button>
              )}
              {!confirmDelete ? (
                <button
                  onClick={() => setConfirmDelete(true)}
                  disabled={statusLoading}
                  className="px-3 py-1.5 text-xs font-medium text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded hover:bg-red-100 dark:hover:bg-red-900/50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Delete
                </button>
              ) : (
                <InlineConfirm
                  message="Delete permanently?"
                  confirmLabel="Delete"
                  variant="danger"
                  timeout={6}
                  onConfirm={async () => {
                    await deleteSession(detail.id);
                    window.dispatchEvent(new Event("sessions-changed"));
                    router.push("/articles");
                  }}
                  onCancel={() => setConfirmDelete(false)}
                />
              )}
            </div>
          </div>
          {detail.title && detail.error_text && (
            <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 whitespace-pre-wrap break-words bg-gray-50 dark:bg-gray-700/50 rounded px-3 py-2">
              {detail.error_text}
            </p>
          )}
          <div className="flex items-center gap-4 mt-2 text-xs text-gray-400 dark:text-gray-500">
            <span>{formatDate(detail.created_at)}</span>
            {detail.model_used && <span>Model: {detail.model_used}</span>}
            <span className="font-mono">Session {detail.session_id.slice(0, 8)}</span>
          </div>

          {/* Categories section */}
          {detail.categories && detail.categories.length > 0 && (
            <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700">
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                Categories
              </h3>
              <div className="flex gap-2 flex-wrap">
                {detail.categories.map((cat, idx) => (
                  <CategoryBadge
                    key={idx}
                    category={cat.category}
                    confidence={cat.confidence}
                    isPrimary={cat.primary}
                    size="md"
                    showConfidence={true}
                  />
                ))}
              </div>
              {detail.classification_reasoning && (
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
                  <strong>Classification:</strong> {detail.classification_reasoning}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Structured content */}
        <div className="px-8 py-6 space-y-6">
          <DynamicJsonRenderer data={detail.raw_json} />
          <SourcesList sources={detail.grounding_sources} />
          {(detail.raw_json?.visual_aid_suggested === true && detail.raw_json?.image_generation_prompt) || detail.infographic_data ? (
            <InfographicGenerator
              suggestedPrompt={String(detail.raw_json?.image_generation_prompt || "")}
              incidentId={detail.id}
              savedInfographic={detail.infographic_data}
            />
          ) : null}
        </div>

        {/* File search citations */}
        {detail.file_search_results && detail.file_search_results.length > 0 && (
          <div className="border-t border-gray-100 dark:border-gray-700 px-8 py-5">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
              📄 Document Citations ({detail.file_search_results.length})
            </h3>
            <div className="space-y-2">
              {detail.file_search_results.map((r, i) => (
                <div key={i} className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
                  <div className="flex items-center gap-2 px-4 py-2 bg-gray-50 dark:bg-gray-800/50">
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
                  </div>
                  {r.text && (
                    <div className="px-4 py-2 text-xs text-gray-600 dark:text-gray-400 italic border-t border-gray-100 dark:border-gray-700">
                      &ldquo;{r.text}&rdquo;
                    </div>
                  )}
                  {r.citations.length > 0 && (
                    <div className="px-4 py-2 space-y-1 border-t border-gray-100 dark:border-gray-700">
                      {r.citations.map((c, ci) => (
                        <div key={ci} className="flex items-start gap-2 text-xs">
                          <span className="shrink-0 mt-0.5 w-1.5 h-1.5 rounded-full bg-blue-400" />
                          <span className="text-gray-600 dark:text-gray-400">{c.cited_text}</span>
                          <span className="shrink-0 text-gray-400">{(c.confidence * 100).toFixed(0)}%</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Notes */}
        <div className="border-t border-gray-100 dark:border-gray-700 px-8 py-5">
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

        {/* Export actions */}
        <div className="border-t border-gray-100 dark:border-gray-700 px-8 py-4 flex items-center gap-2">
          <button
            onClick={() => {
              navigator.clipboard.writeText(JSON.stringify(detail.raw_json, null, 2));
            }}
            className="px-3 py-1.5 text-xs font-medium text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors"
          >
            Copy JSON
          </button>
          <button
            onClick={() => {
              const blob = new Blob([detail.markdown_content], { type: "text/markdown" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = `diagnosis-${detail.session_id.slice(0, 8)}.md`;
              a.click();
              URL.revokeObjectURL(url);
            }}
            className="px-3 py-1.5 text-xs font-medium text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors"
          >
            Export .md
          </button>
          <Link
            href={`/?session=${detail.session_id}`}
            className="px-3 py-1.5 text-xs font-medium text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-800 rounded hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors"
          >
            Open in Dashboard
          </Link>
        </div>
      </article>

        {/* Right sidebar — related articles */}
        {detail.related_articles && detail.related_articles.length > 0 && (
          <aside className="w-72 shrink-0 hidden lg:block">
            <div className="sticky top-6">
              <RelatedArticles articles={detail.related_articles} />
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
